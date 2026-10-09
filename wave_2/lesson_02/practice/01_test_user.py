"""Формат ответа на простом примере: тестовый пользователь.

Описываем объект Pydantic-моделью. SDK превращает её в JSON Schema, отправляет вместе
с запросом и разбирает ответ обратно в объект Python.

Запуск:
    python 01_test_user.py --show-schema   — какую схему SDK отправит в API (без ключа)
    python 01_test_user.py                 — получить объект TestUser от модели
    python 01_test_user.py --raw           — то же без parse: схема и разбор вручную
    python 01_test_user.py --check '{"name": "Анна", "age": "тридцать", ...}'   — проверить свой JSON (без ключа)
"""
import argparse
import json
from typing import Literal

from pydantic import BaseModel, ValidationError


class TestUser(BaseModel):
    name: str
    age: int
    email: str
    role: Literal["buyer", "seller", "admin"]
    bio: str


PROMPT = "Сгенерируй тестового пользователя для интернет-магазина."


def show_schema() -> None:
    from openai.lib._pydantic import to_strict_json_schema  # то же преобразование, что в SDK

    print("Схема, которую responses.parse отправит в text.format (strict):")
    print(json.dumps(to_strict_json_schema(TestUser), ensure_ascii=False, indent=2))


def check(text: str) -> None:
    print("[модель не вызывалась: проверяем JSON, введённый человеком]")
    try:
        print("✓ объект TestUser:", TestUser.model_validate_json(text))
    except ValidationError as e:
        print("✗ ValidationError:")
        for err in e.errors():
            print(f"   {'.'.join(map(str, err['loc'])) or '(корень)'}: {err['msg']}")


def with_parse() -> None:
    """Обычный способ: SDK делает схему и разбор сам."""
    from common import make_client

    client, model = make_client()
    response = client.responses.parse(model=model, input=PROMPT, text_format=TestUser)
    print(f"[live: {model}] status={response.status}")
    print("текст ответа:", response.output_text)
    user = response.output_parsed
    print(f"объект: {type(user).__name__} → user.name = {user.name!r}, user.age = {user.age}")


def without_parse() -> None:
    """То же руками: так видно, что делает parse."""
    from openai.lib._pydantic import to_strict_json_schema

    from common import make_client

    client, model = make_client()
    response = client.responses.create(
        model=model, input=PROMPT,
        text={"format": {"type": "json_schema", "name": "test_user",
                         "schema": to_strict_json_schema(TestUser), "strict": True}},
    )
    print(f"[live: {model}] status={response.status}")
    data = json.loads(response.output_text)   # текст → dict
    # dict → объект с проверкой типов
    print(f"объект: {data}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show-schema", action="store_true")
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--check", metavar="JSON")
    opts = parser.parse_args()
    if opts.show_schema:
        show_schema()
    elif opts.check:
        check(opts.check)
    elif opts.raw:
        without_parse()
    else:
        with_parse()


if __name__ == "__main__":
    main()
