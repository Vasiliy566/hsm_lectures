# %% [markdown]
# # Python API workshop: LLM без магии
#
# Файл разбит на ячейки `# %%`. Откройте его в PyCharm или VS Code и запускайте
# по одной секции. Не запускайте весь файл целиком: это сделает много API-вызовов.
#
# Главные правила:
#
# - ключ никогда не записываем в код;
# - один вызов — одна понятная цель;
# - `response.output` может содержать не только текст;
# - строгая JSON-схема гарантирует форму, но не истинность значений;
# - долгий ответ лучше стримить;
# - tool call — запрос модели, а не разрешение выполнить действие.

# %%
from __future__ import annotations

import asyncio
import json
import os
from typing import Literal

import openai
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel, Field

load_dotenv()


def client_settings() -> dict:
    """Настройки для официального API, корпоративного шлюза или совместимого endpoint."""
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    api_key = (
        os.getenv("LLM_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ("local-not-a-secret" if base_url else None)
    )

    if not api_key:
        raise RuntimeError(
            "Задайте LLM_API_KEY или OPENAI_API_KEY в локальном .env. "
            "Не вставляйте ключ в ноутбук."
        )

    settings = {
        "api_key": api_key,
        "timeout": 120.0,
        "max_retries": 2,
    }
    if base_url:
        settings["base_url"] = base_url
    return settings


client = OpenAI(**client_settings())
MODEL = os.getenv("LLM_MODEL", "gpt-5.6")

print("model:", MODEL)
print("base_url:", os.getenv("LLM_BASE_URL") or "official OpenAI endpoint")

# %% [markdown]
# ## 1. Минимальный запрос через Responses API
#
# `developer` задаёт постоянное поведение приложения, `user` — конкретную задачу.

# %%
response = client.responses.create(
    model=MODEL,
    input=[
        {
            "role": "developer",
            "content": (
                "Отвечай по-русски. Сначала дай вывод, затем максимум три пункта. "
                "Не добавляй факты, которых нет во входе."
            ),
        },
        {
            "role": "user",
            "content": (
                "Из заметок встречи известно: решили добавить статус «Сохранено». "
                "Мария готовит текст и макет. Срок релиза не утверждён. "
                "Сформулируй краткий итог."
            ),
        },
    ],
)

print(response.output_text)

# %% [markdown]
# ## 2. Почему нельзя всегда брать `output[0].content[0].text`
#
# `response.output` может содержать сообщения, reasoning items, tool calls и другие
# элементы. Для обычного текста используйте агрегатор `output_text`. Для диагностики
# смотрите тип каждого элемента.

# %%
print("id:", response.id)
print("status:", response.status)
print("text:", response.output_text)
print("usage:", response.usage)

for index, item in enumerate(response.output):
    print(f"\nOUTPUT ITEM {index}: type={item.type}")
    print(item.model_dump_json(indent=2, exclude_none=True))

if response.status == "incomplete":
    print("incomplete_details:", response.incomplete_details)

# %% [markdown]
# ## 3. Если провайдер поддерживает только Chat Completions
#
# Некоторые корпоративные или OpenAI-compatible endpoints ещё не реализуют Responses
# API. Тогда базовый вызов выглядит так. Конкретную совместимость всегда проверяйте у
# своего провайдера.

# %%
chat_response = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": "Отвечай по-русски и кратко."},
        {"role": "user", "content": "Чем API отличается от интерфейса чата?"},
    ],
)

print(chat_response.choices[0].message.content)

# %% [markdown]
# ## 4. Длинный ответ: streaming
#
# Без streaming пользователь ждёт, пока будет создан весь ответ. Со streaming первые
# фрагменты можно показывать сразу. Нас интересуют события
# `response.output_text.delta`, `response.completed` и `error`.

# %%
stream = client.responses.create(
    model=MODEL,
    input=(
        "Составь компактный чек-лист ревью промпта из 10 пунктов. "
        "Для каждого пункта дай короткий пример."
    ),
    stream=True,
)

completed_response = None

for event in stream:
    if event.type == "response.output_text.delta":
        print(event.delta, end="", flush=True)
    elif event.type == "response.completed":
        completed_response = event.response
    elif event.type == "error":
        print("\nSTREAM ERROR:", event)

