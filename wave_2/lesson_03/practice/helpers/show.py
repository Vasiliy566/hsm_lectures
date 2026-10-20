"""Печать в терминал: заголовки, найденные фрагменты, ответы, таблицы."""
from helpers.documents import Chunk
from helpers.llm import Answer

WIDTH = 78


def header(title: str) -> None:
    print()
    print("━" * WIDTH)
    print(title)
    print("━" * WIDTH)


def results(found: list[tuple[Chunk, float]], expect: str | None = None) -> None:
    """Найденные фрагменты: место, id, score и начало текста. ★ — фрагмент с нужным текстом."""
    for place, (chunk, score) in enumerate(found, 1):
        mark = "★" if expect and expect in chunk.text else " "
        preview = " ".join(chunk.text.split())[:52]
        print(f" {mark} {place}. {chunk.id:<14} {score:>7}   {preview}…")


def chunk(item: Chunk) -> None:
    print(f"[{item.id}]")
    print(item.text)
    print()


def answer(item: Answer) -> None:
    print(item.text)
    print(f"\n(токенов во входе: {item.input_tokens})")


def table(rows: list[list[str]]) -> None:
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    for n, row in enumerate(rows):
        print("  ".join(cell.ljust(w) for cell, w in zip(row, widths)))
        if n == 0:
            print("  ".join("─" * w for w in widths))
