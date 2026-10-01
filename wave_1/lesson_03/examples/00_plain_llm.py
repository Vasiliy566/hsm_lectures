"""Шаг 0. Проверяем ответ LLM без документов о свежей редакции закона."""

from __future__ import annotations

from demo_common import (
    ask_plain_llm,
    grade_consumer_answer,
    headline,
    paragraph,
    print_json,
    print_question,
    print_result,
    section,
)
from legal_corpus import CONSUMER_QUESTION


def run() -> None:
    headline("0. Голая LLM: автодобавленная страховка")
    print_question(CONSUMER_QUESTION)

    answer = ask_plain_llm(CONSUMER_QUESTION)
    section("ОТВЕТ МОДЕЛИ")
    print_json(answer)

    passed = grade_consumer_answer(answer)
    print_result(
        passed,
        "69-ФЗ от 07.04.2025; п. 3.1 ст. 16 Закона о защите прав потребителей; "
        "действует с 01.09.2025; платная дополнительная услуга; письменное "
        "согласие; запрет автоматической отметки; отказ от оплаты или возврат "
        "в течение трех дней после требования.",
    )
    section("ВАЖНО")
    paragraph(
        "Это эксперимент, а не заготовленный ответ: при смене модели результат "
        "может измениться. Даже фактический PASS здесь ещё не означает, что "
        "ответ был получен из проверяемого источника."
    )


if __name__ == "__main__":
    run()
