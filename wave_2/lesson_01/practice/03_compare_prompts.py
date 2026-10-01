"""Показ 3. Сравниваем два промпта на одинаковых примерах.

Запуск:  python 03_compare_prompts.py prompts/vague.txt prompts/full.txt --runs 3

Для каждого промпта модель несколько раз пишет функцию parse_duration.
Код сохраняется в папку runs/ — откройте и прочитайте его.
Затем check_duration.py проверяет функцию на 12 примерах.
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()
MODEL = os.environ["OPENAI_MODEL"]
# Цены за 1 млн токенов — со страницы модели в документации OpenAI (необязательно).
PRICE_IN = float(os.environ.get("PRICE_IN_PER_M", 0))
PRICE_OUT = float(os.environ.get("PRICE_OUT_PER_M", 0))


def extract_code(text):
    """Берём первый блок ```python ...```; если блока нет — весь текст."""
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    return match.group(1) if match else text


def run_once(prompt, name, i):
    start = time.perf_counter()
    response = client.responses.create(model=MODEL, input=prompt)
    seconds = time.perf_counter() - start
    code = extract_code(response.output_text or "")

    path = Path("runs") / f"{name}_{i}.py"
    path.write_text(code, encoding="utf-8")

    # Чужой код запускаем в отдельном процессе с ограничением по времени.
    # Перед запуском полезно его прочитать: это код, который написала модель.
    try:
        proc = subprocess.run(
            [sys.executable, str(HERE / "check_duration.py"), str(path)],
            capture_output=True, text=True, timeout=10,
        )
        report = json.loads(proc.stdout or '{"error": "нет вывода"}')
    except subprocess.TimeoutExpired:
        report = {"error": "превышено время"}

    if isinstance(report, dict):  # код не запустился
        passed, critical, total = 0, 0, 12
        failed = [report["error"]]
    else:
        passed = sum(r["ok"] for r in report)
        critical = sum(r["critical"] for r in report)
        total = len(report)
        failed = [f'{r["input"]!r} -> {r["got"]}' for r in report if not r["ok"]]

    usage = response.usage
    cost = (usage.input_tokens * PRICE_IN + usage.output_tokens * PRICE_OUT) / 1e6
    return {
        "prompt": name, "run": i, "passed": passed, "total": total, "critical": critical,
        "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
        "seconds": round(seconds, 1), "cost_usd": round(cost, 5), "failed": "; ".join(failed),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prompts", nargs="+", help="файлы с промптами")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    Path("runs").mkdir(exist_ok=True)
    rows = []
    for prompt_file in args.prompts:
        name = Path(prompt_file).stem
        prompt = Path(prompt_file).read_text(encoding="utf-8")
        for i in range(1, args.runs + 1):
            row = run_once(prompt, name, i)
            rows.append(row)
            print(f'{name:>10} #{i}: {row["passed"]}/{row["total"]} примеров, '
                  f'критических ошибок {row["critical"]}, {row["seconds"]} с')
            if row["failed"]:
                print("            не прошли:", row["failed"][:200])

    print("\nИтог (модель:", MODEL + ")")
    print(f'{"промпт":>10} | {"прошло":>7} | {"запуски с крит.":>15} | {"ср. время":>9} | {"токены вых.":>11} | {"цена":>8}')
    for name in dict.fromkeys(r["prompt"] for r in rows):
        rs = [r for r in rows if r["prompt"] == name]
        passed = sum(r["passed"] for r in rs)
        total = sum(r["total"] for r in rs)
        crit_runs = sum(r["critical"] > 0 for r in rs)
        avg_s = sum(r["seconds"] for r in rs) / len(rs)
        out_tokens = sum(r["output_tokens"] for r in rs) / len(rs)
        cost = sum(r["cost_usd"] for r in rs)
        print(f'{name:>10} | {passed:>3}/{total:<3} | {crit_runs:>7} из {len(rs):<5} | {avg_s:>7.1f} с | {out_tokens:>11.0f} | ${cost:.4f}')

    with open("results.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["model", *rows[0].keys()])
        if f.tell() == 0:
            writer.writeheader()
        for r in rows:
            writer.writerow({"model": MODEL, **r})
    print("\nПодробности: results.csv, код функций: папка runs/")


if __name__ == "__main__":
    main()
