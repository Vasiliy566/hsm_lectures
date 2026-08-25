"""Шаг 2. Embeddings помогают найти норму при несовпадающих формулировках."""

from __future__ import annotations

from demo_common import (
    check,
    headline,
    paragraph,
    print_hits,
    print_question,
    section,
    vector_search,
)
from legal_corpus import CONSUMER_QUESTION, SEARCH_DOCUMENTS


EXPECTED_ID = "consumer_fz69_article1"


def run() -> None:
    headline("2. Поиск по embeddings: тот же живой вопрос")
    print_question(CONSUMER_QUESTION)

    hits = vector_search(CONSUMER_QUESTION, SEARCH_DOCUMENTS, top_k=3)
    section("БЛИЖАЙШИЕ ФРАГМЕНТЫ")
    print_hits(hits)
    check(
        "top-1 - запрет автоматической отметки",
        hits[0][1]["id"] == EXPECTED_ID,
        f"фактически: {hits[0][1]['id']}",
    )
    section("ЧТО ПРОИЗОШЛО")
    paragraph(
        "Embedding превратил запрос и документы в числовые векторы. "
        "Близость получилась не из точного совпадения слов «страховка» и "
        "«дополнительная услуга», а из похожего контекста. Но найденный "
        "фрагмент ещё не является готовым ответом."
    )


if __name__ == "__main__":
    run()
