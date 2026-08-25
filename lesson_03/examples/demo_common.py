"""Общие функции, чтобы примеры отличались идеей, а не служебным кодом."""

from __future__ import annotations

import json
import math
import re
import textwrap
from collections import Counter
from typing import Iterable

import numpy as np
from google.genai import types

from gemini_client import EMBEDDING_MODEL, GENERATIVE_MODEL, get_client


TOKEN_RE = re.compile(r"[0-9a-zа-яё]+", re.IGNORECASE)
STOP_WORDS = {
    "без", "бы", "в", "во", "вот", "где", "да", "для", "до", "его",
    "если", "же", "за", "и", "из", "или", "как", "ли", "мне", "на",
    "не", "но", "о", "об", "от", "по", "при", "с", "со", "то", "у",
    "уже", "что", "эта", "это", "я",
}
OUTPUT_WIDTH = 96


def headline(title: str) -> None:
    print(f"\n{'=' * OUTPUT_WIDTH}\n{title}\n{'=' * OUTPUT_WIDTH}")


def section(title: str) -> None:
    """Отделяет смысловые части вывода без тяжёлых рамок."""

    print(f"\n{title}\n{'-' * min(len(title), OUTPUT_WIDTH)}")


def paragraph(text: str, *, indent: int = 0) -> None:
    """Нормализует случайные переносы и не выпускает текст за ширину окна."""

    normalized = " ".join(str(text).split())
    padding = " " * indent
    print(
        textwrap.fill(
            normalized,
            width=OUTPUT_WIDTH,
            initial_indent=padding,
            subsequent_indent=padding,
        )
    )


def print_question(question: str) -> None:
    section("ВОПРОС")
    paragraph(question)


def print_json(value: object) -> None:
    """Печатает JSON-ответ как читаемые поля с переносами."""

    def scalar_text(item: object) -> str:
        if isinstance(item, str):
            return item
        return json.dumps(item, ensure_ascii=False)

    def labeled(label: str, item: object, indent: int) -> None:
        prefix = f"{' ' * indent}{label}"
        continuation = " " * len(prefix)
        print(
            textwrap.fill(
                " ".join(scalar_text(item).split()),
                width=OUTPUT_WIDTH,
                initial_indent=prefix,
                subsequent_indent=continuation,
            )
        )

    def render(item: object, indent: int = 0) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                if isinstance(nested, (dict, list)):
                    print(f"{' ' * indent}{key}:")
                    render(nested, indent + 2)
                else:
                    labeled(f"{key}: ", nested, indent)
            return
        if isinstance(item, list):
            for index, nested in enumerate(item, start=1):
                if isinstance(nested, (dict, list)):
                    print(f"{' ' * indent}{index}.")
                    render(nested, indent + 3)
                else:
                    labeled(f"{index}. ", nested, indent)
            return
        paragraph(scalar_text(item), indent=indent)

    render(value)


def check(label: str, passed: bool, details: str = "") -> bool:
    print(f"[{'PASS' if passed else 'FAIL'}] {label}")
    if details and not passed:
        paragraph(f"Детали: {details}", indent=4)
    return passed


def print_result(passed: bool, expected: str) -> None:
    section(f"ИТОГ: {'PASS' if passed else 'FAIL'}")
    paragraph(f"Ожидание: {expected}")


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in TOKEN_RE.findall(text.lower().replace("ё", "е"))
        if len(token) > 2 and token not in STOP_WORDS
    ]


def document_text(doc: dict) -> str:
    return " | ".join(
        str(doc.get(field, ""))
        for field in ("law", "article", "effective_from", "text")
    )


def fulltext_search(query: str, docs: list[dict], top_k: int = 3) -> list[tuple[float, dict]]:
    """Минимальный lexical search: TF-IDF по точным словоформам.

    Это компактная модель полнотекстового поиска для занятия, а не замена
    PostgreSQL FTS/Elasticsearch: морфология здесь намеренно не подключена.
    """

    query_tokens = tokenize(query)
    document_tokens = [tokenize(document_text(doc)) for doc in docs]
    document_frequency = Counter(
        token for tokens in document_tokens for token in set(tokens)
    )
    total = len(docs)
    scores: list[tuple[float, dict]] = []

    for doc, tokens in zip(docs, document_tokens, strict=True):
        counts = Counter(tokens)
        score = 0.0
        for token in query_tokens:
            if counts[token]:
                inverse_document_frequency = math.log(
                    (total + 1) / (document_frequency[token] + 1)
                ) + 1
                score += (1 + math.log(counts[token])) * inverse_document_frequency
        scores.append((score, doc))

    return sorted(scores, key=lambda item: item[0], reverse=True)[:top_k]


def embed(texts: list[str], *, task_type: str) -> np.ndarray:
    # Для gemini-embedding-2 список строк считается частями одного Content.
    # Явные Content-объекты дают отдельный embedding для каждого документа.
    contents = [
        types.UserContent(parts=[types.Part(text=text)])
        for text in texts
    ]
    response = get_client().models.embed_content(
        model=EMBEDDING_MODEL,
        contents=contents,
        config=types.EmbedContentConfig(task_type=task_type),
    )
    matrix = np.asarray(
        [embedding.values for embedding in response.embeddings], dtype=np.float32
    )
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.maximum(norms, 1e-12)


