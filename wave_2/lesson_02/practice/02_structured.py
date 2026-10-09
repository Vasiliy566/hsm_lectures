"""Практика 1, часть 2. Просим у модели один объект по схеме и проверяем его.

Вопрос: в каком ОДНОМ файле и какой функции исправить ошибку, из-за которой падают тесты?
Контекст (файлы и вывод тестов) собирает программа — инструментов здесь нет,
чтобы смотреть только на формат ответа.

Запуск:
    python 02_structured.py                    — со схемой (structured output, strict)
    python 02_structured.py --no-schema        — формат описан только словами в промпте
    python 02_structured.py --runs 3           — несколько запусков и итог по уровням
    python 02_structured.py --max-output-tokens 16   — что будет, если ответ оборвётся
    python 02_structured.py --manual           — без API: ответ вводите вы, проверка та же
Каждый ответ модели сохраняется в runs/answer_*.txt — его можно проверить check_answer.py.
"""
import argparse
import time

from check_answer import SCHEMA, check, mark
from common import RUNS, ModelStop, check_finished, make_client
from tools import PROJECT, ensure_sandbox, run_tests

INSTRUCTIONS = """Ты анализируешь небольшой проект на Python и находишь место ошибки.
Ответ — один объект: файл, функция, вид изменения и короткая причина."""

FORMAT_IN_WORDS = """Ответь JSON-объектом с полями file (один путь), function, change
(одно из: fix_code, fix_test, no_change) и reason."""


def build_context() -> str:
    """Программа сама собирает факты: список файлов, их содержимое и вывод тестов."""
    ensure_sandbox()
    parts = ["Файлы проекта:"]
    for path in sorted(PROJECT.rglob("*.py")):
        if "__pycache__" not in path.parts:
            rel = path.relative_to(PROJECT)
            parts.append(f"=== FILE: {rel} ===\n{path.read_text(encoding='utf-8')}")
    tests = run_tests()
    parts.append(f"=== ВЫВОД ТЕСТОВ ===\n{tests['output_tail']}")
    parts.append("Вопрос: в каком одном файле и какой функции нужно исправить ошибку?")
    return "\n\n".join(parts)


def ask_model(client, model: str, context: str, use_schema: bool,
              max_output_tokens: int | None) -> str:
    kwargs = {"model": model, "instructions": INSTRUCTIONS, "input": context}
    if use_schema:
        # Схема уходит в API отдельно от промпта. strict: ответ обязан ей соответствовать.
        kwargs["text"] = {"format":
                              {"type": "json_schema",
                               "name": "fix_target",
                               "schema": SCHEMA,
                               "strict": True}
                          }
    else:
        kwargs["input"] = context + "\n\n" + FORMAT_IN_WORDS
    if max_output_tokens:
        kwargs["max_output_tokens"] = max_output_tokens
    response = client.responses.create(**kwargs)
    check_finished(response)  # incomplete или отказ → исключение, а не «пустой JSON»
    return response.output_text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-schema", action="store_true")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--max-output-tokens", type=int)
    parser.add_argument("--manual", action="store_true")
    opts = parser.parse_args()

    if opts.manual:
        print("[ручной режим: модель не вызывалась] Вставьте ответ одной строкой:")
        r = check(input("> "))
        print(f"JSON {mark(r['json'])}  схема {mark(r['schema'])}  факты {mark(r['facts'])}  — {r['why']}")
        return

    client, model = make_client()
    use_schema = not opts.no_schema
    label = "schema" if use_schema else "noschema"
    print(f"[live: {model}] режим: {'схема strict' if use_schema else 'формат только в промпте'}")
    context = build_context()
    RUNS.mkdir(exist_ok=True)
    totals = {"json": 0, "schema": 0, "facts": 0, "stopped": 0}

    for i in range(1, opts.runs + 1):
        print("─" * 72)
        try:
            text = ask_model(client, model, context, use_schema, opts.max_output_tokens)
        except ModelStop as stop:
            print(f"запуск {i}: ✗ {stop} — разбирать нечего, программа не выдумывает ответ")
            totals["stopped"] += 1
            continue
        path = RUNS / f"answer_{label}_{time.strftime('%H%M%S')}_{i}.txt"
        path.write_text(text, encoding="utf-8")
        r = check(text)
        for level in ("json", "schema", "facts"):
            totals[level] += bool(r[level])
        print(f"запуск {i}: {text}")
        print(f"  JSON {mark(r['json'])}  схема {mark(r['schema'])}  факты {mark(r['facts'])}  — {r['why']}")
        print(f"  сохранено: {path.relative_to(path.parent.parent)}")

    print("─" * 72)
    print(f"Итого из {opts.runs}: JSON {totals['json']}, схема {totals['schema']}, "
          f"факты {totals['facts']}, остановлено {totals['stopped']}")


if __name__ == "__main__":
    main()
