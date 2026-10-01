"""Шаг 5. Один вопрос требует двух RAG-индексов и multi-label routing."""

from __future__ import annotations

import json

from demo_common import (
    check,
    generate_json,
    headline,
    paragraph,
    print_hits,
    print_json,
    print_question,
    section,
    vector_search,
)
from legal_corpus import (
    MULTI_DOMAIN_QUESTION,
    SEARCH_DOCUMENTS,
    STRUCTURED_CONSUMER_CHUNKS,
)


EXPECTED_BY_DOMAIN = {
    "consumer": "consumer_16_after_69_complete_rule",
    "labor": "labor_fz306_article178",
}
ALLOWED_DOMAINS = ["consumer", "labor"]


def route(question: str) -> list[str]:
    payload = generate_json(
        "Вы маршрутизатор юридического корпуса. Верните все основные разделы, "
        "без которых нельзя ответить на каждую часть вопроса. Для московской "
        "организации используйте labor, а не северную специальную норму. "
        f"Допустимые разделы: {ALLOWED_DOMAINS}. "
        "Формат: {\"domains\": [\"domain\", ...]}.\n\n"
        f"Вопрос: {question}"
    )
    domains = payload.get("domains", [])
    return [domain for domain in domains if domain in ALLOWED_DOMAINS]


def run() -> None:
    headline("5. Multi-RAG: страховка + сокращение в одном вопросе")
    print_question(MULTI_DOMAIN_QUESTION)

    global_hits = vector_search(MULTI_DOMAIN_QUESTION, SEARCH_DOCUMENTS, top_k=1)
    section("НАИВНЫЙ ГЛОБАЛЬНЫЙ RETRIEVAL, top_k=1")
    print_hits(global_hits)
    global_ids = {doc["id"] for _, doc in global_hits}
    global_complete = set(EXPECTED_BY_DOMAIN.values()).issubset(global_ids)
    check(
        "один глобальный чанк покрыл два независимых закона",
        global_complete,
        "при top_k=1 это невозможно",
    )

    domains = route(MULTI_DOMAIN_QUESTION)
    section("ROUTER")
    print("Выбранные области:", ", ".join(domains) or "нет")
    check(
        "router выбрал обе обязательные области",
        set(EXPECTED_BY_DOMAIN).issubset(domains),
    )

    routed_hits: dict[str, list[tuple[float, dict]]] = {}
    for domain in domains:
        if domain == "consumer":
            # После routing используем уже исправленный индекс с собранной
            # редакцией статьи 16, а не сырой текст закона-изменения.
            domain_docs = STRUCTURED_CONSUMER_CHUNKS
        else:
            domain_docs = [
                doc for doc in SEARCH_DOCUMENTS if doc["domain"] == domain
            ]
        if not domain_docs:
            continue
        routed_hits[domain] = vector_search(
            MULTI_DOMAIN_QUESTION, domain_docs, top_k=1
        )
        section(f"RAG[{domain}]")
        print_hits(routed_hits[domain])

    for domain, expected_id in EXPECTED_BY_DOMAIN.items():
        actual_ids = {doc["id"] for _, doc in routed_hits.get(domain, [])}
        check(
            f"RAG[{domain}] нашёл {expected_id}",
            expected_id in actual_ids,
            f"фактически: {sorted(actual_ids)}",
        )

    evidence = [
        {
            "domain": domain,
            "law": doc["law"],
            "article": doc["article"],
            "effective_from": doc["effective_from"],
            "text": doc["text"],
            "source_url": doc["source_url"],
        }
        for domain, hits in routed_hits.items()
        for _, doc in hits
        if domain in EXPECTED_BY_DOMAIN
    ]
    final_answer = generate_json(
        "Составьте один ответ по двум ситуациям, используя только evidence. "
        "Разделите выводы по consumer и labor. Не объявляйте нарушение "
        "доказанным: укажите норму и какие факты ещё надо подтвердить. "
        "Формат: {\"situations\": [{\"domain\": \"...\", "
        "\"conclusion\": \"...\", \"law\": \"...\", "
        "\"article\": \"...\", \"conditions_to_check\": [\"...\"]}]}.\n\n"
        f"QUESTION: {MULTI_DOMAIN_QUESTION}\n\n"
        f"EVIDENCE: {json.dumps(evidence, ensure_ascii=False)}"
    )
    section("ФИНАЛЬНЫЙ ОТВЕТ АГЕНТА")
    print_json(final_answer)
    final_text = json.dumps(final_answer, ensure_ascii=False).lower()
    check(
        "синтез ссылается на оба найденных закона",
        "69-фз" in final_text and "306-фз" in final_text,
    )
    check(
        "указаны ст. 16 и ст. 178, а северная ст. 318 не подмешана",
        "16" in final_text and "178" in final_text and "318" not in final_text,
    )

    section("ВЫВОД")
    paragraph(
        "Router не отвечает на юридический вопрос. Он превращает один сложный "
        "запрос в два ограниченных поиска, после чего ответы можно объединить "
        "с отдельными источниками для каждой ситуации."
    )


if __name__ == "__main__":
    run()
