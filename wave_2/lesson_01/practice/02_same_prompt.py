"""Показ 2. Один и тот же промпт, несколько запусков: почему ответы разные.

Запуск:  python 02_same_prompt.py
         python 02_same_prompt.py --prompt "Сколько будет 17 * 23? Ответь только числом."
         python 02_same_prompt.py --effort high        — больше рассуждения
         python 02_same_prompt.py --temperature 0      — если модель принимает параметр
"""
import argparse
import os
import time
from collections import Counter

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()
MODEL = os.environ["OPENAI_MODEL"]

parser = argparse.ArgumentParser()
parser.add_argument("--prompt", default="Придумай название для кофейни рядом с университетом. Ответь только названием.")
parser.add_argument("--runs", type=int, default=5)
parser.add_argument("--effort", help="reasoning effort: например low, medium, high")
parser.add_argument("--temperature", type=float, help="не все модели принимают этот параметр")
args = parser.parse_args()

settings = {}
if args.effort:
    settings["reasoning"] = {"effort": args.effort}
if args.temperature is not None:
    settings["temperature"] = args.temperature

print(f"модель: {MODEL}, настройки: {settings or 'по умолчанию'}")
print(f"промпт: {args.prompt}\n")

answers = []
for i in range(1, args.runs + 1):
    start = time.perf_counter()
    response = client.responses.create(model=MODEL, input=args.prompt, **settings)
    seconds = time.perf_counter() - start
    answer = response.output_text.strip()
    answers.append(answer)
    usage = response.usage
    print(f"#{i}  {seconds:4.1f} с  выход {usage.output_tokens:4} ток. "
          f"(рассуждение {usage.output_tokens_details.reasoning_tokens:4})  →  {answer[:80]}")

counts = Counter(answers)
print(f"\nРазных ответов: {len(counts)} из {args.runs}")
for answer, n in counts.most_common():
    print(f"  {n} × {answer[:80]}")
