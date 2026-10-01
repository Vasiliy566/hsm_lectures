"""Показ 1. Первый запрос к модели OpenAI из Python (Responses API).

Запуск:  python 01_first_call.py
         python 01_first_call.py "Свой вопрос"
"""
import json
import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # читаем OPENAI_API_KEY и OPENAI_MODEL из файла .env
client = OpenAI()  # ключ SDK берёт из переменной окружения OPENAI_API_KEY
MODEL = os.environ["OPENAI_MODEL"]

question = sys.argv[1] if len(sys.argv) > 1 else "Что такое токен? Ответь в двух предложениях."
instructions = "Ты отвечаешь кратко и по-русски."  # правила

start = time.perf_counter()
response = client.responses.create(
    model=MODEL,
    instructions=instructions,  # правила: то же, что сообщение system
    input=question,             # задача
    # Настройки генерации (их влияние — в 02_same_prompt.py):
    # reasoning={"effort": "low"},
    # max_output_tokens=2000,
)
seconds = time.perf_counter() - start

answer = response.output_text  # весь текст ответа одной строкой
usage = response.usage
print(answer)
print("---")
print("модель:  ", response.model)
print("статус:  ", response.status)  # incomplete — ответ оборвался (см. incomplete_details)
print("токены:   вход", usage.input_tokens, "| выход", usage.output_tokens,
      "| из них на рассуждение", usage.output_tokens_details.reasoning_tokens)
print(f"время:    {seconds:.1f} с")

# Сохраняем ответ вместе с условиями запуска: пригодится для сравнения.
record = {
    "model": response.model,
    "instructions": instructions,
    "input": question,
    "answer": answer,
    "input_tokens": usage.input_tokens,
    "output_tokens": usage.output_tokens,
    "seconds": round(seconds, 2),
}
with open("answers.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(record, ensure_ascii=False) + "\n")
