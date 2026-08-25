"""Шаг 1. Полнотекстовый поиск видит совпадающие слова, а не смысл целиком."""

from __future__ import annotations

from demo_common import check, fulltext_search, headline, paragraph, print_hits, section
from legal_corpus import CONSUMER_EXACT_QUERY, CONSUMER_QUESTION, SEARCH_DOCUMENTS


EXPECTED_ID = "consumer_fz69_article1"


def show_query(label: str, query: str) -> bool:
    section(label)
    paragraph(f"Запрос: {query}")
    hits = fulltext_search(query, SEARCH_DOCUMENTS, top_k=3)
    print()
    print_hits(hits)
    return check(
        f"top-1 - {EXPECTED_ID}",
        hits[0][1]["id"] == EXPECTED_ID,
        f"фактически: {hits[0][1]['id']}",
    )


def run() -> None:
    headline("1. Полнотекстовый поиск: точная формулировка и живой вопрос")
    exact_passed = show_query("А. Язык закона", CONSUMER_EXACT_QUERY)
    natural_passed = show_query("Б. Как спрашивает человек", CONSUMER_QUESTION)

    section("НАБЛЮДЕНИЕ")
    paragraph(
        "Один индекс и один алгоритм. В первом запросе есть слова нормы: "
        "«дополнительная услуга», «письменное согласие», «автоматическая "
        "отметка». Во втором человек пишет: «страховка уже лежала в корзине»."
    )
    check("точный запрос находится", exact_passed)
    check("живой вопрос показывает vocabulary gap", not natural_passed)


if __name__ == "__main__":
    run()
