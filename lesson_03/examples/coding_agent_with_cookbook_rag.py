"""Coding agent из лекции 02, дополненный RAG по локальной Python Cookbook.

Запуск (из папки 03/examples):
    python coding_agent_with_cookbook_rag.py \
      --repo ../coding_agent/sample_repo \
      --book "/Users/vasily/Downloads/D. Beazley, B.K. Jones - Python Cookbook, 3rd Edition. 2013.pdf" \
      --task "Исправь average([]) и объясни, как тестируется крайний случай"

Скрипт намеренно работает в режиме read-only: он читает файлы, запускает тесты и
ищет по книге, но не редактирует код. Это безопасная точка для занятия. Добавлять
write_file стоит отдельным tool с approval после того, как траектория стала понятна.

Книга не копируется в репозиторий: PDF остаётся локальным, а фрагменты извлекаются
в память на время запуска. Используйте книгу только при наличии прав на её чтение.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from google import genai
from google.genai import types
from pypdf import PdfReader


MODEL = "gemini-3.5-flash"
EMBEDDING_MODEL = "gemini-embedding-2"
MAX_AGENT_STEPS = 8
CHUNK_SIZE_LIMIT = 1_800
CHUNK_OVERLAP = 240
CONSOLE_WIDTH = 96
# PDF extraction sometimes wraps a heading into two or three physical lines
# (e.g. "Arbitrary\nLength"). The semantic boundary stays the following
# Problem/Solution marker, so we allow those wrapped title lines explicitly.
RECIPE_RE = re.compile(
    r"(?m)^(?P<recipe>\d{1,2}\.\d{1,2}\.)\s+(?P<title>(?:[^\n]+\n){0,3}?[^\n]+?)\n(?:Problem|Solution)\b"
)

# В конце PDF после рецептов идут приложения, указатель и служебные страницы.
# По ним нельзя строить «рецепт»: они попадают в retrieval, но не отвечают на
# вопрос о коде. В извлечённом PDF заголовки иногда разорваны пробелами, поэтому
# сравниваем и исходный вид строки, и её буквенно-цифровой ключ.
TERMINAL_SECTION_RE = re.compile(r"(?mi)^\s*(?:appendix\s+[a-z]|index|about\s+the\s+authors)\s*$")


@dataclass
class CookbookChunk:
    recipe: str
    title: str
    page_from: int
    page_to: int
    text: str


@dataclass(frozen=True)
class CookbookDiagnostics:
    recipes: int
    chunks: int
    max_chunk_chars: int
    first_recipe: str
    last_recipe: str
    page_from: int
    page_to: int


def normalize(text: str) -> str:
    """Убирает артефакты PDF, не меняя смысл и не склеивая слова без пробела."""
    return re.sub(r"[ \t]+", " ", text).replace("\x00", "").strip()


def print_console_section(title: str) -> None:
    print(f"\n{title}\n{'-' * min(len(title), CONSOLE_WIDTH)}")


def print_console_paragraph(text: str) -> None:
    print(textwrap.fill(" ".join(text.split()), width=CONSOLE_WIDTH))


def print_json_preview(value: object, limit: int = 900) -> None:
    rendered = json.dumps(value, ensure_ascii=False, indent=2)
    print(rendered[:limit])
    if len(rendered) > limit:
        print("… вывод инструмента сокращён …")


def clean_title(text: str) -> str:
    """Склеивает переносы заголовка и типичный PDF-артефакт `L ength`."""
    title = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\b([A-Z]) (?=[a-z]{2,})", r"\1", title)


def heading_key(text: str) -> str:
    """Нормализует разорванный PDF-заголовок для сравнения, не для выдачи."""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def is_terminal_heading(line: str) -> bool:
    """Проверяет обычные и разорванные заголовки конца содержательной части."""
    compact = heading_key(line)
    return bool(TERMINAL_SECTION_RE.fullmatch(line.strip())) or compact in {
        "appendixa",
        "appendixb",
        "index",
        "abouttheauthors",
        "colophon",
    }


def find_content_end(text: str, start: int) -> int:
    """Находит первую служебную секцию после последнего рецепта."""
    for line_match in re.finditer(r"(?m)^(.*)$", text[start:]):
        if is_terminal_heading(line_match.group(1)):
            return start + line_match.start()
    return len(text)


def split_oversized_block(block: str, limit: int) -> list[str]:
    """Делит большой PDF-блок по строкам, затем по словам.

    Одно очень длинное слово или URL всё равно режем жёстко: лимит фрагмента
    является инвариантом ingestion, а не пожеланием.
    """
    if len(block) <= limit:
        return [block]

    lines = [normalize(line) for line in block.splitlines() if normalize(line)]
    units: list[str] = []
    for line in lines:
        if len(line) <= limit:
            units.append(line)
            continue

        current_words: list[str] = []
        for word in line.split():
            if len(word) > limit:
                if current_words:
                    units.append(" ".join(current_words))
                    current_words = []
                units.extend(word[offset : offset + limit] for offset in range(0, len(word), limit))
                continue
            candidate = " ".join([*current_words, word])
            if current_words and len(candidate) > limit:
                units.append(" ".join(current_words))
                current_words = [word]
            else:
                current_words.append(word)
        if current_words:
            units.append(" ".join(current_words))
    return units


def overlap_tail(units: list[str], max_chars: int) -> list[str]:
    """Возвращает только целые последние строки/абзацы для overlap."""
    tail: list[str] = []
    length = 0
    for unit in reversed(units):
        extra = len(unit) + (2 if tail else 0)
        if length + extra > max_chars:
            break
        tail.insert(0, unit)
        length += extra
    return tail


def split_recipe(recipe: str, title: str, page_from: int, page_to: int, text: str) -> list[CookbookChunk]:
    """Режет длинный рецепт по абзацам с коротким overlap.

    Основная граница - рецепт, а не фиксированное число символов. Перекрытие
    сохраняет переходы Problem -> Solution -> Discussion, если рецепт длинный.
    """
    paragraphs = [normalize(p) for p in re.split(r"\n\s*\n", text) if normalize(p)]
    units = [
        unit
        for paragraph in paragraphs
        for unit in split_oversized_block(paragraph, CHUNK_SIZE_LIMIT)
    ]
    output: list[CookbookChunk] = []
    current: list[str] = []

    for unit in units:
        if len(unit) > CHUNK_SIZE_LIMIT:
            raise AssertionError("split_oversized_block нарушил лимит фрагмента")
        candidate = "\n\n".join([*current, unit])
        if current and len(candidate) > CHUNK_SIZE_LIMIT:
            output.append(CookbookChunk(recipe, title, page_from, page_to, "\n\n".join(current)))
            current = overlap_tail(current, CHUNK_OVERLAP)
            if len("\n\n".join([*current, unit])) > CHUNK_SIZE_LIMIT:
                current = []
            current.append(unit)
        else:
            current.append(unit)
    if current:
        output.append(CookbookChunk(recipe, title, page_from, page_to, "\n\n".join(current)))
    if any(len(chunk.text) > CHUNK_SIZE_LIMIT for chunk in output):
        raise AssertionError("Рецепт разрезан на фрагменты больше лимита")
    return output


def build_cookbook_chunks(pdf_path: Path) -> list[CookbookChunk]:
    """Извлекает рецепты из PDF и сохраняет chapter/recipe/page metadata.

    Ищем заголовок рецепта перед Problem/Solution. Если распознавание PDF не нашло
    структуру, останавливаемся: молча резать весь PDF по 500 символов здесь было бы
    ровно тем антипримером RAG, который разбираем на занятии.
    """
    reader = PdfReader(str(pdf_path))
    pages = [(number + 1, page.extract_text() or "") for number, page in enumerate(reader.pages)]
    joined = "\n\f\n".join(f"[[PAGE:{number}]]\n{text}" for number, text in pages)
    page_markers = [(marker.start(), int(marker.group(1))) for marker in re.finditer(r"\[\[PAGE:(\d+)\]\]", joined)]

    def page_at(position: int) -> int:
        """Номер страницы по ближайшему предшествующему маркеру PDF."""
        return next(page for offset, page in reversed(page_markers) if offset <= position)

    matches = list(RECIPE_RE.finditer(joined))
    if not matches:
        raise ValueError("Не удалось выделить рецепты из PDF. Проверьте, что это текстовый PDF Python Cookbook.")

    # Ищем конец от первого рецепта, а не от последнего regex-match: иначе
    # случайный похожий фрагмент в указателе мог бы стать «последним рецептом».
    content_end = find_content_end(joined, matches[0].start())
    matches = [match for match in matches if match.start() < content_end]
    if not matches:
        raise ValueError("После отсечения указателя не осталось рецептов.")

    chunks: list[CookbookChunk] = []
    for index, match in enumerate(matches):
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else content_end
        )
        raw = joined[match.start():end]
        page_from, page_to = page_at(match.start()), page_at(max(match.start(), end - 1))
        cleaned = re.sub(r"\[\[PAGE:\d+\]\]", "", raw)
        chunks.extend(
            split_recipe(
                recipe=match.group("recipe"),
                title=clean_title(match.group("title")),
                page_from=page_from,
                page_to=page_to,
                text=cleaned,
            )
        )
    if not chunks:
        raise ValueError("Не удалось извлечь ни одного фрагмента Cookbook.")
    if any(len(chunk.text) > CHUNK_SIZE_LIMIT for chunk in chunks):
        raise AssertionError("Ingestion создал фрагмент больше CHUNK_SIZE_LIMIT")
    return chunks


def cookbook_diagnostics(chunks: list[CookbookChunk]) -> CookbookDiagnostics:
    """Короткая проверяемая сводка для подготовки домашки без обращения к API."""
    if not chunks:
        raise ValueError("Нельзя построить диагностику по пустому набору фрагментов.")
    recipes = sorted({chunk.recipe for chunk in chunks}, key=lambda value: tuple(map(int, value[:-1].split("."))))
    return CookbookDiagnostics(
        recipes=len(recipes),
        chunks=len(chunks),
        max_chunk_chars=max(len(chunk.text) for chunk in chunks),
        first_recipe=recipes[0],
        last_recipe=recipes[-1],
        page_from=min(chunk.page_from for chunk in chunks),
        page_to=max(chunk.page_to for chunk in chunks),
    )


def print_cookbook_diagnostics(chunks: list[CookbookChunk]) -> None:
    report = cookbook_diagnostics(chunks)
    print(
        "Cookbook ingestion: "
        f"{report.recipes} рецептов, {report.chunks} фрагментов, "
        f"максимум {report.max_chunk_chars}/{CHUNK_SIZE_LIMIT} символов."
    )
    print(
        f"Границы: рецепт {report.first_recipe} .. {report.last_recipe}; "
        f"страницы PDF {report.page_from} .. {report.page_to}."
    )


class CookbookRag:
    def __init__(self, client: genai.Client, pdf_path: Path, *, chunks: list[CookbookChunk] | None = None) -> None:
        self.client = client
        self.chunks = chunks if chunks is not None else build_cookbook_chunks(pdf_path)
        documents = [f"Recipe {c.recipe} {c.title}\n{c.text}" for c in self.chunks]
        self.matrix = self._embed(documents, task_type="RETRIEVAL_DOCUMENT")

    def _embed(self, texts: list[str], *, task_type: str) -> np.ndarray:
        # Batch the calls: a full book may contain hundreds of recipe fragments.
        vectors: list[list[float]] = []
        for start in range(0, len(texts), 64):
            contents = [
                types.UserContent(parts=[types.Part(text=text)])
                for text in texts[start : start + 64]
            ]
            response = self.client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=contents,
                config=types.EmbedContentConfig(task_type=task_type),
            )
            vectors.extend(item.values for item in response.embeddings)
        result = np.asarray(vectors, dtype=np.float32)
        return result / np.maximum(np.linalg.norm(result, axis=1, keepdims=True), 1e-12)

    def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        q = self._embed([query], task_type="RETRIEVAL_QUERY")[0]
        scores = self.matrix @ q
        results: list[dict[str, Any]] = []
        for idx in np.argsort(scores)[::-1][:limit]:
            chunk = self.chunks[int(idx)]
            results.append(
                {
                    "recipe": f"{chunk.recipe} {chunk.title}",
                    "pages": f"{chunk.page_from}-{chunk.page_to}",
                    "score": round(float(scores[idx]), 3),
                    # Ограничение делает tool result компактным и оставляет место для repo observations.
                    "excerpt": normalize(chunk.text)[:1_200],
                }
            )
        return results


def inside(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    if root != candidate and root not in candidate.parents:
        raise ValueError("Разрешены только файлы внутри --repo.")
    return candidate


def tool_declarations() -> list[types.Tool]:
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="list_files",
                    description="Показать файлы в учебном репозитории. Используй до чтения незнакомого пути.",
                    parameters_json_schema={"type": "object", "properties": {}},
                ),
                types.FunctionDeclaration(
                    name="read_file",
                    description="Прочитать UTF-8 текстовый файл внутри учебного репозитория.",
                    parameters_json_schema={
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                ),
                types.FunctionDeclaration(
                    name="run_tests",
                    description="Запустить pytest -q внутри учебного репозитория и вернуть stdout/stderr/код завершения.",
                    parameters_json_schema={"type": "object", "properties": {}},
                ),
                types.FunctionDeclaration(
                    name="search_python_cookbook",
                    description="Найти до трёх релевантных рецептов в локальной Python Cookbook. Возвращает номер рецепта, страницы и фрагмент.",
                    parameters_json_schema={
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                ),
            ]
        )
    ]


def execute_tool(name: str, args: dict[str, Any], root: Path, rag: CookbookRag) -> dict[str, Any]:
    """Единый registry: неизвестный tool не исполняется как shell-команда."""
    if name == "list_files":
        files = [
            str(p.relative_to(root))
            for p in root.rglob("*")
            if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts
        ]
        return {"files": sorted(files)[:100]}
    if name == "read_file":
        path = inside(root, str(args["path"]))
        if not path.is_file() or path.stat().st_size > 50_000:
            raise ValueError("Файл отсутствует, не является файлом или слишком велик для контекста.")
        return {"path": str(path.relative_to(root)), "content": path.read_text(encoding="utf-8")}
    if name == "run_tests":
        run = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"], cwd=root, text=True, capture_output=True, timeout=30
        )
        return {"exit_code": run.returncode, "stdout": run.stdout[-6_000:], "stderr": run.stderr[-2_000:]}
    if name == "search_python_cookbook":
        return {"results": rag.search(str(args["query"]))}
    raise ValueError(f"Неизвестный tool: {name}")


def response_parts(response: Any) -> list[Any]:
    """Берём parts из ответа модели; не полагаемся на response.text, где tool calls скрыты."""
    if not response.candidates or not response.candidates[0].content:
        raise RuntimeError("Модель не вернула content.")
    return list(response.candidates[0].content.parts or [])


def run_agent(client: genai.Client, root: Path, rag: CookbookRag, task: str) -> str:
    system = """Ты coding agent в учебном Python-репозитории. Работай доказательно.
