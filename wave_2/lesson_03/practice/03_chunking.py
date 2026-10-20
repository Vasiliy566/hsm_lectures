"""Показ 2Б. Нарезка: по размеру, по пунктам и по пунктам с заголовком.

Меняем только нарезку. Поиск один и тот же — по словам, top-5.

Запуск:  python 03_chunking.py
"""
from helpers.documents import as_context, chunk_by_sections, chunk_by_size, load_documents, load_questions
from helpers.llm import ask
from helpers.search import WordSearch, recall
from helpers.show import answer, chunk, header, table

docs = load_documents()
questions = load_questions()  # 10 вопросов, где важно исключение для экспресс-доставки, и 10 обычных

variants = {
    "по размеру": [c for d in docs for c in chunk_by_size(d, size=400)],
    "по пунктам": [c for d in docs for c in chunk_by_sections(d)],
    "по пунктам + заголовок": [c for d in docs for c in chunk_by_sections(d, with_header=True)],
}

# 1. Граница по размеру прошла посреди пункта 4.2: правило в одном фрагменте, исключение в другом.
header("1. Нарезка по размеру, 400 символов: регламент ред. 3")
pieces = {c.id: c for c in variants["по размеру"]}
chunk(pieces["policy-v3#3"])
chunk(pieces["policy-v3#4"])

# 2. Для скольких вопросов нужный фрагмент попал в top-5.
header("2. Нужный фрагмент в top-5")
rows = [["нарезка", "вопросы про исключение", "обычные вопросы"]]
for name, chunks in variants.items():
    search = WordSearch(chunks).search
    rows.append([name, recall(search, questions, "exception"), recall(search, questions, "regular")])
table(rows)

# 3. Что ответит модель по найденному. Вопрос из тех, где нужно исключение.
QUESTION = "Заказ уже оплачен. Можно поменять адрес доставки?"
for name in ("по размеру", "по пунктам + заголовок"):
    header(f"3. Ответ модели · нарезка {name}")
    found = WordSearch(variants[name]).search(QUESTION, k=5)
    print("во входе:", ", ".join(c.id for c, _ in found), "\n")
    answer(ask(QUESTION, context=as_context(found)))
