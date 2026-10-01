"""Показ 1б. История переписки — это список сообщений, который мы отправляем заново.

Запуск:  python 01b_chat_history.py
Пустая строка — выход. Следите, как растёт число входных токенов.
"""
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()
MODEL = os.environ["OPENAI_MODEL"]

history = []  # вся переписка: реплики пользователя и ответы модели

while True:
    text = input("\nвы> ").strip()
    if not text:
        break
    history.append({"role": "user", "content": text})

    response = client.responses.create(
        model=MODEL,
        instructions="Ты отвечаешь кратко и по-русски.",
        input=history,  # отправляем всю историю, а не только последнюю реплику
    )
    answer = response.output_text
    print("модель>", answer)
    print(f"[сообщений отправлено: {len(history)}, токенов на входе: {response.usage.input_tokens}]")

    # Без этой строки модель «забудет» свой ответ: историю ведёт наша программа.
    # (У Responses API есть и другой способ — previous_response_id; здесь ведём историю сами.)
    history.append({"role": "assistant", "content": answer})