Сначала прочитай нужные файлы и воспроизведи ошибку тестом. Для Python-подходов
используй search_python_cookbook, когда это уместно. Не редактируй файлы: после
диагностики предложи минимальное изменение, назови доказательства и попроси approval.
Не утверждай, что тесты проходят, без результата run_tests."""
    history: list[types.Content] = [types.Content(role="user", parts=[types.Part.from_text(text=task)])]

    for step in range(1, MAX_AGENT_STEPS + 1):
        response = client.models.generate_content(
            model=MODEL,
            contents=history,
            config=types.GenerateContentConfig(system_instruction=system, tools=tool_declarations()),
        )
        parts = response_parts(response)

        # Критичный фикс относительно наивного цикла: добавляем в историю КАЖДЫЙ
        # ответ LLM, включая обычный текст. Затем выбираем следующее состояние по
        # parts: tool calls -> observations -> следующий вызов; текст -> final.
        history.append(types.Content(role="model", parts=parts))
        calls = [part.function_call for part in parts if getattr(part, "function_call", None)]
        text = "\n".join(part.text for part in parts if getattr(part, "text", None)).strip()

        print_console_section(f"ШАГ {step}")
        if text:
            print(text)

        if not calls:
            if text:
                return text
            raise RuntimeError("Протокольная ошибка: ни текста, ни function_call.")

        tool_results: list[types.Part] = []
        for call in calls:
            try:
                result = execute_tool(call.name, dict(call.args or {}), root, rag)
            except Exception as exc:  # tool error тоже observation, а не падение траектории
                result = {"error": type(exc).__name__, "message": str(exc)}
            print_console_section(f"TOOL: {call.name}")
            print_json_preview(result)
            tool_results.append(types.Part.from_function_response(name=call.name, response=result))
        history.append(types.Content(role="user", parts=tool_results))

    raise RuntimeError(f"Достигнут max_steps={MAX_AGENT_STEPS}; агент остановлен безопасно.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, help="Папка учебного репозитория")
    parser.add_argument("--book", type=Path, required=True, help="Локальный PDF Python Cookbook")
    parser.add_argument("--task", help="Задача для coding agent")
    parser.add_argument(
        "--check-book",
        action="store_true",
        help="Проверить границы и размеры фрагментов Cookbook без Gemini API.",
    )
    args = parser.parse_args()
    book = args.book.resolve()
    if not book.is_file():
        raise SystemExit("Проверьте --book.")

    chunks = build_cookbook_chunks(book)
    print_cookbook_diagnostics(chunks)
    if args.check_book:
        return
    if not args.repo or not args.task:
        raise SystemExit("Для запуска агента укажите --repo и --task или используйте --check-book.")
    root = args.repo.resolve()
    if not root.is_dir():
        raise SystemExit("Проверьте --repo.")

    # Импорт откладывается, чтобы --check-book не требовал ключ Gemini.
    from gemini_client import get_client

    client = get_client()
    rag = CookbookRag(client, book, chunks=chunks)
    print_console_section("RAG ГОТОВ")
    print_console_paragraph(f"Источник остаётся локальным: {book.name}")
    final = run_agent(client, root, rag, args.task)
    print_console_section("ФИНАЛЬНЫЙ ОТВЕТ")
    print(final)


if __name__ == "__main__":
    main()
