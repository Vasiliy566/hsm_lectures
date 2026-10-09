"""Практика 2. Настоящая модель выбирает инструменты, программа их выполняет.

Только чтение: list_files, read_file, run_tests. Записи в этом скрипте нет.

Запуск:
    python 04_tool_call.py
    python 04_tool_call.py "Какие тесты падают и в каком файле функция, которую они проверяют?"
    python 04_tool_call.py --manual     — без API: роль модели играете вы
После запуска откройте runs/tools_*.json: там вся история, которую получала модель.
"""
import argparse

from common import agent_loop
from tools import TOOLS, Permissions, execute_call

READ_ONLY = [t for t in TOOLS if t["name"] != "write_file"]

INSTRUCTIONS = """Ты помогаешь разработчику разобраться в небольшом проекте на Python.
Факты о проекте получай только через инструменты: не угадывай имена файлов и их содержимое.
Отвечай по-русски, коротко, со ссылками на файлы."""

DEFAULT_TASK = "Где в проекте правило, можно ли менять адрес заказа? Проходят ли тесты?"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task", nargs="?", default=DEFAULT_TASK)
    parser.add_argument("--manual", action="store_true", help="роль модели играет человек")
    parser.add_argument("--max-steps", type=int, default=6)
    opts = parser.parse_args()

    permissions = Permissions(allow_write=False)
    agent_loop(opts.task, INSTRUCTIONS, READ_ONLY,
               executor=lambda name, args: execute_call(name, args, permissions),
               manual=opts.manual, max_steps=opts.max_steps, label="tools")


if __name__ == "__main__":
    main()
