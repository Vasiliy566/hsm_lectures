"""Три способа искать фрагменты: по словам (BM25), по смыслу (эмбеддинги) и гибрид.

Каждый поиск возвращает список пар (фрагмент, score), лучшие — первыми.
"""
import hashlib
import json
import math
import os
import re
from collections import Counter, defaultdict

import snowballstemmer

from helpers.documents import PRACTICE, Chunk
from helpers.llm import connect

STEMMER = snowballstemmer.stemmer("russian")
STOP_WORDS = {"и", "в", "во", "на", "с", "со", "по", "до", "у", "к", "о", "об", "а", "но", "ли",
              "не", "что", "как", "это", "уже", "ещё", "еще", "если", "для", "из", "за", "же", "то"}
CACHE = PRACTICE / "cache" / "embeddings.json"


def words(text: str) -> list[str]:
    """Нормализация для поиска по словам: нижний регистр, без служебных слов, основа слова.
    «заказа» и «заказ» → «заказ». А «собирают» и «сборка» останутся разными."""
    tokens = re.findall(r"[а-яёa-z0-9]+", text.lower())
    return [STEMMER.stemWord(t) for t in tokens if t not in STOP_WORDS]


class WordSearch:
    """BM25: score растёт за каждое совпавшее слово, редкие слова весят больше частых."""

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.counts = [Counter(words(c.text)) for c in chunks]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.avg_length = sum(self.lengths) / len(self.lengths)
        n = len(chunks)
        df = Counter(word for counts in self.counts for word in counts)
        self.idf = {w: math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5)) for w in df}

    def search(self, query: str, k: int = 5) -> list[tuple[Chunk, float]]:
        scored = []
        for chunk, counts, length in zip(self.chunks, self.counts, self.lengths):
            score = 0.0
            for word in words(query):
                tf = counts.get(word, 0)
                if tf:
                    norm = self.k1 * (1 - self.b + self.b * length / self.avg_length)
                    score += self.idf[word] * tf * (self.k1 + 1) / (tf + norm)
            if score > 0:
                scored.append((chunk, round(score, 2)))
        return sorted(scored, key=lambda pair: -pair[1])[:k]


class MeaningSearch:
    """Эмбеддинги OpenAI: текст → вектор, ищем ближайшие векторы (косинус).
    Векторы сохраняются в cache/, поэтому заготовленные вопросы работают и без ключа."""

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.vectors = embed([c.text for c in chunks])

    def search(self, query: str, k: int = 5) -> list[tuple[Chunk, float]]:
        q = embed([query])[0]
        scored = [(chunk, round(cosine(q, v), 3)) for chunk, v in zip(self.chunks, self.vectors)]
        return sorted(scored, key=lambda pair: -pair[1])[:k]


def hybrid(query: str, word_search: WordSearch, meaning_search: MeaningSearch,
           k: int = 5) -> list[tuple[Chunk, float]]:
    """RRF: складываем 1 / (60 + место) из двух списков. Сами score не сравниваем — у них разные шкалы."""
    scores, by_id = defaultdict(float), {}
    for results in (word_search.search(query, 20), meaning_search.search(query, 20)):
        for place, (chunk, _) in enumerate(results, 1):
            scores[chunk.id] += 1 / (60 + place)
            by_id[chunk.id] = chunk
    best = sorted(scores, key=lambda cid: -scores[cid])[:k]
    return [(by_id[cid], round(scores[cid], 4)) for cid in best]


def found(results: list[tuple[Chunk, float]], expect: str) -> bool:
    """Нужный текст есть хотя бы в одном найденном фрагменте."""
    return any(expect in chunk.text for chunk, _ in results)


def recall(search, questions: list[dict], kind: str, k: int = 5) -> str:
    """Для скольких вопросов нужный фрагмент попал в top-k: «7 / 10»."""
    selected = [q for q in questions if q["kind"] == kind]
    hits = sum(found(search(q["question"], k), q["expect"]) for q in selected)
    return f"{hits} / {len(selected)}"


# ---------------------------------------------------------------- эмбеддинги с кэшем

def embed(texts: list[str]) -> list[list[float]]:
    model = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    keys = [hashlib.sha256(f"{model}\n{t}".encode()).hexdigest() for t in texts]
    missing = [t for t, key in zip(texts, keys) if key not in cache]
    if missing:
        client, _ = connect()
        response = client.embeddings.create(model=model, input=missing)
        for text, item in zip(missing, response.data):
            key = hashlib.sha256(f"{model}\n{text}".encode()).hexdigest()
            cache[key] = [round(x, 6) for x in item.embedding]
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(cache), encoding="utf-8")
    return [cache[key] for key in keys]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))
