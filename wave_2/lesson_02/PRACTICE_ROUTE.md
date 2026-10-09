# Как повторить практику второго занятия

Начните без модели: так можно проверить окружение и увидеть ошибки формата, аргументов и прав без расходов на API. Затем подключите модель и сравните её вызовы с ручными.

## Подготовка окружения

Нужны Python 3.11 или новее и `uv`. [Инструкция по установке uv](https://docs.astral.sh/uv/getting-started/installation/) на английском; сами упражнения и комментарии к ним на русском.

Откройте терминал в папке `practice`. Создайте окружение и установите зависимости:

```bash
uv venv
uv pip install -r requirements.txt
```

Активируйте окружение. На macOS и Linux:

```bash
source .venv/bin/activate
```

На Windows в PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Если PowerShell запрещает активацию, можно не менять политику системы: запускайте `.venv\Scripts\python.exe` вместо `python`. На macOS и Linux аналогично используйте `.venv/bin/python`.

```bash
python selfcheck.py
```

Ожидается «Всё готово». В исходном учебном проекте **два теста должны падать**: это специально оставленная ошибка, которую будет исправлять агент.

## Маршрут без API

Ориентир по времени: 30–45 минут на повторение и разбор.

### Формат и смысл ответа

```bash
python 01_test_user.py --show-schema
python check_answer.py answers/manual_1_text.txt answers/manual_3_two_files.json answers/manual_6_no_such_file.json answers/manual_8_good.json
```

Посмотрите, на каком уровне останавливается каждый ответ: JSON, схема или факты. Все файлы `answers/manual_*` написаны вручную, это не результаты замера качества модели.

Вопрос: почему `manual_6_no_such_file.json` может соответствовать схеме и всё равно быть неправильным?

### Вызов инструмента

```bash
python 03_tools_by_hand.py calls/01_list_files.json calls/02_read_file.json calls/03_run_tests.json
python 03_tools_by_hand.py calls/04_bad_args.json calls/05_unknown_tool.json calls/06_outside.json calls/07_secret.json calls/08_missing.json calls/09_write_denied.json
```

Сравните успешный вызов с неверными аргументами, неизвестным инструментом, выходом за границы проекта и запретом записи. Найдите в `tools.py` проверку, которая отклоняет каждый ошибочный вызов.

Вопрос: кто принимает окончательное решение о доступе к `.env`, модель или программа?

### Skill

```bash
python skills_lab.py
python skills_lab.py --show fix-failing-test
```

Скопируйте `skill_template/my-skill/` в `skills/` под новым именем. Приведите поле `name` в YAML-шапке в соответствие имени папки. Напишите понятное `description`: когда этот skill нужен и когда не нужен. Ещё раз запустите `python skills_lab.py`.

Вопрос: что изменится, если написать в skill «сделай git commit», но инструмента для git у агента нет?

У `02_structured.py`, `04_tool_call.py` и `05_mini_coder.py` есть `--manual`: роль модели играете вы. Это способ исследовать протокол, а не запуск настоящей модели и не доказательство качества агента.

## Маршрут с моделью

Скопируйте `.env.example` в `.env` и впишите свой ключ и доступную модель с поддержкой function calling и structured outputs. Локальные API-запросы могут быть платными; ключ, который даёт Planerverse, предназначен для стенда и не заменяет локальный ключ. Файл `.env` не публикуйте.

```bash
python 02_structured.py --no-schema --runs 3
python 02_structured.py --runs 3
python 02_structured.py --max-output-tokens 16
python 04_tool_call.py
```

Три запуска нужны для наблюдения различий, а не для статистического вывода о надёжности. При ограничении ответа посмотрите на статус до попытки разобрать JSON. В трассе `runs/tools_*.json` найдите вызов и результат с одинаковым `call_id`.

```bash
python 05_mini_coder.py "Тест падает: бот разрешил сменить адрес для A127. Исправь." --allow-write
python 05_mini_coder.py "Тест падает: бот разрешил сменить адрес для A127. Исправь."
```

Сравните работу с правом записи и без него. Программа проверяет отчёт по диску и тестам. Исходный `project/` не меняется: работа идёт с копией `sandbox/`. В `project/.env` лежит только искусственная учебная заглушка для проверки запрета доступа.

Подробности и остальные команды: [practice/README.md](practice/README.md).
