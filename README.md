# HSM: LLM agents course

Материалы второй лекции: от первых API-запросов и наивного workflow до
function calling, ReAct-loop и минимального coding agent.

## Содержание

- [`lesson_02/steps`](lesson_02/steps) — шаги практики `01–08`;
- [`lesson_02/starter`](lesson_02/starter) — минимальный рабочий coding agent;
- [`lesson_02/HOMEWORK.md`](lesson_02/HOMEWORK.md) — домашнее задание;
- [`lesson_02/lesson_02_agents_architecture.pdf`](lesson_02/lesson_02_agents_architecture.pdf) — презентация.

`secret_constants.py` намеренно отсутствует. Ключ Gemini передаётся только через
переменную окружения `GEMINI_API_KEY` или локальный `.env`, который исключён из
Git.

## Запуск starter-agent

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Заполните GEMINI_API_KEY в .env

cd lesson_02/starter
python ai_coder.py
```

Все вызовы Gemini настоящие. Mock-ответы модели не используются.
