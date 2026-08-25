"""Быстрые проверки логики примеров без вызова Gemini API."""

from demo_common import consumer_checks, fixed_size_chunks, fulltext_search
from coding_agent_with_cookbook_rag import CHUNK_SIZE_LIMIT, split_recipe
from legal_corpus import (
    CONSUMER_EXACT_QUERY,
    CONSUMER_QUESTION,
    RAW_FZ69_DOCUMENT,
    SEARCH_DOCUMENTS,
    STRUCTURED_CONSUMER_CHUNKS,
)


def test_fulltext_contrast_is_real() -> None:
    exact_top = fulltext_search(CONSUMER_EXACT_QUERY, SEARCH_DOCUMENTS, top_k=1)[0][1]
    natural_top = fulltext_search(CONSUMER_QUESTION, SEARCH_DOCUMENTS, top_k=1)[0][1]

    assert exact_top["id"] == "consumer_fz69_article1"
    assert natural_top["id"] == "consumer_insurance_cooling_period"


def test_no_fixed_chunk_contains_complete_answer() -> None:
    chunks = fixed_size_chunks(RAW_FZ69_DOCUMENT, chunk_size=280)

    assert len(chunks) > 1
    assert all(not all(consumer_checks(chunk).values()) for chunk in chunks)


def test_structured_chunk_contains_complete_answer() -> None:
    assert all(consumer_checks(STRUCTURED_CONSUMER_CHUNKS[0]).values())


def test_real_sources_are_attached() -> None:
    official_ids = {
        "consumer_fz69_article1",
        "consumer_fz69_article2",
        "labor_fz306_article178",
    }
    official_docs = [doc for doc in SEARCH_DOCUMENTS if doc["id"] in official_ids]

    assert len(official_docs) == len(official_ids)
    assert all(
        doc["source_url"].startswith("https://publication.pravo.gov.ru/")
        for doc in official_docs
    )


def test_cookbook_splitter_respects_limit_without_cutting_words() -> None:
    long_pdf_block = " ".join(f"token_{index}" for index in range(900))
    chunks = split_recipe("X.1.", "Synthetic", 1, 2, long_pdf_block)

    assert len(chunks) > 1
    assert max(len(chunk.text) for chunk in chunks) <= CHUNK_SIZE_LIMIT
    assert "token_0" in chunks[0].text
    assert "token_899" in chunks[-1].text
