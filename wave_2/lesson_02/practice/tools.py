"""Инструменты мини-кодера: описания для модели и функции, которые выполняет программа.

Модель видит только TOOLS — имя, описание и схему аргументов.
Функции ниже модель не видит и не запускает: их вызывает execute_call().
Все файловые инструменты работают только в папке sandbox/ — рабочей копии project/.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft7Validator

HERE = Path(__file__).resolve().parent
PROJECT = HERE / "project"   # исходник учебного проекта, никогда не меняется
SANDBOX = HERE / "sandbox"   # рабочая копия: читать и (если разрешено) писать можно только здесь

MAX_READ_CHARS = 6000        # длинный файл обрезаем: вход модели не бесконечен
BLOCKED_NAMES = {".env"}     # секреты не читаем даже внутри sandbox


# ---------------------------------------------------------------- описания для модели

TOOLS = [
    {
        "type": "function",
        "name": "list_files",
        "description": "Список путей к файлам проекта. Возвращает только имена, не содержимое.",
        "parameters": {
            "type": "object",
            "properties": {
                "folder": {"type": "string",
                           "description": "Папка относительно корня проекта, например 'shop' или '.'"},
            },
            "required": ["folder"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "read_file",
        "description": "Содержимое одного текстового файла проекта.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string",
                         "description": "Путь относительно корня проекта, например 'shop/orders.py'"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "run_tests",
        "description": "Запускает все тесты проекта и возвращает итог и конец вывода.",
        "parameters": {"type": "object", "properties": {}, "required": [],
                       "additionalProperties": False},
        "strict": True,
    },
    {
        "type": "function",
        "name": "write_file",
        "description": "Записывает новое полное содержимое файла проекта. Тесты менять нельзя.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Путь относительно корня проекта"},
                "content": {"type": "string", "description": "Новое содержимое файла целиком"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

TOOL_BY_NAME = {tool["name"]: tool for tool in TOOLS}


# ---------------------------------------------------------------- права

class Permissions:
    """Что разрешено программой. Модель эти настройки не видит и изменить не может."""

    def __init__(self, allow_write: bool = False):
        self.allow_write = allow_write


# ---------------------------------------------------------------- функции

class ToolError(Exception):
    """Ошибка, которую программа вернёт модели как результат вызова."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code, self.detail = code, detail


def reset_sandbox() -> None:
    """Сделать свежую копию project/ в sandbox/."""
    shutil.rmtree(SANDBOX, ignore_errors=True)
    shutil.copytree(PROJECT, SANDBOX, ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)


def ensure_sandbox() -> None:
    if not SANDBOX.exists():
        reset_sandbox()


def safe_path(relative: str) -> Path:
    """Путь внутри sandbox/ или ошибка access_denied. Проверяет программа, а не модель."""
    target = (SANDBOX / relative).resolve()
    if not target.is_relative_to(SANDBOX.resolve()):
        raise ToolError("access_denied", f"путь вне папки проекта: {relative}")
    if target.name in BLOCKED_NAMES:
        raise ToolError("access_denied", f"файл с секретами закрыт для агента: {relative}")
    return target


def list_files(folder: str) -> dict:
    root = safe_path(folder)
    if not root.is_dir():
        raise ToolError("not_found", f"нет такой папки: {folder}")
    files = sorted(
        str(p.relative_to(SANDBOX)) for p in root.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.name not in BLOCKED_NAMES
    )
    return {"folder": folder, "files": files}


def read_file(path: str) -> dict:
    target = safe_path(path)
    if not target.is_file():
        raise ToolError("not_found", f"нет такого файла: {path}")
    text = target.read_text(encoding="utf-8")
    truncated = len(text) > MAX_READ_CHARS
    return {"path": path, "content": text[:MAX_READ_CHARS], "truncated": truncated}


def run_tests() -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=SANDBOX, capture_output=True, text=True, timeout=60,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    output = (proc.stdout + proc.stderr).strip().replace(str(SANDBOX) + "/", "")
    last_line = output.splitlines()[-1] if output else ""
    return {"passed": proc.returncode == 0, "summary": last_line, "output_tail": output[-2500:]}


def write_file(path: str, content: str, permissions: Permissions) -> dict:
    if not permissions.allow_write:
        raise ToolError("access_denied", "запись выключена: запустите с --allow-write")
    target = safe_path(path)
    if Path(path).parts and Path(path).parts[0] == "tests":
        raise ToolError("access_denied", "тесты менять нельзя")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": path, "written_chars": len(content)}


# ---------------------------------------------------------------- исполнение вызова

def execute_call(name: str, arguments: str, permissions: Permissions) -> tuple[str, bool]:
    """Выполнить вызов, который прислала модель (или человек в ручном режиме).

    Возвращает (output, ok). output — строка JSON: её программа отправит модели
    как function_call_output. Ошибка тоже возвращается модели, а не роняет программу.
    """
    ensure_sandbox()
    try:
        tool = TOOL_BY_NAME.get(name)
        if tool is None:
            raise ToolError("unknown_tool", f"нет инструмента {name!r}; есть: {', '.join(TOOL_BY_NAME)}")
        try:
            args = json.loads(arguments)
        except json.JSONDecodeError as e:
            raise ToolError("bad_arguments", f"аргументы — не JSON: {e.msg}")
        errors = sorted(Draft7Validator(tool["parameters"]).iter_errors(args), key=str)
        if errors:
            raise ToolError("bad_arguments", "; ".join(e.message for e in errors))

        if name == "list_files":
            result = list_files(**args)
        elif name == "read_file":
            result = read_file(**args)
        elif name == "run_tests":
            result = run_tests()
        else:
            result = write_file(**args, permissions=permissions)
        return json.dumps(result, ensure_ascii=False), True
    except ToolError as e:
        return json.dumps({"error": e.code, "detail": e.detail}, ensure_ascii=False), False


def changed_files() -> list[str]:
    """Какие файлы sandbox/ отличаются от project/ — факт, который проверяет программа."""
    changed = []
    for p in sorted(SANDBOX.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts:
            continue
        rel = p.relative_to(SANDBOX)
        original = PROJECT / rel
        if not original.exists() or original.read_bytes() != p.read_bytes():
            changed.append(str(rel))
    return changed
