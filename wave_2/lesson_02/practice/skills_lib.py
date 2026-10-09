"""Как среда агента находит и загружает skills. Модель здесь не участвует.

Три уровня загрузки (как в спецификации Agent Skills):
  1. каталог: name + description всех skills — сразу в инструкции, это дёшево;
  2. тело SKILL.md — только когда модель вызвала load_skill(name);
  3. файлы из папки skill (references/ и др.) — только по read_skill_file(name, path).
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS_DIR = HERE / "skills"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def parse_skill(skill_md: Path) -> dict:
    """Разобрать SKILL.md: YAML-шапка между --- и текст инструкции."""
    text = skill_md.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not match:
        return {"folder": skill_md.parent.name, "meta": {}, "body": text, "path": skill_md}
    meta = {}
    for line in match.group(1).splitlines():  # простой разбор: «ключ: значение» в одну строку
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    return {"folder": skill_md.parent.name, "meta": meta, "body": match.group(2).strip(),
            "path": skill_md}


def problems(skill: dict) -> list[str]:
    """Проверки формата SKILL.md."""
    found = []
    name, description = skill["meta"].get("name", ""), skill["meta"].get("description", "")
    if not skill["meta"]:
        found.append("нет YAML-шапки между строками ---")
    if not name:
        found.append("нет поля name")
    elif not NAME_RE.match(name) or len(name) > 64:
        found.append(f"name {name!r}: только a-z, 0-9 и дефисы, до 64 символов")
    elif name != skill["folder"]:
        found.append(f"name {name!r} не совпадает с именем папки {skill['folder']!r}")
    if not description:
        found.append("нет поля description")
    elif len(description) > 1024:
        found.append(f"description длиннее 1024 символов ({len(description)})")
    if not skill["body"]:
        found.append("пустая инструкция после шапки")
    return found


def discover(skills_dir: Path = SKILLS_DIR) -> dict[str, dict]:
    """Все корректные skills в папке: имя → skill. Некорректные пропускаем."""
    found = {}
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        skill = parse_skill(skill_md)
        if not problems(skill):
            found[skill["meta"]["name"]] = skill
    return found


def catalog_text(skills: dict[str, dict]) -> str:
    """Уровень 1: что попадёт в инструкции до начала работы."""
    if not skills:
        return ""
    lines = ["Доступные skills. Если задача подходит под описание, сначала вызови load_skill:"]
    lines += [f"- {name}: {s['meta']['description']}" for name, s in skills.items()]
    return "\n".join(lines)


def skill_files(skill: dict) -> list[str]:
    folder = skill["path"].parent
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*")
                  if p.is_file() and p.name != "SKILL.md")


def load_skill(skills: dict[str, dict], name: str) -> dict:
    """Уровень 2: тело инструкции и список дополнительных файлов."""
    if name not in skills:
        return {"error": "not_found", "detail": f"нет skill {name!r}; есть: {', '.join(skills) or 'нет'}"}
    skill = skills[name]
    return {"name": name, "instructions": skill["body"], "files": skill_files(skill)}


def read_skill_file(skills: dict[str, dict], name: str, path: str) -> dict:
    """Уровень 3: один файл из папки skill. Только внутри этой папки."""
    if name not in skills:
        return {"error": "not_found", "detail": f"нет skill {name!r}"}
    folder = skills[name]["path"].parent.resolve()
    target = (folder / path).resolve()
    if not target.is_relative_to(folder):
        return {"error": "access_denied", "detail": "путь вне папки skill"}
    if not target.is_file():
        return {"error": "not_found", "detail": f"нет файла {path} в skill {name}"}
    return {"name": name, "path": path, "content": target.read_text(encoding="utf-8")}


SKILL_TOOLS = [
    {
        "type": "function",
        "name": "load_skill",
        "description": "Загрузить инструкцию skill по имени из списка доступных skills.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}},
                       "required": ["name"], "additionalProperties": False},
        "strict": True,
    },
    {
        "type": "function",
        "name": "read_skill_file",
        "description": "Прочитать дополнительный файл из папки загруженного skill, например references/report.md.",
        "parameters": {"type": "object",
                       "properties": {"name": {"type": "string"}, "path": {"type": "string"}},
                       "required": ["name", "path"], "additionalProperties": False},
        "strict": True,
    },
]