print("\n\ncompleted:", completed_response is not None)

# %% [markdown]
# ## 5. Timeout, лимит ответа и повторные попытки
#
# - `timeout` ограничивает ожидание на стороне клиента.
# - `max_output_tokens` ограничивает генерацию, но слишком малое значение может дать
#   `status="incomplete"`.
# - SDK повторяет часть временных ошибок автоматически. Не делайте бесконечный retry.

# %%
long_response = client.with_options(timeout=180.0).responses.create(
    model=MODEL,
    input="Объясни на одном практическом примере, как устроен eval-набор для LLM-кодера.",
    max_output_tokens=1200,
)

print("status:", long_response.status)
print("usage:", long_response.usage)
print(long_response.output_text)

if long_response.status == "incomplete":
    print("Почему ответ не завершён:", long_response.incomplete_details)

# %% [markdown]
# ## 6. Structured Outputs: Pydantic вместо ручного парсинга
#
# Схема гарантирует наличие полей и их типы. Она не доказывает, что содержание полей
# верно — это проверяется по источнику и бизнес-правилам.

# %%
class ActionItem(BaseModel):
    owner: str | None = Field(description="Ответственный или None")
    action: str
    deadline: str | None = Field(description="Срок из текста или None")
    status: Literal["confirmed", "uncertain"]


class MeetingResult(BaseModel):
    decisions: list[str]
    actions: list[ActionItem]
    open_questions: list[str]


meeting_notes = """
Решили добавить статус «Сохранено» рядом с кнопкой.
Мария подготовит текст и состояния макета к четвергу.
Игорь оценит фронтенд после получения макета.
Релиз хотят включить в 2.8, но дата версии не утверждена.
"""

parsed_response = client.responses.parse(
    model=MODEL,
    input=[
        {
            "role": "developer",
            "content": (
                "Извлекай только явно указанные решения и действия. "
                "Не придумывай сроки и ответственных."
            ),
        },
        {"role": "user", "content": meeting_notes},
    ],
    text_format=MeetingResult,
)

meeting_result = parsed_response.output_parsed
print(meeting_result.model_dump_json(indent=2))

# Бизнес-проверка поверх схемы:
assert all(item.owner is not None for item in meeting_result.actions)

# %% [markdown]
# ## 7. Несколько ходов: `previous_response_id`
#
# Этот вариант удобен для последовательной работы. Он создаёт серверное состояние;
# для чувствительных сценариев отдельно изучите настройки хранения и вариант
# `store=False` с ручной передачей истории.

# %%
first = client.responses.create(
    model=MODEL,
    input="Предложи три критерия качества ответа LLM-кодера.",
)

second = client.responses.create(
    model=MODEL,
    previous_response_id=first.id,
    input="Теперь преврати эти критерии в короткий чек-лист перед merge.",
)

print(second.output_text)

# %% [markdown]
# ## 8. Обработка ошибок
#
# Полезно различать: сеть, timeout, rate limit и ответ API с ошибочным статусом.
# В production логируйте `request_id`, но никогда не логируйте API-ключ и секретные
# данные из промпта.

# %%
try:
    safe_response = client.responses.create(
        model=MODEL,
        input="Ответь одним словом: работает?",
    )
    print(safe_response.output_text)

except openai.APITimeoutError as exc:
    print("Timeout. Можно повторить ограниченное число раз:", exc)

except openai.APIConnectionError as exc:
    print("Не удалось соединиться с endpoint:", exc)

except openai.RateLimitError as exc:
    print("Лимит запросов или бюджета:", exc)

except openai.APIStatusError as exc:
    print("API вернул ошибку:", exc.status_code)
    print("request_id:", exc.request_id)
    print("body:", exc.body)

# %% [markdown]
# ## 9. Параллельные независимые запросы через AsyncOpenAI
#
# Параллелить можно независимые задачи. Не запускайте сотни запросов без semaphore:
# получите rate limit и неконтролируемые расходы.

# %%
async_client = AsyncOpenAI(**client_settings())


