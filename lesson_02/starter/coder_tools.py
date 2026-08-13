"""Безопасные инструменты стартового coding agent."""

from difflib import unified_diff
from pathlib import Path


PLAYGROUND_DIR = (Path(__file__).parent / "playground").resolve()


def _safe_path(file_name: str) -> Path:
    file_path = (PLAYGROUND_DIR / file_name).resolve()
    if not file_path.is_relative_to(PLAYGROUND_DIR):
        raise ValueError("Путь должен находиться внутри playground")
    return file_path


def list_files() -> list[str]:
    return [
        str(path.relative_to(PLAYGROUND_DIR))
        for path in sorted(PLAYGROUND_DIR.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    ]


def open_file(file_name: str) -> str:
    file_path = _safe_path(file_name)
    if not file_path.is_file():
        raise FileNotFoundError(f"Файл не найден: {file_name}")
    return file_path.read_text(encoding="utf-8")


def propose_file_change(file_name: str, new_content: str) -> str:
    """Показывает diff и записывает файл только после одобрения."""
    file_path = _safe_path(file_name)
    old_content = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    diff = "".join(
        unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{file_name}",
            tofile=f"b/{file_name}",
        )
    )

    print(f"\nПредлагаемое изменение:\n{diff or '(нет изменений)'}")
    if input("Применить? [y/N]: ").strip().lower() not in {"y", "yes"}:
        return "Пользователь отклонил изменение"

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(new_content, encoding="utf-8")
    return f"Файл {file_name} записан"
