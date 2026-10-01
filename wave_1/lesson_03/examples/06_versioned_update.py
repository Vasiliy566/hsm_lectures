"""Шаг 6. Обновляем RAG новой редакцией, не удаляя старую."""

from __future__ import annotations

import hashlib
from datetime import date

from demo_common import check, headline, section
from legal_corpus import (
    CONSUMER_16_NEW_CONSOLIDATED_TEXT,
    CONSUMER_16_OLD_TEXT,
    SOURCE_FZ69,
    SOURCE_ZPP_16,
)


OLD_VERSION = {
    "id": "consumer_16_v1",
    "effective_from": date(1992, 4, 7),
    "effective_to": None,
    "source_url": SOURCE_ZPP_16,
    "text": CONSUMER_16_OLD_TEXT,
}

NEW_VERSION = {
    "id": "consumer_16_v2_after_69_fz",
    "effective_from": date(2025, 9, 1),
    "effective_to": None,
    "source_url": SOURCE_FZ69,
    "text": CONSUMER_16_NEW_CONSOLIDATED_TEXT,
}


def active_version(index: list[dict], as_of: date) -> dict:
    candidates = [
        chunk
        for chunk in index
        if chunk["effective_from"] <= as_of
        and (chunk["effective_to"] is None or as_of < chunk["effective_to"])
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"На {as_of} найдено редакций: {len(candidates)}")
    return candidates[0]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def apply_update(index: list[dict], new_version: dict) -> list[dict]:
    updated: list[dict] = []
    for chunk in index:
        if chunk["effective_to"] is None:
            chunk = {**chunk, "effective_to": new_version["effective_from"]}
        updated.append(chunk)
    updated.append(new_version)
    return updated


def show_lookup(index: list[dict], as_of: date) -> dict:
    version = active_version(index, as_of)
    print(f"{as_of}: {version['id']}")
    print(f"   hash: {content_hash(version['text'])}")
    print(f"   период: {version['effective_from']} .. {version['effective_to'] or '∞'}")
    return version


def run() -> None:
    headline("6. Закон обновился: versioned upsert вместо overwrite")

    stale_index = [OLD_VERSION]
    section("ДО ЗАГРУЗКИ 69-ФЗ")
    stale_result = show_lookup(stale_index, date(2025, 9, 15))
    check(
        "на 15.09 выбрана новая редакция",
        stale_result["id"] == NEW_VERSION["id"],
        "индекс устарел и ошибочно считает старую редакцию бессрочной",
    )

    current_index = apply_update(stale_index, NEW_VERSION)
    section("UPDATE JOB")
    print("1. Скачали официальный источник и посчитали hash.")
    print("2. Закрыли effective_to старой версии датой 2025-09-01.")
    print("3. Добавили новую версию и её embedding. Старую не удалили.")
    print("4. После атомарного переключения запускаем retrieval-eval.")

    section("ПОСЛЕ ОБНОВЛЕНИЯ")
    before = show_lookup(current_index, date(2025, 8, 31))
    after = show_lookup(current_index, date(2025, 9, 15))
    check("на 31.08 сохранена старая редакция", before["id"] == OLD_VERSION["id"])
    check("на 15.09 выбрана новая редакция", after["id"] == NEW_VERSION["id"])
    check(
        "периоды версий не пересекаются",
        current_index[0]["effective_to"] == current_index[1]["effective_from"],
    )


if __name__ == "__main__":
    run()
