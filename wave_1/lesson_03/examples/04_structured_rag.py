"""Шаг 4. Структурный чанк хранит норму вместе с родителем и версией."""

from __future__ import annotations

from demo_common import (
    answer_from_context,
    check,
    grade_consumer_answer,
    headline,
    paragraph,
    print_hits,
    print_json,
    section,
    vector_search,
)
from legal_corpus import (
    CONSUMER_QUESTION,
    SEARCH_DOCUMENTS,
    STRUCTURED_CONSUMER_CHUNKS,
)


def run() -> None:
    headline("4. Исправленный RAG: юридическая структура + parent context")
    distractors = [
        doc for doc in SEARCH_DOCUMENTS
        if doc["id"] not in {"consumer_fz69_article1", "consumer_fz69_article2"}
    ]
    index = [*STRUCTURED_CONSUMER_CHUNKS, *distractors]
    hits = vector_search(CONSUMER_QUESTION, index, top_k=1)

    section("RETRIEVAL")
    print_hits(hits)
    selected = hits[0][1]
    section("МЕТАДАННЫЕ ЧАНКА")
    print_json({key: value for key, value in selected.items() if key != "text"})
    section("КОНТЕКСТ")
    paragraph(selected["text"])

    context_complete = grade_consumer_answer(selected)
    check("контекст покрывает весь контракт ответа", context_complete)

    answer = answer_from_context(CONSUMER_QUESTION, [selected])
    section("ОТВЕТ RAG")
    print_json(answer)
    answer_complete = grade_consumer_answer(answer)
    check("ответ прошёл все критерии", answer_complete)
    section("ВЫВОД")
    paragraph(
        "Исправление не в магическом chunk_size: ingestion собрал статью 16 "
        "целиком и прикрепил номер закона, дату действия и ссылку на "
        "официальный источник."
    )


if __name__ == "__main__":
    run()
