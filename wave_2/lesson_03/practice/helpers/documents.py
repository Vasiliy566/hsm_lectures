"""Документы магазина и нарезка на фрагменты.

Документ — файл data/*.md. В шапке между строками --- лежат метаданные:
id, название, редакция и даты действия.
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path

PRACTICE = Path(__file__).resolve().parents[1]
DATA = PRACTICE / "data"


@dataclass
class Document:
    id: str
    title: str
    version: str
    valid_from: str
    valid_to: str
    text: str


@dataclass
class Chunk:
    id: str          # например policy-v3#4.2 или policy-v3#7
    doc: Document    # откуда фрагмент: по нему видны редакция и даты
    text: str        # что ищем и что попадёт во вход модели


def load_documents() -> list[Document]:
    docs = []
    for path in sorted(DATA.glob("*.md")):
        _, header, text = path.read_text(encoding="utf-8").split("---", 2)
        meta = {}
        for line in header.strip().splitlines():
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
        docs.append(Document(meta["id"], meta["title"], meta["version"],
                             meta["valid_from"], meta["valid_to"], text.strip()))
    return docs


def load_questions() -> list[dict]:
    return json.loads((DATA / "questions.json").read_text(encoding="utf-8"))


def chunk_by_size(doc: Document, size: int) -> list[Chunk]:
    """Режем текст подряд кусками примерно по size символов, не глядя на пункты."""
    words = re.sub(r"^#+\s*", "", doc.text, flags=re.M).split()
    pieces, current = [], ""
    for word in words:
        if current and len(current) + 1 + len(word) > size:
            pieces.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    pieces.append(current)
    return [Chunk(f"{doc.id}#{n}", doc, piece) for n, piece in enumerate(pieces, 1)]


def chunk_by_sections(doc: Document, with_header: bool = False) -> list[Chunk]:
    """Режем по заголовкам: один пункт — один фрагмент.

    with_header=True дописывает в начало фрагмента документ и редакцию,
    чтобы фрагмент был понятен без соседей.
    """
    parts = re.split(r"^#{2,3} (.+)$", doc.text, flags=re.M)
    chunks = []
    for n, (title, body) in enumerate(zip(parts[1::2], parts[2::2]), 1):
        body = body.strip()
        if not body:  # заголовок раздела без своего текста, например «4. Изменение заказа…»
            continue
        number = title.split()[0].rstrip(".")
        section = number if number[0].isdigit() else str(n)
        text = f"{title}\n{body}"
        if with_header:
            text = f"[{doc.title}, ред. {doc.version}, {valid(doc)}]\n{text}"
        chunks.append(Chunk(f"{doc.id}#{section}", doc, text))
    return chunks


def valid(doc: Document) -> str:
    return f"действует {doc.valid_from} — {doc.valid_to or 'сейчас'}"


def as_context(found: list[tuple[Chunk, float]]) -> str:
    """Найденные фрагменты для входа модели: текст вместе с источником и редакцией."""
    blocks = []
    for chunk, _ in found:
        blocks.append(f'<fragment id="{chunk.id}" version="{chunk.doc.version}" '
                      f'valid="{valid(chunk.doc)}">\n{chunk.text}\n</fragment>')
    return "\n\n".join(blocks)
