"""Запуск всей практики или одного шага.

Примеры:
    python workflow_legal_agent.py --step fulltext
    python workflow_legal_agent.py --step bad-chunks
    python workflow_legal_agent.py --step all
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from types import ModuleType


HERE = Path(__file__).resolve().parent
STEPS = {
    "plain": "00_plain_llm.py",
    "fulltext": "01_fulltext_search.py",
    "vector": "02_vector_search.py",
    "bad-chunks": "03_bad_chunking_rag.py",
    "structured-rag": "04_structured_rag.py",
    "routing": "05_multi_rag_router.py",
    "versions": "06_versioned_update.py",
}


def load_module(filename: str) -> ModuleType:
    path = HERE / filename
    module_name = f"lesson03_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Не удалось загрузить {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_step(name: str) -> None:
    module = load_module(STEPS[name])
    runner = getattr(module, "run", None)
    if not callable(runner):
        raise RuntimeError(f"В {STEPS[name]} нет функции run()")
    runner()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Практика занятия 03")
    parser.add_argument(
        "--step",
        choices=[*STEPS, "all"],
        default="all",
        help="Какой шаг запустить (по умолчанию все)",
    )
    return parser.parse_args()


def main() -> None:
    selected = parse_args().step
    names = list(STEPS) if selected == "all" else [selected]
    for name in names:
        run_step(name)


if __name__ == "__main__":
    main()
