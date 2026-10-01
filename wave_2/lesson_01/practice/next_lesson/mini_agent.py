"""Заглянуть вперёд (занятие 1.2). Цикл агента: модель читает файлы, правит код и запускает тесты.

Запуск:  python next_lesson/mini_agent.py                 — каждое изменение файла подтверждаете вы
         python next_lesson/mini_agent.py --yes           — без подтверждений (для прогона на задачах)
         python next_lesson/mini_agent.py --workspace path/to/project --task "Что сделать"
         python next_lesson/mini_agent.py --reset         — вернуть исходную версию workspace/durations.py

Всё, что видно в этом файле, — это harness: инструкции, инструменты,
история (состояние), лимит шагов, подтверждение и журнал.
"""
import argparse
import difflib
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()
MODEL = os.environ["OPENAI_MODEL"]
HERE = Path(__file__).parent
WORKSPACE = (HERE / "workspace").resolve()  # меняется аргументом --workspace
AUTO_APPROVE = False                      # меняется флагом --yes

ORIGINAL = '''import re

UNITS = {"h": 3600, "m": 60, "s": 1}


def parse_duration(text: str) -> int:
    """Переводит строку вроде "1h 30m" в секунды."""
    total = 0
    for number, unit in re.findall(r"(\\d+)([hms])", text):
        total += int(number) * UNITS[unit]
    return total
'''


# ---------- инструменты: обычные функции, которые исполняет программа ----------
def safe_path(name: str) -> Path:
    path = (WORKSPACE / name).resolve()
    if WORKSPACE not in path.parents:
        raise ValueError("доступ только к файлам внутри workspace/")
    return path


def list_files() -> str:
    files = [p.relative_to(WORKSPACE).as_posix() for p in WORKSPACE.rglob("*")
             if p.is_file() and not any(part.startswith((".", "__")) for part in p.parts)]
    return "\n".join(sorted(files))


def read_file(path: str) -> str:
    return safe_path(path).read_text(encoding="utf-8")


def write_file(path: str, content: str) -> str:
    target = safe_path(path)
    if target.name.startswith("test_"):
        return "Отказано: тесты менять нельзя."
    old = target.read_text(encoding="utf-8") if target.exists() else ""
    diff = "".join(difflib.unified_diff(old.splitlines(True), content.splitlines(True), path, path))
    # Подтверждение человека: изменение показываем до записи на диск.
    print("\n--- предлагаемое изменение ---\n" + (diff or "(без изменений)"))
    if not AUTO_APPROVE and input("Применить? [y/N] ").strip().lower() != "y":
        return "Пользователь отклонил изменение."
    target.write_text(content, encoding="utf-8")
    return "Файл сохранён."


def run_tests() -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "-q"],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=60,
    )
    return (proc.stdout + proc.stderr)[-3000:]


FUNCTIONS = {"list_files": list_files, "read_file": read_file,
             "write_file": write_file, "run_tests": run_tests}


def tool(fn_name, description, **params):
    return {"type": "function", "name": fn_name, "description": description,
            "parameters": {"type": "object",
                           "properties": {k: {"type": "string", "description": v} for k, v in params.items()},
                           "required": list(params)}}


TOOLS = [
    tool("list_files", "Список файлов в рабочей папке."),
    tool("read_file", "Прочитать файл из рабочей папки.", path="имя файла"),
    tool("write_file", "Заменить содержимое файла целиком.", path="имя файла", content="новый текст файла"),
    tool("run_tests", "Запустить тесты проекта и вернуть вывод."),
]

INSTRUCTIONS = """Ты работаешь с Python-проектом в рабочей папке через инструменты.
Сначала посмотри список файлов, прочитай код и тесты, запусти тесты.
Тесты не меняй. Меняй только то, что нужно для задачи.
После изменения снова запусти тесты. Когда тесты пройдут,
коротко опиши, что было не так и что ты изменил."""

DEFAULT_TASK = "Исправь код так, чтобы проходили все тесты."


def main():
    global WORKSPACE, AUTO_APPROVE
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=str(HERE / "workspace"), help="папка проекта")
    parser.add_argument("--task", default=DEFAULT_TASK, help="текст задачи")
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--yes", action="store_true", help="применять изменения без вопроса")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    WORKSPACE = Path(args.workspace).resolve()
    AUTO_APPROVE = args.yes

    if args.reset:
        (HERE / "workspace" / "durations.py").write_text(ORIGINAL, encoding="utf-8")
        print("next_lesson/workspace/durations.py восстановлен.")
        return

    history = [{"role": "user", "content": args.task}]  # состояние текущего запуска
    trace = open("trace.jsonl", "w", encoding="utf-8")
    tokens_in = tokens_out = 0

    for step in range(1, args.max_steps + 1):
        response = client.responses.create(
            model=MODEL, instructions=INSTRUCTIONS, input=history, tools=TOOLS)
        tokens_in += response.usage.input_tokens
        tokens_out += response.usage.output_tokens
        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:  # модель ответила текстом — цикл окончен
            print(f"\n[шаг {step}] итог:\n{response.output_text}")
            break

        # Ответ модели сохраняем в истории: на следующем шаге она увидит свои вызовы.
        history += response.output

        for call in calls:
            call_args = json.loads(call.arguments or "{}")
            print(f"[шаг {step}] {call.name}({', '.join(call_args)})")
            try:
                result = FUNCTIONS[call.name](**call_args)
            except Exception as e:  # ошибку тоже возвращаем модели
                result = f"Ошибка: {e}"
            trace.write(json.dumps({"step": step, "tool": call.name, "args": call_args,
                                    "result": result[:500]}, ensure_ascii=False) + "\n")
            history.append({"type": "function_call_output", "call_id": call.call_id, "output": result})
    else:
        print(f"\nОстановлено: лимит {args.max_steps} шагов.")

    trace.close()
    print(f"\nТокены: вход {tokens_in}, выход {tokens_out}. Журнал действий: trace.jsonl")
    print(f"Проверьте сами: cd {args.workspace} && python -m unittest")


if __name__ == "__main__":
    main()
