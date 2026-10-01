"""Заглянуть вперёд (занятие 1.2). Модель просит вызвать функцию, программа её выполняет.

Запуск:  python next_lesson/tool_call.py            — с инструментом
         python next_lesson/tool_call.py --no-tools — тот же вопрос без инструмента
"""
import json
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()
MODEL = os.environ["OPENAI_MODEL"]


# 1. Обычная функция Python. Модель её не видит — видит только описание ниже.
def factorize(n: int) -> list[int]:
    factors, d = [], 2
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1
    if n > 1:
        factors.append(n)
    return factors


# 2. Описание инструмента: имя, назначение и аргументы в формате JSON Schema.
TOOLS = [{
    "type": "function",
    "name": "factorize",
    "description": "Раскладывает число на простые множители.",
    "parameters": {
        "type": "object",
        "properties": {"n": {"type": "integer", "description": "целое число больше 1"}},
        "required": ["n"],
    },
}]

history = [{"role": "user", "content": "Разложи на простые множители число 34324329."}]

if "--no-tools" in sys.argv:
    response = client.responses.create(model=MODEL, input=history)
    print(response.output_text)
    print("\nПроверка программой:", factorize(34324329))
    sys.exit()

# 3. Первый запрос: модель видит вопрос и список инструментов.
response = client.responses.create(model=MODEL, input=history, tools=TOOLS)
calls = [item for item in response.output if item.type == "function_call"]

if not calls:
    print("Модель ответила без инструмента:\n", response.output_text)
    sys.exit()

# 4. Модель вернула не ответ, а просьбу вызвать функцию с аргументами.
#    Сохраняем её ответ в истории, чтобы на следующем шаге модель видела свою просьбу.
history += response.output
for call in calls:
    args = json.loads(call.arguments)
    print(f"модель просит: {call.name}({args})")
    result = factorize(**args)  # выполняет наша программа, а не модель
    print("программа вернула:", result)
    history.append({"type": "function_call_output", "call_id": call.call_id, "output": json.dumps(result)})

# 5. Второй запрос: та же история + результат. Теперь модель пишет ответ.
response = client.responses.create(model=MODEL, input=history, tools=TOOLS)
print("\nответ:", response.output_text)
