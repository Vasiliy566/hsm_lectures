"""Тот же минимальный цикл через LangChain — дополнительный пример."""

from dotenv import load_dotenv
from langchain.messages import HumanMessage, SystemMessage
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

from coder_tools import list_files, open_file, propose_file_change


load_dotenv()


@tool
def list_project_files() -> list[str]:
    """Показать список файлов в playground."""
    return list_files()


@tool
def read_project_file(file_name: str) -> str:
    """Прочитать один файл из playground."""
    return open_file(file_name)


@tool
def suggest_file_change(file_name: str, new_content: str) -> str:
    """Показать diff и запросить одобрение перед записью."""
    return propose_file_change(file_name, new_content)


TOOLS = [list_project_files, read_project_file, suggest_file_change]
TOOLS_BY_NAME = {item.name: item for item in TOOLS}
MODEL = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite").bind_tools(TOOLS)


def ai_code(task: str, max_steps: int = 10) -> str:
    messages = [
        SystemMessage("Ты Python-разработчик. Используй инструменты вместо догадок."),
        HumanMessage(task),
    ]

    for _ in range(max_steps):
        response = MODEL.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            return str(response.content)

        for call in response.tool_calls:
            result = TOOLS_BY_NAME[call["name"]].invoke(call)
            messages.append(result)

    raise RuntimeError(f"Agent exceeded max_steps={max_steps}")


if __name__ == "__main__":
    print(ai_code(input("Задача для coding agent: ")))
