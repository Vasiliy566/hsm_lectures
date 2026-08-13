# Практика 03. Один настоящий function/tool call
#
# План:
# 1. Описать read_file как function declaration с JSON Schema.
# 2. Передать declaration в tools вместе с задачей пользователя.
# 3. Найти в ответе step типа function_call.
# 4. Получить name, arguments и call_id.
# 5. Выполнить Python-функцию read_file.
# 6. Отправить function_result с тем же call_id.
# 7. Получить финальный текст или следующий function_call.
#
# TODO: составить tool schema для read_file.
# TODO: выполнить настоящий запрос с tools.
# TODO: проверить тип шага перед чтением arguments.
# TODO: выполнить только разрешённый tool.
# TODO: вернуть результат с корректным call_id.
# TODO: не делать цикл — этот файл намеренно обслуживает только один tool call.

