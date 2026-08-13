# Практика 06. Обобщаем повторение в ReAct-loop
#
# План:
# 1. Создать state: task + история model steps + observations.
# 2. В цикле просить модель выбрать следующее действие.
# 3. Если пришёл function_call — выполнить tool и добавить function_result.
# 4. Если пришёл финальный ответ — остановиться.
# 5. Остановиться также по max_steps, error или approval_required.
# 6. Записать наблюдаемый trace: action + arguments + observation.
#
# TODO: заменить три одинаковые итерации на for/while loop.
# TODO: обработать ноль, один и несколько function_call в ответе.
# TODO: добавить max_steps и timeout.
# TODO: добавить явные stop conditions.
# TODO: не записывать скрытую chain-of-thought в trace.
# TODO: вывести траекторию coding agent после завершения.

