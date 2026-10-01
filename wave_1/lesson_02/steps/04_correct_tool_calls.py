# Практика 04. Корректный слой tools
#
# План:
# 1. Описать list_files, read_file, replace_in_file и run_tests.
# 2. Создать registry: имя tool → Python-функция.
# 3. Валидировать имя и аргументы до выполнения.
# 4. Ограничить все пути корнем sample_repo.
# 5. Разделить read tools и write tools.
# 6. Для write вернуть approval_required, пока разрешение не выдано.
# 7. Нормализовать результат каждого tool в JSON.
#
# TODO: написать JSON Schema для каждого tool.
# TODO: написать registry без eval и динамического импорта.
# TODO: реализовать safe_path и защиту от ../.
# TODO: реализовать единый execute_tool(name, arguments).
# TODO: добавить timeout для run_tests.
# TODO: добавить approval gate для replace_in_file.
# TODO: проверить неизвестный tool и неверные аргументы.

