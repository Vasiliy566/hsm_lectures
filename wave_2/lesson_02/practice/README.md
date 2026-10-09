# Практика занятия 1.2: формат ответа, инструменты и skills

Создаём **мини-кодер**: программу, которая с помощью модели OpenAI находит и исправляет ошибку в маленьком проекте. Проект — магазин «Север» из занятия 1.1. В нём ошибка: функция разрешает сменить адрес заказа A127, хотя сборка уже началась. Из-за неё падают два теста.

```
человек ⇄ модель (LLM) ⇄ код программы: инструменты list_files, read_file, write_file, run_tests
                                            работают с sandbox/ — копией project/
```

## Установка (5 минут, лучше до занятия)

```bash
cd practice                                    # из корня распакованного комплекта
uv venv
uv pip install -r requirements.txt
# Активируйте окружение перед командами python; варианты для Windows и macOS/Linux:
# ../PRACTICE_ROUTE.md
cp .env.example .env                            # впишите ключ OpenAI и модель
python selfcheck.py                             # всё, что работает без API, должно быть ✓
```

Ключ храните только в `.env`. Не вставляйте его в код, git, чат или на скриншот.

Для `selfcheck.py` ключ не нужен. Установленные зависимости нужны даже для локальных упражнений. Пошаговый запуск и активация окружения описаны в [маршруте практики](../PRACTICE_ROUTE.md).

## Если API недоступен

Без ключа работают:

- `01_test_user.py --show-schema` и `--check`;
- `check_answer.py`, `03_tools_by_hand.py`, `skills_lab.py`.

У `02_structured.py`, `04_tool_call.py` и `05_mini_coder.py` есть флаг `--manual`: роль модели играете вы. В выводе и в трассе это помечено словами «manual» и «вы вместо модели». Такие ответы — не ответы модели.

---

## Практика 1. Формат ответа

Преподаватель показывает это на занятии. Повторить можно сами.

```bash
python 01_test_user.py --show-schema   # схема, которую SDK сделает из класса TestUser (без ключа)
python 01_test_user.py                 # объект TestUser от модели через responses.parse
python 01_test_user.py --raw           # то же без parse: схема в text.format и разбор вручную
python 01_test_user.py --check '{"name": "Анна", "age": "тридцать", "email": "a@example.com", "role": "guest", "bio": "-"}'
                                       # проверка своего JSON через Pydantic (без ключа)
python check_answer.py answers/*       # три проверки: JSON → схема → правда (ответы написаны вручную)
python 02_structured.py --no-schema --runs 3   # формат только в промпте
python 02_structured.py --runs 3               # со схемой
python 02_structured.py --max-output-tokens 16 # ответ оборвался: разбирать нечего
```

## Практика 2. Инструменты и skills (≈15 минут)

**2.1. Вызов руками.** Модель присылает не действие, а вызов: имя функции и аргументы. Здесь вызов пишете вы.

```bash
python 03_tools_by_hand.py calls/01_list_files.json calls/02_read_file.json calls/03_run_tests.json
python 03_tools_by_hand.py calls/0[4-9]*.json
```

Чем `list_files` отличается от `read_file`? Для каждого ошибочного вызова запишите, кто заметил ошибку и что получит модель.

**2.2. С моделью:**

```bash
python 04_tool_call.py
```

Откройте трассу `runs/tools_*.json`. Найдите пару `function_call` → `function_call_output` с одинаковым `call_id`.

**2.3. Skill: что видит агент и свой skill.**

```bash
python skills_lab.py --show fix-failing-test
cp -r skill_template/my-skill skills/<имя>      # имя папки = name в шапке
python skills_lab.py
```

**2.4. Включается ли skill** (с моделью; без ключа — `--manual`):

```bash
python 05_mini_coder.py "<запрос, на котором skill должен включиться>"
python 05_mini_coder.py "<запрос, на котором skill включаться не должен>"
```

Найдите в выводе `load_skill(...)`. Если skill не включается, улучшите `description`.

Затем добавьте в свой skill шаг «закоммить в git» или «добавь тест в tests/». Что произойдёт и почему?

**Готово, если:**

- нашли пару по `call_id` и знаете, где хранится история — в списке `history` программы;
- ваш skill прошёл `skills_lab.py` и загрузился хотя бы на одном запросе;
- можете объяснить, почему инструкция в skill не даёт доступа.

## Мини-кодер (показывает преподаватель)

```bash
python 05_mini_coder.py "Тест падает: бот разрешил сменить адрес для A127. Исправь." --allow-write
python 05_mini_coder.py "Тест падает: бот разрешил сменить адрес для A127. Исправь."
```

Модель загружает skill, вызывает инструменты и возвращает отчёт по схеме. Программа сверяет отчёт с диском и тестами. Второй запуск — без права записи.

## Файлы

| Файл | Что делает |
|---|---|
| `01_test_user.py` | Pydantic-модель, `responses.parse` и то же вручную |
| `02_structured.py`, `schema.json`, `check_answer.py` | схема против формата в промпте; три уровня проверки ответа |
| `tools.py` | описания инструментов, их запуск, проверка аргументов и прав |
| `03_tools_by_hand.py`, `04_tool_call.py` | вызов инструмента руками и с моделью |
| `common.py` | подключение к модели и цикл «запрос → вызов → результат» |
| `skills_lib.py`, `skills_lab.py` | как среда находит skills и загружает их по уровням |
| `05_mini_coder.py` | всё вместе |
| `project/` | учебный проект, не меняется; агент работает с копией `sandbox/` |
