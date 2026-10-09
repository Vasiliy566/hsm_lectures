"""Практика 2. Что видит агент на каждом уровне загрузки skills. Без API.

Запуск:
    python skills_lab.py                         — проверить все skills и показать каталог
    python skills_lab.py --show fix-failing-test — что вернёт load_skill(...)
    python skills_lab.py --dir skill_template    — проверить шаблон или свою папку
"""
import argparse
import json
from pathlib import Path

from skills_lib import SKILLS_DIR, catalog_text, discover, load_skill, parse_skill, problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, default=SKILLS_DIR)
    parser.add_argument("--show", help="имя skill: показать тело, как его получит модель")
    opts = parser.parse_args()

    print(f"Папка: {opts.dir}\n")
    for skill_md in sorted(opts.dir.glob("*/SKILL.md")):
        skill = parse_skill(skill_md)
        found = problems(skill)
        status = "✓ формат в порядке" if not found else "✗ " + "; ".join(found)
        print(f"{skill['folder']:22} {status}")
        print(f"{'':22} шапка {len(skill_md.read_text(encoding='utf-8')) - len(skill['body'])} симв., "
              f"тело {len(skill['body'])} симв.")

    skills = discover(opts.dir)
    print("\n── Уровень 1. Каталог: это добавляется в инструкции ДО начала работы ──")
    print(catalog_text(skills) or "(нет корректных skills — каталог пустой)")

    if opts.show:
        print(f"\n── Уровень 2. load_skill({opts.show!r}) вернёт модели ──")
        result = load_skill(skills, opts.show)
        if "error" in result:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"name: {result['name']}\nfiles: {result['files']}\ninstructions:")
            print("  " + result["instructions"].replace("\n", "\n  "))
        print("\nУровень 3: файлы из списка files модель читает через read_skill_file, если нужно.")
    print("\nНапоминание: skill — это текст. Он не добавляет инструментов и прав: "
          "их задаёт программа (tools.py, Permissions).")


if __name__ == "__main__":
    main()
