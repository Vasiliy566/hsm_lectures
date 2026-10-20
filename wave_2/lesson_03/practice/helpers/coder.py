"""Мини-кодер из занятия 1.2 плюс поиск: инструменты, их исполнение, цикл и проверка результата.

Модель видит только TOOLS — имена, описания и аргументы.
Функции ниже выполняет программа. Файлы меняются только в sandbox/ — копии project/.
"""
import json
import shutil
import subprocess
import sys
import time

from helpers.documents import PRACTICE, as_context, chunk_by_sections, load_documents
from helpers.llm import connect
from helpers.search import MeaningSearch, WordSearch, hybrid

PROJECT = PRACTICE / "project"
SANDBOX = PRACTICE / "sandbox"
CHECKS = PRACTICE / "checks"
RUNS = PRACTICE / "runs"


def tool(name: str, description: str, **params: str) -> dict:
    """Описание инструмента для модели. Все аргументы — строки или числа, все обязательные."""
    properties = {key: {"type": "integer" if key.endswith("_line") else "string", "description": text}
                  for key, text in params.items()}
    return {"type": "function", "name": name, "description": description, "strict": True,
            "parameters": {"type": "object", "properties": properties,
                           "required": list(params), "additionalProperties": False}}


TOOLS = [
    tool("search_docs", "Поиск по регламентам и FAQ магазина. Возвращает до 3 фрагментов "
                        "с id, редакцией и датами действия.",
         query="Что ищем, своими словами"),
    tool("search_code", "Поиск текста в файлах проекта. Возвращает строки вида путь:номер: строка.",
         text="Точный текст, например имя функции"),
    tool("read_file", "Строки файла проекта с номерами.",
         path="Путь от корня проекта, например shop/orders.py",
         start_line="Первая строка, с 1", end_line="Последняя строка"),
    tool("replace_in_file", "Заменяет фрагмент файла. old должен встречаться в файле ровно один раз. "
                            "Файлы в tests/ менять нельзя.",
         path="Путь от корня проекта", old="Точный текст, который заменить", new="Новый текст"),
    tool("run_tests", "Запускает тесты проекта и возвращает итог."),
]


# ---------------------------------------------------------------- исполнение инструментов

class Docs:
    """Индекс регламентов: фрагменты по пунктам с заголовком, гибридный поиск."""

    def __init__(self):
        chunks = [c for d in load_documents() for c in chunk_by_sections(d, with_header=True)]
        self.words, self.meaning = WordSearch(chunks), MeaningSearch(chunks)

    def search(self, query: str) -> str:
        return as_context(hybrid(query, self.words, self.meaning, k=3))


def execute(name: str, arguments: str, docs: Docs) -> str:
    """Выполняет вызов модели. Ошибку возвращаем модели текстом — программа не падает."""
    try:
        args = json.loads(arguments)
        if name == "search_docs":
            return docs.search(args["query"])
        if name == "search_code":
            return search_code(args["text"])
        if name == "read_file":
            return read_file(args["path"], args["start_line"], args["end_line"])
        if name == "replace_in_file":
            return replace_in_file(args["path"], args["old"], args["new"])
        if name == "run_tests":
            return run_tests(SANDBOX)["summary"]
        return f"ошибка: нет инструмента {name}"
    except Exception as error:  # noqa: BLE001 — любая ошибка становится результатом вызова
        return f"ошибка: {error}"


def safe_path(path: str):
    target = (SANDBOX / path).resolve()
    if not target.is_relative_to(SANDBOX) or not target.is_file():
        raise ValueError(f"нет такого файла в проекте: {path}")
    return target


def search_code(text: str) -> str:
    lines = []
    for file in sorted(SANDBOX.rglob("*.py")):
        for n, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
            if text in line:
                lines.append(f"{file.relative_to(SANDBOX)}:{n}: {line.strip()}")
    return "\n".join(lines[:20]) or "ничего не найдено"