def vector_search(query: str, docs: list[dict], top_k: int = 3) -> list[tuple[float, dict]]:
    vectors = embed(
        [document_text(doc) for doc in docs], task_type="RETRIEVAL_DOCUMENT"
    )
    query_vector = embed([query], task_type="RETRIEVAL_QUERY")[0]
    scores = vectors @ query_vector
    indices = np.argsort(scores)[::-1][:top_k]
    return [(float(scores[index]), docs[index]) for index in indices]


def print_hits(hits: Iterable[tuple[float, dict]]) -> None:
    for rank, (score, doc) in enumerate(hits, start=1):
        print(f"{rank}. {doc['id']}")
        print(f"   score: {score:.3f}")
        if doc.get("law"):
            paragraph(f"источник: {doc['law']}", indent=3)
        if doc.get("article"):
            paragraph(f"фрагмент: {doc['article']}", indent=3)
        if doc.get("effective_from"):
            print(f"   действует с: {doc['effective_from']}")


LEGAL_RESPONSE_SHAPE = {
    "answer": "краткий вывод или 'недостаточно данных'",
    "law": "название и номер закона или null",
    "article": "пункт и статья или null",
    "effective_from": "YYYY-MM-DD или null",
    "conditions": ["условие 1", "условие 2"],
    "source_is_known": True,
}


def generate_json(prompt: str) -> dict:
    response = get_client().models.generate_content(
        model=GENERATIVE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        ),
    )
    try:
        return json.loads(response.text)
    except (TypeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Модель вернула не JSON: {response.text!r}") from error


def ask_plain_llm(question: str) -> dict:
    return generate_json(
        "Ответьте на юридический вопрос только по памяти модели, без поиска и "
        "инструментов. Не выдумывайте реквизиты; неизвестные поля заполните null. "
        f"Формат ответа: {json.dumps(LEGAL_RESPONSE_SHAPE, ensure_ascii=False)}\n\n"
        f"Вопрос: {question}"
    )


def answer_from_context(question: str, docs: list[dict]) -> dict:
    context = "\n\n".join(
        f"[ФРАГМЕНТ {index}]\n{document_text(doc)}\nИсточник: {doc.get('source_url')}"
        for index, doc in enumerate(docs, start=1)
    )
    return generate_json(
        "Ответьте только по приведенному контексту. Запрещено дополнять ответ "
        "знаниями модели. Если контекст не доказывает реквизит или условие, "
        "запишите null и прямо скажите, чего не хватает. "
        f"Формат ответа: {json.dumps(LEGAL_RESPONSE_SHAPE, ensure_ascii=False)}\n\n"
        f"КОНТЕКСТ:\n{context}\n\nВОПРОС:\n{question}"
    )


def _flat_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False).lower().replace("ё", "е")


def consumer_checks(value: object) -> dict[str, bool]:
    text = _flat_text(value)
    return {
        "ФЗ № 69-ФЗ от 07.04.2025": bool(
            re.search(r"(?:№|n)?\s*69\s*[-‑\u2013]?\s*фз", text)
            and ("07.04.2025" in text or "7 апреля 2025" in text)
        ),
        "п. 3.1 ст. 16 Закона о защите прав потребителей": (
            "16" in text and ("3.1" in text or "3 1" in text)
            and ("потребител" in text or "2300-1" in text)
        ),
        "действует с 01.09.2025": (
            "2025-09-01" in text
            or "01.09.2025" in text
            or "1 сентября 2025" in text
        ),
        "дополнительная услуга за отдельную плату": (
            "дополнитель" in text
            and ("услуг" in text or "товар" in text or "работ" in text)
            and ("плат" in text or "деньг" in text)
        ),
        "нужно письменное согласие": (
            "соглас" in text and "письмен" in text
        ),
        "автоматическая отметка запрещена": (
            ("автомат" in text or "заранее" in text or "предустанов" in text)
            and ("отмет" in text or "галоч" in text or "соглас" in text)
        ),
        "можно отказаться от оплаты или потребовать возврат": (
            ("отказ" in text or "не оплач" in text)
            and ("возврат" in text or "вернуть" in text)
        ),
        "возврат в течение трех дней после требования": (
            ("трех дн" in text or "три дн" in text or "3 дн" in text)
            and ("требован" in text or "заявлен" in text)
        ),
    }


def grade_consumer_answer(value: object, *, show: bool = True) -> bool:
    results = consumer_checks(value)
    if show:
        for label, passed in results.items():
            check(label, passed)
    return all(results.values())


def fixed_size_chunks(text: str, chunk_size: int) -> list[str]:
    """Наивное разбиение: ровно N символов, без знания структуры документа."""

    return [text[start : start + chunk_size] for start in range(0, len(text), chunk_size)]
