"""Модель OpenAI через Responses API: подключение и один вопрос."""
import os
from dataclasses import dataclass
from pathlib import Path

PRACTICE = Path(__file__).resolve().parents[1]

SUPPORT_RULES = "Ты помощник поддержки магазина «Север». Отвечай по-русски, коротко, в 2–3 предложениях."
WITH_FRAGMENTS = ("Отвечай только по фрагментам из входа. Если ответа в них нет, так и скажи. "
                  "В конце укажи id фрагментов, на которые опираешься.")


@dataclass
class Answer:
    text: str
    input_tokens: int


def connect():
    """Клиент OpenAI и имя модели из .env этой папки."""
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv(PRACTICE / ".env")
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Нет OPENAI_API_KEY. Скопируйте .env.example в .env и впишите ключ.")
    return OpenAI(), os.environ.get("OPENAI_MODEL", "")


def ask(question: str, context: str | None = None) -> Answer:
    """Вопрос модели. context — то, что программа кладёт во вход вместе с вопросом."""
    client, model = connect()
    instructions = SUPPORT_RULES if context is None else f"{SUPPORT_RULES}\n{WITH_FRAGMENTS}"
    text = question if context is None else f"{context}\n\nВопрос: {question}"
    response = client.responses.create(model=model, instructions=instructions, input=text)
    return Answer(response.output_text.strip(), response.usage.input_tokens)
