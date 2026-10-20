"""Показ 1. Один вопрос поддержки: без документа и с регламентом целиком во входе.

Запуск:  python 01_without_and_with_docs.py
"""
from helpers.documents import load_documents
from helpers.llm import ask
from helpers.show import answer, header

QUESTION = "Заказ A311 с экспресс-доставкой уже оплачен. Можно поменять адрес доставки?"

# А. Модель знает только то, что было в данных обучения. Регламента «Севера» там нет.
header("А. Без документа")
answer(ask(QUESTION))

# Б. Программа кладёт регламент во вход целиком. Это тоже контекст, только большой.
header("Б. Регламент, ред. 3, целиком во входе")
policy = next(doc for doc in load_documents() if doc.id == "policy-v3")
answer(ask(QUESTION, context=policy.text))
