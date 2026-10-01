"""Офлайн-заглушка OpenAI Responses API — только для проверки установки и показа механики.

Ответы заранее записаны: это НЕ модель. Запуск:
    python offline/fake_llm_server.py
и в .env:
    OPENAI_API_KEY=offline
    OPENAI_BASE_URL=http://127.0.0.1:8765/v1
    OPENAI_MODEL=offline
Для работы с настоящим OpenAI строку OPENAI_BASE_URL из .env удалите.
"""
import json, random, time
from http.server import BaseHTTPRequestHandler, HTTPServer

GOOD = '''```python
import re

_PATTERN = re.compile(r"^\\s*(?:(\\d+)h)?\\s*(?:(\\d+)m)?\\s*(?:(\\d+)s)?\\s*$", re.IGNORECASE)


def parse_duration(text: str) -> int:
    match = _PATTERN.match(text)
    if not match or not any(match.groups()):
        raise ValueError(f"bad duration: {text!r}")
    h, m, s = (int(g) if g else 0 for g in match.groups())
    return h * 3600 + m * 60 + s
```'''
SLOPPY = '''Вот функция:
```python
import re
def parse_duration(s):
    total = 0
    for n, u in re.findall(r"(\\d+)([hms])", s):
        total += int(n) * {"h": 3600, "m": 60, "s": 1}[u]
    return total
```
Она поддерживает часы, минуты и секунды.'''
FIXED = GOOD.split("```python\n")[1].split("```")[0]

def text_item(text):
    return {"type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}]}


def call_item(i, name, args):
    return {"type": "function_call", "id": f"fc_{i}", "call_id": f"call_{i}", "name": name,
            "arguments": json.dumps(args, ensure_ascii=False), "status": "completed"}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert self.path.endswith("/responses"), f"ожидался Responses API, пришло {self.path}"
        items = req["input"] if isinstance(req["input"], list) else [{"role": "user", "content": req["input"]}]
        for it in items:  # проверяем, что история собрана в формате Responses API
            kind = it.get("type", "message")
            assert kind in ("message", "function_call", "function_call_output", "reasoning"), it
            if kind == "function_call_output":
                assert "call_id" in it and isinstance(it["output"], str), it
            if kind == "function_call":
                assert {"call_id", "name", "arguments"} <= set(it), it
        for t in req.get("tools", []):
            assert t["type"] == "function" and "name" in t and "parameters" in t, t
        tools = [t["name"] for t in req.get("tools", [])]
        n_out = sum(it.get("type") == "function_call_output" for it in items)
        if "factorize" in tools:
            out = [text_item("[офлайн-заглушка] 34324329 = 3 × 13 × 839 × 1049")] if n_out \
                else [call_item(n_out, "factorize", {"n": 34324329})]
        elif "run_tests" in tools:
            script = [("list_files", {}), ("read_file", {"path": "durations.py"}),
                      ("read_file", {"path": "test_durations.py"}), ("run_tests", {}),
                      ("write_file", {"path": "durations.py", "content": FIXED}), ("run_tests", {})]
            out = [call_item(n_out, *script[n_out])] if n_out < len(script) \
                else [text_item("[офлайн-заглушка] Готово: добавил проверку формата и регистр.")]
        else:
            users = [it for it in items if it.get("role") == "user"]
            text = users[-1]["content"]
            if "stats.py" in text and "average" in text:  # пример из homework_01_agent/local_check
                fixed = ('def average(numbers):\n    """Среднее арифметическое списка чисел."""\n'
                         '    if not numbers:\n        return 0.0\n    return sum(numbers) / len(numbers)\n\n\n'
                         'def median(numbers):\n    """Медиана списка чисел."""\n    ordered = sorted(numbers)\n'
                         '    middle = len(ordered) // 2\n    if len(ordered) % 2:\n        return ordered[middle]\n'
                         '    return (ordered[middle - 1] + ordered[middle]) / 2')
                out = [text_item(f"=== FILE: stats.py ===\n```python\n{fixed}\n```")]
            elif "parse_duration" in text:
                out = [text_item(GOOD if "# Правила" in text else SLOPPY)]
            elif "Придумай" in text:  # имитация разброса ответов
                out = [text_item("[офлайн-заглушка] " + random.choice(["Зерно", "Конспект", "Перемена", "Зерно"]))]
            else:
                out = [text_item(f"[офлайн-заглушка] получено: {text[:40]} (в истории {len(items)} сообщений)")]
        n_in = len(json.dumps(req, ensure_ascii=False)) // 4
        body = {"id": "resp_1", "object": "response", "created_at": int(time.time()), "status": "completed",
                "model": req["model"], "output": out, "parallel_tool_calls": True, "tool_choice": "auto",
                "tools": req.get("tools", []),
                "usage": {"input_tokens": n_in, "output_tokens": 42, "total_tokens": n_in + 42,
                          "input_tokens_details": {"cached_tokens": 0},
                          "output_tokens_details": {"reasoning_tokens": 0}}}
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


print("Заглушка слушает http://127.0.0.1:8765/v1 (Ctrl+C — выход)")
HTTPServer(("127.0.0.1", 8765), H).serve_forever()
