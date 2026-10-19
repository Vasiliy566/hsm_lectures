# Практика: проверяемый coding-agent harness

## Что собрано

`coder_agent.py` содержит:

- заменяемый `ModelProvider`;
- tools `list_files`, `read_file`, `run_tests`, `replace_in_file`;
- path sandbox и валидацию аргументов;
- approval gate для записи;
- ReAct-loop с `max_steps`;
- typed `finish`, который не примет `verified=true` без зелёных тестов;
- наблюдаемый trace без скрытой chain-of-thought.

`ScriptedProvider` нужен для гарантированного офлайн-показа. Он имитирует решения
модели, но все tools, тесты, approval и запись выполняются настоящим Python-кодом.

## Подготовка

```bash
cd lesson_04/practice
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Проверка harness:

```bash
python -m pytest -q
```

Ожидается `4 passed`.

## Гарантированное демо

Никогда не включайте write-demo на исходной папке. Создайте временную копию:

```bash
demo_dir=$(mktemp -d)
cp -R sample_repo "$demo_dir/repo"
python coder_agent.py \
  --provider scripted \
  --workspace "$demo_dir/repo" \
  --approve
```

В trace должна появиться траектория:

```text
list → read → read tests → tests fail
→ approval_required → edit → tests pass → finish
```

Без `--approve` агент должен остановиться со статусом `approval_required`.

## Домашняя LLM

Provider ожидает OpenAI-compatible `POST /chat/completions` с tool calls.

```bash
export LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
export LOCAL_LLM_MODEL=qwen3

demo_dir=$(mktemp -d)
cp -R sample_repo "$demo_dir/repo"
python coder_agent.py \
  --provider local \
  --workspace "$demo_dir/repo"
```

Первый запуск лучше делать без `--approve`: модель может читать и запускать
тесты, но write остановится на approval gate. После проверки trace повторите запуск
на новой временной копии с `--approve`.

Для длинного agent loop модели нужны:

- надёжный tool calling;
- контекс, куда помещаются system prompt, schemas и observations;
- достаточное качество для работы с кодом;
- предсказуемый chat template у model server.

Если модель отвечает обычным текстом, игнорирует tools или зацикливается, harness вернёт
`unverified_model_stop` или `max_steps`, а не разрешит модели изобразить успех.

## Telegram: read-only demo

1. Создайте бота через BotFather.
2. Укажите token и allowlist chat IDs только в environment.
3. Не показывайте token на проекторе.

```bash
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_ALLOWED_CHAT_IDS=123456789
export BOT_WORKSPACE="$PWD/sample_repo"
export LOCAL_LLM_BASE_URL=http://your-home-server:11434/v1
export LOCAL_LLM_MODEL=qwen3
python telegram_bot.py
```

В Telegram:

```text
/task Найди причину падающего теста. Ничего не изменяй.
```

Bot adapter всегда создаёт `ToolRegistry(..., allow_write=False)` и не имеет механизма approval.
Это демонстрация канала, а не production-ready Telegram service.

## Порядок live coding

1. Показать `ModelProvider` и `ToolRegistry`.
2. Запустить без approval и получить остановку.
3. Показать `_safe_path()` и `replace_in_file()`.
4. Повторить запуск на свежей копии с approval.
5. Открыть trace и проверку `finish`.
6. Заменить `ScriptedProvider` на `OpenAICompatibleProvider`.
