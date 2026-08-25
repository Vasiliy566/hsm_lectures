"""Общий Gemini-клиент для примеров занятия 03."""

from google import genai


GENERATIVE_MODEL = "gemini-3.5-flash"
EMBEDDING_MODEL = "gemini-embedding-2"


def get_client() -> genai.Client:
    """Создаёт клиент только для примеров, которым нужен Gemini API."""

    return genai.Client()
