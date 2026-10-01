# Занятие 1.1. Введение: LLM, промптинг и работа с моделью через API

- [`practice`](practice) — код, который показывается на занятии: первый запрос, один промпт в нескольких запусках, сравнение двух промптов. Инструкция по запуску — в [`practice/README.md`](practice/README.md).
- [`practice/next_lesson`](practice/next_lesson) — заглянуть вперёд: вызов функции и маленький агент (занятие 1.2).
- [`homework_01_agent`](homework_01_agent) — домашнее задание 1: агент уровня 1 для [AgentScore](https://planerverse.ru/).

Код работает напрямую с OpenAI через Responses API. Ключ и модель задаются в `.env`:
`OPENAI_API_KEY`, `OPENAI_MODEL`. Файл `.env` в git не добавляйте.
