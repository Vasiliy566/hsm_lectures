"""Общий код практики: подключение к модели и цикл «запрос → вызов → результат → запрос».

Здесь нет ничего, кроме того, что разбирали на слайдах:
  * история — обычный список Python `history`, его ведёт наша программа;
  * модель возвращает элементы output: текст (message) или вызов инструмента (function_call);
  * функцию выполняет программа и добавляет function_call_output с тем же call_id;
  * цикл ограничен числом шагов.

Режим --manual: роль модели играет человек. Программа при этом работает так же,
но все «ответы модели» набраны руками — в выводе и в трассе это помечено.
"""
import json
import os
import time
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
BAR = "─" * 72


# ---------------------------------------------------------------- подключение

def make_client():
    """Клиент OpenAI и имя модели из .env. Импорт внутри: ручному режиму SDK не нужен."""
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv(HERE / ".env")
    missing = [k for k in ("OPENAI_API_KEY", "OPENAI_MODEL") if not os.environ.get(k)]
    if missing:
        raise SystemExit(
            f"Не заданы {', '.join(missing)}. Скопируйте .env.example в .env и впишите ключ "
            "или запустите с --manual (роль модели играете вы)."
        )
    return OpenAI(), os.environ["OPENAI_MODEL"]


# ---------------------------------------------------------------- разбор ответа модели

def as_dict(item) -> dict:
    """Элемент истории в виде dict — чтобы напечатать и сохранить в трассу."""
    return item if isinstance(item, dict) else item.model_dump(exclude_none=True)


def refusal_text(response) -> str | None:
    """Отказ модели приходит отдельным типом содержимого, а не текстом ответа."""
    for item in response.output:
        if item.type == "message":
            for part in item.content:
                if part.type == "refusal":
                    return part.refusal
    return None


def check_finished(response) -> None:
    """Незавершённый ответ и отказ — не ответ. Разбирать такой текст как JSON нельзя."""
    if response.status == "incomplete":
        reason = getattr(response.incomplete_details, "reason", None)
        raise ModelStop(f"ответ не завершён (status=incomplete, reason={reason})")
    refusal = refusal_text(response)
    if refusal:
        raise ModelStop(f"модель отказалась: {refusal}")


class ModelStop(Exception):
    """Цикл остановлен: отказ, незавершённый ответ или лимит шагов."""


# ---------------------------------------------------------------- ручной режим

def human_turn(step: int) -> list[dict]:
    """Человек вместо модели: печатает вызов функции или финальный ответ."""
    print("  [вы вместо модели] Введите вызов:  read_file {\"path\": \"shop/orders.py\"}")
    print("                     или ответ:      ответ: текст или JSON")
    while True:
        line = input("  > ").strip()
        if line.lower().startswith("ответ:"):
            text = line.split(":", 1)[1].strip()
            return [{"type": "message", "role": "assistant",
                     "content": [{"type": "output_text", "text": text}]}]
        name, _, arguments = line.partition(" ")
        if name:
            return [{"type": "function_call", "call_id": f"call_manual_{step:02d}",
                     "name": name, "arguments": arguments.strip() or "{}"}]


def message_text(items: list[dict]) -> str:
    return "".join(part.get("text", "") for item in items if item.get("type") == "message"
                   for part in item.get("content", []))


# ---------------------------------------------------------------- цикл

def agent_loop(task: str, instructions: str, tools: list[dict],
               executor: Callable[[str, str], tuple[str, bool]], *,
               manual: bool, max_steps: int = 8, text_format: dict | None = None,
               max_output_tokens: int | None = None, label: str = "run") -> dict:
    """Повторяем запросы, пока модель вызывает инструменты. Возвращает трассу (dict)."""
    client = model = None
    if not manual:
        client, model = make_client()
    mode = "manual: роль модели играл человек" if manual else f"live: {model}"
    actor = "вы вместо модели" if manual else "модель"
    print(f"[{mode}]")

    history: list = [{"role": "user", "content": task}]  # вся «память» — этот список
    trace = {"mode": mode, "task": task, "steps": [], "final_text": None, "stopped": None}

    for step in range(1, max_steps + 1):
        print(BAR)
        print(f"шаг {step} → отправляем: instructions + история из {len(history)} элементов "
              f"+ описания {len(tools)} инструментов")
        started = time.perf_counter()
        if manual:
            output = human_turn(step)
            raw_output = output
            usage = None
        else:
            kwargs = {"model": model, "instructions": instructions, "input": history,
                      "tools": tools, "parallel_tool_calls": False}
            if text_format:
                kwargs["text"] = {"format": text_format}
            if max_output_tokens:
                kwargs["max_output_tokens"] = max_output_tokens
            response = client.responses.create(**kwargs)
            usage = {"input_tokens": response.usage.input_tokens,
                     "output_tokens": response.usage.output_tokens}
            try:
                check_finished(response)
            except ModelStop as stop:
                print("  ✗", stop)
                trace["stopped"] = str(stop)
                break
            raw_output = response.output
            output = [as_dict(item) for item in raw_output]
        seconds = round(time.perf_counter() - started, 1)

        history += raw_output  # ответ модели целиком — в историю, иначе она не увидит свой вызов
        calls = [item for item in output if item.get("type") == "function_call"]
        record = {"step": step, "seconds": seconds, "usage": usage, "calls": [], "text": None}
        if usage:
            print(f"  токены: вход {usage['input_tokens']}, выход {usage['output_tokens']}; {seconds} с")

        for call in calls:
            print(f"  ← {actor} вызывает: {call['name']}({short(call['arguments'], 200)})   call_id={call['call_id']}")
            result, ok = executor(call["name"], call["arguments"])
            print(f"  ⚙ программа выполнила: {'успех' if ok else 'ОШИБКА'} → {short(result)}")
            history.append({"type": "function_call_output", "call_id": call["call_id"], "output": result})
            record["calls"].append({"name": call["name"], "arguments": call["arguments"],
                                    "call_id": call["call_id"], "ok": ok, "output": result})
        trace["steps"].append(record)

        if not calls:  # вызовов нет — модель дала ответ
            text = message_text(output)
            record["text"] = text
            trace["final_text"] = text
            print(f"  ← {actor}: ответ без вызовов")
            print("    " + text.replace("\n", "\n    "))
            break
    else:
        trace["stopped"] = f"лимит шагов: {max_steps}"
        print(BAR)
        print(f"  ✗ остановлено: лимит {max_steps} шагов, ответа нет")

    trace["history"] = [as_dict(item) for item in history]
    path = save_trace(trace, label)
    print(BAR)
    print(f"трасса сохранена: {path.relative_to(HERE)}")
    return trace


def short(text: str, limit: int = 160) -> str:
    text = text.replace("\n", "\\n")
    return text if len(text) <= limit else text[:limit] + f"… (+{len(text) - limit})"


def save_trace(trace: dict, label: str) -> Path:
    RUNS.mkdir(exist_ok=True)
    path = RUNS / f"{label}_{time.strftime('%H%M%S')}.json"
    path.write_text(json.dumps(trace, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path
