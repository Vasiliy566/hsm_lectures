"""Показ 3. Мини-кодер с поиском по регламентам решает задачу SEV-418.

Инструменты: search_docs, search_code, read_file, replace_in_file, run_tests.
Каждый запуск начинается с чистой копии проекта в sandbox/.

Запуск:  python 04_mini_coder.py
"""
from helpers.coder import check_result, reset_sandbox, run_agent

TASK = """SEV-418. Смена адреса работает не по регламенту для экспресс-заказов.
Приведи can_change_address в shop/orders.py в соответствие с действующей редакцией
регламента изменения заказа. Новая сигнатура: can_change_address(status, express=False)."""

INSTRUCTIONS = """Ты — кодер магазина «Север». Работаешь только через инструменты.
Правила магазина ищи в регламентах через search_docs и смотри на редакцию и даты действия.
Код ищи через search_code и читай через read_file. Меняй точечно через replace_in_file, тесты не трогай.
После правки запусти run_tests.
В конце коротко: что изменил и на какой фрагмент регламента опирался (id фрагмента)."""

reset_sandbox()
trace = run_agent(TASK, INSTRUCTIONS, max_steps=15)
check_result(trace)
