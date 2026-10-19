from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import requests

from coder_agent import AgentRunner, OpenAICompatibleProvider, ToolRegistry


def send_message(token: str, chat_id: int, text: str) -> None:
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text[:4000]},
        timeout=30,
    ).raise_for_status()


def format_result(result: Any) -> str:
    lines = [f"status: {result.status}", result.summary, "", "trace:"]
    for item in result.state.trace[-8:]:
        tool = item.get("tool") or item.get("event")
        observation = item.get("observation") or {}
        lines.append(f"{item.get('step', '?')}. {tool}: {observation.get('status', '')}")
    return "\n".join(lines)


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    allowed = {
        int(value.strip())
        for value in os.environ["TELEGRAM_ALLOWED_CHAT_IDS"].split(",")
        if value.strip()
    }
    workspace = Path(os.environ.get("BOT_WORKSPACE", Path(__file__).parent / "sample_repo"))
    provider = OpenAICompatibleProvider(
        os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1"),
        os.getenv("LOCAL_LLM_MODEL", "qwen3"),
        api_key=os.getenv("LOCAL_LLM_API_KEY", ""),
    )

    offset = 0
    while True:
        try:
            response = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"offset": offset, "timeout": 25},
                timeout=35,
            )
            response.raise_for_status()
            for update in response.json().get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message") or {}
                chat_id = (message.get("chat") or {}).get("id")
                text = (message.get("text") or "").strip()
                if not chat_id or chat_id not in allowed:
                    continue
                if text in {"/start", "/help"}:
                    send_message(
                        token,
                        chat_id,
                        "Send /task <question about the demo repository>. "
                        "The bot can read files and run tests, but cannot write.",
                    )
                    continue
                if not text.startswith("/task "):
                    send_message(token, chat_id, "Use /task <question>.")
                    continue

                task = text.removeprefix("/task ").strip()
                send_message(token, chat_id, "Running the local coding agent…")
                registry = ToolRegistry(workspace, allow_write=False)
                result = AgentRunner(provider, registry, max_steps=8).run(task)
                send_message(token, chat_id, format_result(result))
        except requests.RequestException as exc:
            print(f"telegram error: {exc}")
            time.sleep(3)


if __name__ == "__main__":
    main()
