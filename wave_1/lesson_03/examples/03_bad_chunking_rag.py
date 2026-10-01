"""Шаг 3. Реальный сбой: закон порезан каждые N символов без overlap."""

from __future__ import annotations

from demo_common import (
    answer_from_context,
    check,
    fixed_size_chunks,
    grade_consumer_answer,
    headline,
    paragraph,
    print_hits,
    print_json,
    section,
    vector_search,
)
from legal_corpus import CONSUMER_QUESTION, RAW_FZ69_DOCUMENT, SOURCE_FZ69


CHUNK_SIZE = 280


def make_bad_chunks() -> list[dict]:
    return [
        {
            "id": f"raw_fz69_chunk_{index}",
            "domain": "consumer",
            "law": "",
            "article": "",
            "effective_from": "",
            "source_url": SOURCE_FZ69,
            "text": text,
        }
        for index, text in enumerate(
            fixed_size_chunks(RAW_FZ69_DOCUMENT, CHUNK_SIZE), start=1
        )
    ]


def run() -> None:
    headline("3. Плохой RAG: fixed-size chunks, overlap=0, top_k=1")
    chunks = make_bad_chunks()

    section("ГРАНИЦЫ ЧАНКОВ")
    for chunk in chunks:
        text = chunk["text"].replace("\n", " ")
        print(chunk["id"])
        paragraph(f"начало: …{text[:54]}…", indent=3)
        paragraph(f"конец:  …{text[-54:]}…", indent=3)

    hits = vector_search(CONSUMER_QUESTION, chunks, top_k=1)
    section("RETRIEVAL")
    print_hits(hits)
    selected = hits[0][1]
    section("КОНТЕКСТ, КОТОРЫЙ УВИДИТ LLM")
    paragraph(selected["text"])

    section("ПОКРЫТИЕ КОНТЕКСТА")
    context_complete = grade_consumer_answer(selected["text"])
    check("один чанк содержит все факты для ответа", context_complete)

    answer = answer_from_context(CONSUMER_QUESTION, [selected])
    section("ОТВЕТ RAG")
    print_json(answer)
    answer_complete = grade_consumer_answer(answer, show=False)
    check("ответ прошёл все критерии", answer_complete)
    check(
        "сбой действительно воспроизведён",
        not context_complete and not answer_complete,
        "причина видна в напечатанном контексте",
    )
    section("ВЫВОД")
    paragraph(
        "Связанные части правила разъехались между чанками: согласие, запрет "
        "автоматической отметки, возврат и дата действия лежат отдельно. "
        "Увеличить prompt недостаточно: надо чинить ingestion."
    )


if __name__ == "__main__":
    run()