async def classify_ticket(ticket: str, semaphore: asyncio.Semaphore) -> str:
    async with semaphore:
        result = await async_client.responses.create(
            model=MODEL,
            input=[
                {
                    "role": "developer",
                    "content": "Классифицируй как bug, feature или question. Верни одно слово.",
                },
                {"role": "user", "content": ticket},
            ],
        )
        return result.output_text.strip()


async def run_batch() -> None:
    tickets = [
        "После сохранения изменения исчезают.",
        "Добавьте массовую выгрузку счетов.",
        "Где изменить email уведомлений?",
    ]
    semaphore = asyncio.Semaphore(3)
    labels = await asyncio.gather(
        *(classify_ticket(ticket, semaphore) for ticket in tickets)
    )
    print(list(zip(tickets, labels, strict=True)))


try:
    running_loop = asyncio.get_running_loop()
except RuntimeError:
    asyncio.run(run_batch())
else:
    # Jupyter/PyCharm Scientific уже держит event loop запущенным.
    batch_task = running_loop.create_task(run_batch())

# %% [markdown]
# ## 10. Tool calling: модель просит, приложение решает
#
# Инструмент ниже только читает локальный словарь. Для опасных действий нужен отдельный
# контроль прав и подтверждение пользователя на стороне приложения.

# %%
COURSE_TOPICS = {
    1: "Промптинг и API",
    2: "Structured Outputs, tools и агенты",
    3: "RAG",
    4: "Архитектуры агентов",
}


def get_course_topic(lesson_number: int) -> str:
    return COURSE_TOPICS.get(lesson_number, "Урок не найден")


tools = [
    {
        "type": "function",
        "name": "get_course_topic",
        "description": "Вернуть тему урока курса по его номеру.",
        "parameters": {
            "type": "object",
            "properties": {
                "lesson_number": {
                    "type": "integer",
                    "description": "Номер урока от 1 до 4",
                }
            },
            "required": ["lesson_number"],
            "additionalProperties": False,
        },
        "strict": True,
    }
]

tool_input = [{"role": "user", "content": "Какая тема у третьего урока?"}]

tool_response = client.responses.create(
    model=MODEL,
    tools=tools,
    input=tool_input,
)

# Важно сохранить ВСЕ output items, включая reasoning items.
tool_input += tool_response.output

for item in tool_response.output:
    if item.type != "function_call":
        continue

    if item.name == "get_course_topic":
        arguments = json.loads(item.arguments)
        output = get_course_topic(arguments["lesson_number"])
        tool_input.append(
            {
                "type": "function_call_output",
                "call_id": item.call_id,
                "output": output,
            }
        )

final_tool_response = client.responses.create(
    model=MODEL,
    tools=tools,
    instructions="Ответь по-русски одним предложением и используй результат инструмента.",
    input=tool_input,
)

print(final_tool_response.output_text)

# %% [markdown]
# ## 11. Минимальное логирование для учебного eval
#
# Сохраняем вход, ответ, модель, токены и статус. В реальном проекте удаляем или
# маскируем персональные данные и секреты.

# %%
def response_record(prompt: str, result) -> dict:
    usage = result.usage
    return {
        "model": MODEL,
        "prompt": prompt,
        "response_id": result.id,
        "status": result.status,
        "output_text": result.output_text,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


eval_prompt = "Назови один проверяемый критерий готовности для задачи рефакторинга."
eval_response = client.responses.create(model=MODEL, input=eval_prompt)
record = response_record(eval_prompt, eval_response)
print(json.dumps(record, ensure_ascii=False, indent=2))

# %% [markdown]
# ## Официальные источники
#
# - Text generation / Responses API:
#   https://developers.openai.com/api/docs/guides/text
# - Streaming:
#   https://developers.openai.com/api/docs/guides/streaming-responses
# - Structured Outputs:
#   https://developers.openai.com/api/docs/guides/structured-outputs
# - Conversation state:
#   https://developers.openai.com/api/docs/guides/conversation-state
# - Function calling:
#   https://developers.openai.com/api/docs/guides/function-calling
# - Current model guide checked on 2026-08-03:
#   https://developers.openai.com/api/docs/guides/latest-model.md