def read_file(path: str, start_line: int, end_line: int) -> str:
    lines = safe_path(path).read_text(encoding="utf-8").splitlines()
    start, end = max(1, start_line), min(len(lines), end_line)
    return "\n".join(f"{n:>4}  {lines[n - 1]}" for n in range(start, end + 1))


def replace_in_file(path: str, old: str, new: str) -> str:
    if path.startswith("tests"):
        raise ValueError("тесты менять нельзя")
    file = safe_path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise ValueError(f"old встречается {text.count(old)} раз, нужно ровно 1")
    file.write_text(text.replace(old, new), encoding="utf-8")
    return "заменено"


def run_tests(folder, tests="tests") -> dict:
    """Тесты из папки tests запускаются против кода из folder."""
    proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(tests)],
                          cwd=folder, capture_output=True, text=True, timeout=60)
    lines = proc.stderr.strip().splitlines()
    ran = next((line for line in lines if line.startswith("Ran ")), "тесты не запустились")
    return {"passed": proc.returncode == 0, "summary": f"{ran} — {lines[-1] if lines else ''}"}


# ---------------------------------------------------------------- цикл агента

def reset_sandbox() -> None:
    shutil.rmtree(SANDBOX, ignore_errors=True)
    shutil.copytree(PROJECT, SANDBOX)


def run_agent(task: str, instructions: str, max_steps: int = 15) -> dict:
    """Запросы к модели, пока она вызывает инструменты. Историю ведёт программа."""
    client, model = connect()
    docs = Docs()
    history = [{"role": "user", "content": task}]
    trace = {"model": model, "task": task, "steps": [], "answer": None}

    for step in range(1, max_steps + 1):
        response = client.responses.create(model=model, instructions=instructions,
                                           input=history, tools=TOOLS)
        if response.status == "incomplete":
            print(f"шаг {step}: ответ не завершён — останавливаемся")
            break
        print(f"шаг {step}: во входе {response.usage.input_tokens} токенов")
        history += response.output
        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            trace["answer"] = response.output_text
            print("\nОтвет модели:\n" + response.output_text)
            break
        for call in calls:
            result = execute(call.name, call.arguments, docs)
            print(f"   {call.name}({short(call.arguments, 90)})\n     → {short(result, 110)}")
            history.append({"type": "function_call_output", "call_id": call.call_id, "output": result})
            trace["steps"].append({"step": step, "tokens": response.usage.input_tokens,
                                   "tool": call.name, "arguments": call.arguments, "result": result})
    else:
        print(f"лимит {max_steps} шагов — ответа нет")

    RUNS.mkdir(exist_ok=True)
    path = RUNS / f"coder_{time.strftime('%H%M%S')}.json"
    path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nтрасса: {path.relative_to(PRACTICE)}")
    return trace


def check_result(trace: dict) -> None:
    """Проверяем факты, а не слова модели."""
    tests = run_tests(SANDBOX)
    hidden = run_tests(SANDBOX, CHECKS)
    changed = [str(f.relative_to(SANDBOX)) for f in sorted(SANDBOX.rglob("*.py"))
               if "__pycache__" not in f.parts and (PROJECT / f.relative_to(SANDBOX)).exists()
               and f.read_bytes() != (PROJECT / f.relative_to(SANDBOX)).read_bytes()]
    found = sorted({line.split('"')[1] for s in trace["steps"] if s["tool"] == "search_docs"
                    for line in s["result"].splitlines() if line.startswith("<fragment id=")})
    cited = "policy-v3#4.2" in (trace["answer"] or "")
    print("\nПРОВЕРКА ПРОГРАММОЙ")
    print(f"  {'✓' if changed else '✗'} изменены файлы: {', '.join(changed) or 'нет'}")
    print(f"  {'✓' if tests['passed'] else '✗'} тесты проекта: {tests['summary']}")
    print(f"  {'✓' if hidden['passed'] else '✗'} проверка SEV-418 по регламенту: {hidden['summary']}")
    print(f"  · поиск по регламентам нашёл: {', '.join(found) or 'ничего'}")
    print(f"  {'✓' if cited else '✗'} в ответе есть ссылка на policy-v3#4.2")


def short(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "…"
