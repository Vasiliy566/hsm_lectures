"""Домашнее задание 2: агент уровня 2 для AgentScore (planerverse.ru).

Платформа запускает агента так:
    python /agent/agent.py --task-file /task/TASK.md --workspace /testbed
Агент читает задачу, меняет файлы в /testbed и завершается. Оценивается git diff.
Модель и ключ приходят из окружения: OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL.

Уровень 2 — инструменты и цикл (занятие 1.2):
  * модель сама ищет и читает нужные файлы и правит их по частям;
  * программа выполняет функции, проверяет аргументы и пути, возвращает результат с call_id;
  * историю ведёт программа (previous_response_id на платформе запрещён);
  * цикл ограничен числом шагов и временем.

Инструменты уже написаны (класс Workspace). Ваша часть помечена TODO.
Образец цикла — common.py и 05_mini_coder.py из практики занятия.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from openai import OpenAI

MAX_STEPS = 30
TIME_BUDGET_S = 480           # платформа даёт 600 с; оставляем запас
MAX_OUTPUT_TOKENS = 4096      # лимит платформы на один запрос
MAX_TOOL_OUTPUT = 12000       # результат инструмента тоже занимает вход модели

# TODO 1. Инструкции: роль, порядок работы с инструментами, правила правки,
# когда остановиться. Вспомните SKILL.md fix-failing-test из практики — это хорошая основа.
INSTRUCTIONS = """..."""

TOOLS = [
    {"type": "function", "name": "list_files",
     "description": "Пути файлов репозитория (git ls-files) внутри папки. Только имена.",
     "parameters": {"type": "object", "properties": {
         "folder": {"type": "string", "description": "Папка относительно корня, '.' — весь репозиторий"}},
         "required": ["folder"], "additionalProperties": False}},
    {"type": "function", "name": "search_code",
     "description": "Поиск строки в файлах *.py. Возвращает до 50 совпадений: путь:строка:текст.",
     "parameters": {"type": "object", "properties": {
         "text": {"type": "string", "description": "Искомая строка, например имя функции"}},
         "required": ["text"], "additionalProperties": False}},
    {"type": "function", "name": "read_file",
     "description": "Строки файла с номерами. Читайте по частям: не больше 300 строк за раз.",
     "parameters": {"type": "object", "properties": {
         "path": {"type": "string"},
         "start_line": {"type": "integer", "description": "С какой строки, от 1"},
         "end_line": {"type": "integer", "description": "По какую строку включительно"}},
         "required": ["path", "start_line", "end_line"], "additionalProperties": False}},
    {"type": "function", "name": "replace_in_file",
     "description": "Заменить фрагмент old_text на new_text. old_text должен встречаться в файле ровно один раз.",
     "parameters": {"type": "object", "properties": {
         "path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}},
         "required": ["path", "old_text", "new_text"], "additionalProperties": False}},
]


class ToolError(Exception):
    pass


class Workspace:
    """Инструменты. Все пути проверяются: только внутри репозитория и не в .git."""

    def __init__(self, root: Path):
        self.root = root
        self.changed: set[str] = set()

    def path(self, rel: str) -> Path:
        target = (self.root / rel).resolve()
        if target != self.root and self.root not in target.parents:
            raise ToolError(f"access_denied: путь вне репозитория: {rel}")
        if ".git" in target.relative_to(self.root).parts:
            raise ToolError("access_denied: .git трогать нельзя")
        return target

    def list_files(self, folder: str) -> str:
        self.path(folder)
        out = subprocess.run(["git", "ls-files", "--", folder], cwd=self.root,
                             capture_output=True, text=True).stdout
        files = out.splitlines()
        return "\n".join(files[:400]) + (f"\n… ещё {len(files) - 400}" if len(files) > 400 else "")

    def search_code(self, text: str) -> str:
        out = subprocess.run(["git", "grep", "-n", "-F", "--", text, "*.py"], cwd=self.root,
                             capture_output=True, text=True).stdout
        lines = out.splitlines()
        return "\n".join(line[:300] for line in lines[:50]) or "совпадений нет"

    def read_file(self, path: str, start_line: int, end_line: int) -> str:
        target = self.path(path)
        if not target.is_file():
            raise ToolError(f"not_found: нет файла {path}")
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start, end = max(1, start_line), min(len(lines), end_line, start_line + 299)
        body = "\n".join(f"{i}: {lines[i - 1]}" for i in range(start, end + 1))
        return f"{path}, строки {start}-{end} из {len(lines)}\n{body}"

    def replace_in_file(self, path: str, old_text: str, new_text: str) -> str:
        target = self.path(path)
        if not target.is_file():
            raise ToolError(f"not_found: нет файла {path}")
        source = target.read_text(encoding="utf-8")
        count = source.count(old_text)
        if count != 1:
            raise ToolError(f"bad_arguments: old_text найден {count} раз, нужен ровно 1")
        target.write_text(source.replace(old_text, new_text), encoding="utf-8")
        self.changed.add(path)
        return f"заменено в {path}"

    def execute(self, name: str, arguments: str) -> str:
        """Ошибка тоже возвращается модели как результат: она может исправить вызов."""
        try:
            args = json.loads(arguments)
            if name not in {t["name"] for t in TOOLS}:
                raise ToolError(f"unknown_tool: {name}")
            result = getattr(self, name)(**args)
        except (ToolError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as e:
            result = f"ERROR {e}"
        return result[:MAX_TOOL_OUTPUT]


def run(client: OpenAI, model: str, task: str, ws: Workspace) -> None:
    """TODO 2. Цикл агента.

    1. history — список, первый элемент: {"role": "user", "content": задача}.
    2. На каждом шаге: client.responses.create(model=..., instructions=INSTRUCTIONS,
       input=history, tools=TOOLS, max_output_tokens=MAX_OUTPUT_TOKENS).
    3. Весь response.output — в history (там просьбы модели и, возможно, рассуждения).
    4. Для каждого элемента с type == "function_call": ws.execute(name, arguments) и
       {"type": "function_call_output", "call_id": тот же call_id, "output": результат} — в history.
    5. Нет вызовов — модель закончила, выходим.
    6. Ограничения: не больше MAX_STEPS шагов и TIME_BUDGET_S секунд.

    TODO 3 (по желанию). Обработать response.status == "incomplete": ответ оборвался
    на лимите 4096 токенов — попросить продолжить короче.
    """
    raise NotImplementedError


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args()

    ws = Workspace(Path(args.workspace).resolve())
    task = Path(args.task_file).read_text(encoding="utf-8")
    client = OpenAI(base_url=os.environ.get("OPENAI_BASE_URL"))  # ключ — из OPENAI_API_KEY
    run(client, os.environ["OPENAI_MODEL"], task, ws)
    print("изменены файлы:", ", ".join(sorted(ws.changed)) or "нет")
    return 0


if __name__ == "__main__":
    sys.exit(main())
