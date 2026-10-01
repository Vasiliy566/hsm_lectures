"""Проверка функции parse_duration на одинаковом наборе примеров.

Запуск вручную:  python check_duration.py runs/full_1.py
Скрипт 03_compare_prompts.py вызывает его сам в отдельном процессе.
"""
import importlib.util
import json
import sys

# (вход, ожидаемый результат). ValueError — функция должна отказаться.
CASES = [
    ("45s", 45),
    ("15m", 900),
    ("2h", 7200),
    ("1h30m", 5400),
    ("1h 30m 15s", 5415),
    ("90m", 5400),
    ("2H", 7200),
    ("", ValueError),
    ("10", ValueError),
    ("1.5h", ValueError),
    ("30m1h", ValueError),
    ("1h1h", ValueError),
]


def check(path):
    spec = importlib.util.spec_from_file_location("candidate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = module.parse_duration

    results = []
    for text, expected in CASES:
        try:
            got = fn(text)
            if expected is ValueError:
                # Критическая ошибка: плохой вход молча превратился в число.
                results.append({"input": text, "ok": False, "critical": True, "got": repr(got)})
            else:
                results.append({"input": text, "ok": got == expected, "critical": False, "got": repr(got)})
        except ValueError as e:
            results.append({"input": text, "ok": expected is ValueError, "critical": False, "got": f"ValueError({e})"})
        except Exception as e:  # упала с другой ошибкой
            results.append({"input": text, "ok": False, "critical": False, "got": f"{type(e).__name__}({e})"})
    return results


if __name__ == "__main__":
    try:
        print(json.dumps(check(sys.argv[1]), ensure_ascii=False))
    except Exception as e:  # код не загрузился или нет функции parse_duration
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
