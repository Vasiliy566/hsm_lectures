"""Практика 2. Выполняем вызов инструмента сами — без модели и без ключа API.

Модель в ответ на запрос присылает не действие, а запись вида
    {"type": "function_call", "call_id": "...", "name": "read_file", "arguments": "{...}"}.
Здесь такую запись пишете вы (или берёте готовую из calls/), а программа делает то же,
что сделала бы с вызовом от модели: проверяет имя, аргументы и права, выполняет функцию
и готовит function_call_output с тем же call_id.

Запуск:
    python 03_tools_by_hand.py calls/02_read_file.json
    python 03_tools_by_hand.py calls/*.json                       — все готовые вызовы
    python 03_tools_by_hand.py --name list_files --args '{"folder": "shop"}'
    python 03_tools_by_hand.py --allow-write calls/09_write_denied.json
    python 03_tools_by_hand.py --reset                            — вернуть sandbox/ к исходному
"""
import argparse
import json

from tools import Permissions, execute_call, reset_sandbox

BAR = "─" * 72


def show(call: dict, permissions: Permissions) -> None:
    print(BAR)
    if call.get("_note"):
        print("#", call["_note"])
    print("ВЫЗОВ (так его присылает модель):")
    print(f"  name      = {call['name']}")
    print(f"  arguments = {call['arguments']}    ← это строка JSON, а не объект")
    print(f"  call_id   = {call['call_id']}")

    output, ok = execute_call(call["name"], call["arguments"], permissions)

    print("ВЫПОЛНЯЕТ ПРОГРАММА →", "успех" if ok else "ошибка, её тоже получит модель")
    result_item = {"type": "function_call_output", "call_id": call["call_id"], "output": output}
    print("РЕЗУЛЬТАТ (function_call_output, тот же call_id):")
    print(f"  call_id   = {result_item['call_id']}")
    print("  output    =", short(output))
    # Для чтения человеком печатаем длинный текст отдельно, без экранирования \n.
    data = json.loads(output)
    for key in ("content", "output_tail"):
        if key in data:
            print(f"  --- {key} как текст ---")
            print("  " + data[key][:1500].replace("\n", "\n  "))


def short(text: str, limit: int = 220) -> str:
    return text if len(text) <= limit else text[:limit] + f"… (+{len(text) - limit} символов)"


def main() -> None:
    parser = argparse.ArgumentParser(description="Ручное выполнение вызовов инструментов")
    parser.add_argument("files", nargs="*", help="файлы с вызовами из calls/")
    parser.add_argument("--name", help="имя инструмента")
    parser.add_argument("--args", default="{}", help="аргументы — строка JSON")
    parser.add_argument("--allow-write", action="store_true", help="разрешить write_file")
    parser.add_argument("--reset", action="store_true", help="пересоздать sandbox/ из project/")
    opts = parser.parse_args()

    if opts.reset:
        reset_sandbox()
        print("sandbox/ пересоздан из project/")
        return

    permissions = Permissions(allow_write=opts.allow_write)
    print("[ручной режим: модель не вызывалась, вызовы написаны человеком]")
    calls = [json.load(open(f, encoding="utf-8")) for f in opts.files]
    if opts.name:
        calls.append({"type": "function_call", "call_id": "call_manual_cli",
                      "name": opts.name, "arguments": opts.args})
    if not calls:
        parser.print_help()
        return
    for call in calls:
        show(call, permissions)
    print(BAR)


if __name__ == "__main__":
    main()
