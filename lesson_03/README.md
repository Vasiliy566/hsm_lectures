# Занятие 03: Context engineering и RAG

Главный сценарий ведущего: `PLAN_ZANYATIYA_03.md`.

| Артефакт | Путь |
|---|---|
| Презентация | `slides/lesson_03_context_engineering_rag.pptx` |
| Сквозной запускаемый workflow | `examples/workflow_legal_agent.py` |
| Семь самостоятельных шагов | `examples/00_plain_llm.py` - `examples/06_versioned_update.py` |
| Общий юридический корпус | `examples/legal_corpus.py` |
| Проверки без API | `examples/test_examples_offline.py` |
| Homework: coding agent + Cookbook RAG | `examples/coding_agent_with_cookbook_rag.py` |

Проверить подготовку книги к домашке можно без ключа и без обращения к Gemini:

```bash
python examples/coding_agent_with_cookbook_rag.py \
  --book "/Users/vasily/Downloads/D. Beazley, B.K. Jones - Python Cookbook, 3rd Edition. 2013.pdf" \
  --check-book
```

Команда выводит число рецептов и фрагментов, максимальную длину фрагмента и
границы содержательной части книги. В RAG не должны попадать приложение,
предметный указатель и служебные страницы.

Презентация и код идут в одном порядке. Слайды явно отмечают переход в каждый
пример и возврат к разбору результата.

Ключ Gemini, PDF *Python Cookbook*, `.env`, `secret_constants.py` и
`__pycache__` не должны попадать в раздаточный архив.
