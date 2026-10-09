"""Практика 1. Три уровня проверки ответа: JSON → схема → факты.

    1. JSON     — текст разбирается как JSON?
    2. Схема    — объект соответствует schema.json: поля, типы, enum, лишних полей нет?
    3. Факты    — то, что написано, правда для нашего проекта? Проверяет программа.

Запуск:
    python check_answer.py answers/*                  — готовые примеры (написаны вручную)
    python check_answer.py runs/answer_*.json         — ответы модели из 02_structured.py
"""
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft7Validator

from tools import PROJECT

HERE = Path(__file__).resolve().parent
SCHEMA = json.loads((HERE / "schema.json").read_text(encoding="utf-8"))


def failing_test_files() -> list[Path]:
    """Тесты, которые падают в исходном проекте. Считаем сами, а не верим ответу."""
    import os
    import subprocess
    proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                          cwd=PROJECT, capture_output=True, text=True, timeout=60,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    names = set(re.findall(r'File "[^"]*?(tests/test_\w+\.py)"', proc.stderr))
    return [PROJECT / n for n in sorted(names)]


def check_facts(answer: dict) -> list[str]:
    """Список нарушений фактов. Пустой список — ничего не нашли (это ещё не доказательство)."""
    problems = []
    path = (PROJECT / answer["file"]).resolve()
    if not path.is_relative_to(PROJECT.resolve()) or not path.is_file():
        return [f"файла {answer['file']} нет в проекте"]
    source = path.read_text(encoding="utf-8")
    if not re.search(rf"^\s*def {re.escape(answer['function'])}\(", source, re.M):
        problems.append(f"в {answer['file']} нет функции {answer['function']}")
    if answer["change"] == "fix_code" and answer["file"].startswith("tests/"):
        problems.append("change=fix_code, но указан файл с тестами")
    failing = failing_test_files()
    if answer["change"] == "no_change" and failing:
        problems.append("change=no_change, но тесты падают")
    if failing and not any(answer["function"] in t.read_text(encoding="utf-8") for t in failing):
        problems.append(f"функция {answer['function']} не встречается в упавших тестах")
    return problems


def check(text: str) -> dict:
    """Проверить текст ответа. Возвращает уровень, на котором ответ остановился, и причину."""
    try:
        answer = json.loads(text)
    except json.JSONDecodeError as e:
        return {"json": False, "schema": None, "facts": None, "why": f"не JSON: {e.msg}"}

    errors = sorted(Draft7Validator(SCHEMA).iter_errors(answer), key=str)
    if errors:
        return {"json": True, "schema": False, "facts": None,
                "why": "; ".join(e.message for e in errors)}

    problems = check_facts(answer)
    if problems:
        return {"json": True, "schema": True, "facts": False, "why": "; ".join(problems)}
    return {"json": True, "schema": True, "facts": True, "why": "нарушений не найдено"}


def mark(value) -> str:
    return {True: "✓", False: "✗", None: "·"}[value]


def main() -> None:
    files = [Path(f) for f in sys.argv[1:] if not f.endswith("README.md")]
    if not files:
        print(__doc__)
        return
    print(f"{'файл':32} JSON схема факты  причина")
    for f in files:
        r = check(f.read_text(encoding="utf-8"))
        print(f"{f.name:32}  {mark(r['json'])}    {mark(r['schema'])}     {mark(r['facts'])}    {r['why']}")
    print("\n✓ прошёл  ✗ остановился здесь  · не проверяли (предыдущий уровень не пройден)")


if __name__ == "__main__":
    main()


d =  {
    "file":"shop/orders.py",
    "function":"can_change_address",
    "change":"fix_code",
    "reason":"Функция разрешает менять адрес при статусе «picking», хотя по ожидаемому поведению после начала сборки это запрещено. Удалите «picking» из списка статусов, для которых возвращается True."
}
