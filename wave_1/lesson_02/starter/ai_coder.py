"""Минимальный coding agent на Gemini Interactions API."""

import json
import logging

from dotenv import load_dotenv
from google import genai

from coder_tools import list_files, open_file, propose_file_change


MODEL = "gemini-3.1-flash-lite"
MAX_STEPS = 10
SYSTEM_PROMPT = """
Ты Python-разработчик. Работай только с файлами из playground.
Сначала изучи README и существующий код. Используй инструменты вместо догадок.
Изменяй файлы только после явного подтверждения пользователя.
""".strip()

TOOLS = [
    {
        "type": "function",
        "name": "list_files",
        "description": "Показывает список файлов в playground.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "open_file",
        "description": "Читает один текстовый файл из playground.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_name": {
                    "type": "string",
                    "description": "Относительный путь внутри playground.",
                }
            },
            "required": ["file_name"],
        },
    },
    {
        "type": "function",
        "name": "propose_file_change",
        "description": "Показывает diff и после одобрения записывает файл.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_name": {
                    "type": "string",
                    "description": "Относительный путь внутри playground.",
                },
                "new_content": {
                    "type": "string",
                    "description": "Новое содержимое файла целиком.",
                },
            },
            "required": ["file_name", "new_content"],
        },
    },
]

TOOL_REGISTRY = {
    "list_files": list_files,
    "open_file": open_file,
    "propose_file_change": propose_file_change,
}

log = logging.getLogger("ai-coder")


def function_result(call, result: object) -> dict:
    """Связывает observation с function_call через call_id."""
    return {
        "type": "function_result",
        "name": call.name,
        "call_id": call.id,
        "result": [
            {
                "type": "text",
                "text": json.dumps(result, ensure_ascii=False),
            }
        ],
    }


def execute(call) -> dict:
    """Выполняет только функции из явного registry."""
    tool = TOOL_REGISTRY.get(call.name)
    if tool is None:
        result = {"ok": False, "error": f"Unknown tool: {call.name}"}
    else:
        try:
            result = {"ok": True, "value": tool(**call.arguments)}
        except Exception as error:
            result = {"ok": False, "error": str(error)}

    log.info("observation tool=%s result=%s", call.name, result)
    return function_result(call, result)


def ai_code(task: str) -> str:
    """Запускает ограниченный ReAct-loop с server-side history."""
    client = genai.Client()
    interaction = client.interactions.create(
        model=MODEL,
        input=task,
        system_instruction=SYSTEM_PROMPT,
        tools=TOOLS,
        store=True,
    )

    for step_number in range(1, MAX_STEPS + 1):
        calls = [
            step
            for step in interaction.steps
            if step.type == "function_call"
        ]

        log.info(
            "step=%s interaction=%s calls=%s",
            step_number,
            interaction.id,
            len(calls),
        )

        if not calls:
            return interaction.output_text or "Модель завершила работу без текста."

        observations = [execute(call) for call in calls]
        interaction = client.interactions.create(
            model=MODEL,
            input=observations,
            previous_interaction_id=interaction.id,
            system_instruction=SYSTEM_PROMPT,
            tools=TOOLS,
            store=True,
        )

    raise RuntimeError(f"Agent exceeded MAX_STEPS={MAX_STEPS}")


if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(ai_code(input("Задача для coding agent: ")))
