"""Показ 2А. Один вопрос — три способа поиска: по словам, по смыслу и гибрид.

Запуск:  python 02_three_searches.py
         python 02_three_searches.py "Свой вопрос"
"""
import sys

from helpers.documents import chunk_by_sections, load_documents
from helpers.search import MeaningSearch, WordSearch, hybrid
from helpers.show import header, results

QUESTION = sys.argv[1] if len(sys.argv) > 1 else "Можно поменять адрес, если заказ уже собирают?"
ANSWER_TEXT = "После начала сборки адрес изменить нельзя"  # ★ в выводе — фрагмент с ответом

# База: регламенты двух редакций и FAQ поддержки, порезанные по пунктам.
chunks = [chunk for doc in load_documents() for chunk in chunk_by_sections(doc)]
print(f"Вопрос: {QUESTION}\nФрагментов в базе: {len(chunks)}")

header("1. По словам (BM25)")
words = WordSearch(chunks)
results(words.search(QUESTION, k=5), ANSWER_TEXT)

header("2. По смыслу (эмбеддинги)")
meaning = MeaningSearch(chunks)
results(meaning.search(QUESTION, k=5), ANSWER_TEXT)

header("3. Гибрид: оба списка, объединённые через RRF")
results(hybrid(QUESTION, words, meaning, k=5), ANSWER_TEXT)
