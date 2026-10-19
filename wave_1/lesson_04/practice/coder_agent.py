from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

import requests


SYSTEM_INSTRUCTION = """You are a coding agent operating inside one workspace.
Use tools to inspect facts instead of guessing. Reproduce a bug with run_tests before
editing. Make the smallest possible change. Write tools may require approval. After
an edit, run tests again. Finish only by calling the finish tool. Set verified=true
only after an observed successful run_tests result. Never claim access outside the
workspace and never invent tool results."""


@dataclass
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ModelTurn:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class ToolObservation:
    tool: str
    status: str
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"tool": self.tool, "status": self.status, **self.data}

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False)


@dataclass
class AgentState:
    task: str
    messages: list[dict[str, Any]]
    trace: list[dict[str, Any]] = field(default_factory=list)
    last_tests_passed: bool = False


@dataclass
class RunResult:
    status: str
    summary: str
    state: AgentState
    final: dict[str, Any] | None = None


class ModelProvider(Protocol):
    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelTurn: ...


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "list_files": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative directory path"}
        },
        "required": ["path"],
        "additionalProperties": False,
    },
    "read_file": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative file path"}
        },
        "required": ["path"],
        "additionalProperties": False,
    },
    "run_tests": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Relative test file, directory, or '.'",
            }
        },
        "required": ["target"],
        "additionalProperties": False,
    },
    "replace_in_file": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old": {"type": "string"},
            "new": {"type": "string"},
        },
        "required": ["path", "old", "new"],
        "additionalProperties": False,
    },
    "finish": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "changed_files": {"type": "array", "items": {"type": "string"}},
            "verified": {"type": "boolean"},
        },
        "required": ["summary", "changed_files", "verified"],
        "additionalProperties": False,
    },
}


TOOL_DESCRIPTIONS = {
    "list_files": "List files under a relative workspace directory.",
    "read_file": "Read a UTF-8 text file inside the workspace.",
    "run_tests": "Run pytest inside the workspace and return the real exit code.",
    "replace_in_file": "Replace one exact text occurrence. Requires write approval.",
    "finish": "Return the final typed result. verified=true requires passing tests.",
}


def tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": TOOL_DESCRIPTIONS[name],
                "parameters": schema,
            },
        }
        for name, schema in TOOL_SCHEMAS.items()
    ]


def validate_arguments(name: str, arguments: dict[str, Any]) -> str | None:
    schema = TOOL_SCHEMAS.get(name)
    if schema is None:
        return f"unknown tool: {name}"
    if not isinstance(arguments, dict):
        return "arguments must be an object"
    allowed = set(schema["properties"])
    extra = set(arguments) - allowed
    if extra:
        return f"unexpected arguments: {sorted(extra)}"
    missing = set(schema["required"]) - set(arguments)
    if missing:
        return f"missing arguments: {sorted(missing)}"
    for key, value in arguments.items():
        expected = schema["properties"][key]["type"]
        valid = {
            "string": isinstance(value, str),
            "boolean": isinstance(value, bool),
            "array": isinstance(value, list),
        }.get(expected, True)
        if not valid:
            return f"{key} must be {expected}"
        if expected == "array" and not all(isinstance(item, str) for item in value):
            return f"all items in {key} must be strings"
    return None


class ToolRegistry:
    def __init__(
        self,
        workspace: Path,
        *,
        allow_write: bool = False,
        test_timeout_seconds: int = 20,
    ) -> None:
        self.workspace = workspace.resolve()
        self.allow_write = allow_write
        self.test_timeout_seconds = test_timeout_seconds

    def _safe_path(self, relative_path: str) -> Path:
        if not relative_path or Path(relative_path).is_absolute():
            raise ValueError("path must be non-empty and relative")
        candidate = (self.workspace / relative_path).resolve()
        try:
            candidate.relative_to(self.workspace)
        except ValueError as exc:
            raise ValueError("path escapes workspace") from exc
        return candidate

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolObservation:
        error = validate_arguments(name, arguments)
        if error:
            return ToolObservation(name, "invalid_arguments", {"error": error})
        try:
            if name == "list_files":
                return self._list_files(arguments["path"])
            if name == "read_file":
                return self._read_file(arguments["path"])
            if name == "run_tests":
                return self._run_tests(arguments["target"])
            if name == "replace_in_file":
                return self._replace_in_file(
                    arguments["path"], arguments["old"], arguments["new"]
                )
            return ToolObservation(name, "error", {"error": "tool is handled by runner"})
        except (OSError, UnicodeError, ValueError) as exc:
            return ToolObservation(name, "error", {"error": str(exc)})

    def _list_files(self, relative_path: str) -> ToolObservation:
        directory = self._safe_path(relative_path)
        if not directory.is_dir():
            raise ValueError("directory does not exist")
        ignored = {".git", ".venv", "__pycache__", ".pytest_cache"}
        files = [
            str(path.relative_to(self.workspace))
            for path in sorted(directory.rglob("*"))
            if path.is_file() and not any(part in ignored for part in path.parts)
        ][:200]
        return ToolObservation("list_files", "ok", {"files": files})

    def _read_file(self, relative_path: str) -> ToolObservation:
        path = self._safe_path(relative_path)
        if not path.is_file():
            raise ValueError("file does not exist")
        text = path.read_text(encoding="utf-8")
        truncated = len(text) > 12_000
        return ToolObservation(
            "read_file",
            "ok",
            {"path": relative_path, "content": text[:12_000], "truncated": truncated},
        )

    def _run_tests(self, target: str) -> ToolObservation:
        safe_target = self._safe_path(target)
        relative_target = str(safe_target.relative_to(self.workspace)) or "."
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", relative_target],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=self.test_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ToolObservation(
                "run_tests",
                "timeout",
                {"target": target, "timeout_seconds": self.test_timeout_seconds},
            )
        output = (completed.stdout + completed.stderr)[-12_000:]
        return ToolObservation(
            "run_tests",
            "ok",
            {
                "target": target,
                "exit_code": completed.returncode,
                "passed": completed.returncode == 0,
                "output": output,
            },
        )

    def _replace_in_file(self, relative_path: str, old: str, new: str) -> ToolObservation:
        path = self._safe_path(relative_path)
        if not path.is_file():
            raise ValueError("file does not exist")
        if not self.allow_write:
            return ToolObservation(
                "replace_in_file",
                "approval_required",
                {"path": relative_path, "preview": {"old": old, "new": new}},
            )
        text = path.read_text(encoding="utf-8")
        occurrences = text.count(old)
        if occurrences != 1:
            return ToolObservation(
                "replace_in_file",
                "rejected",
                {"error": f"expected exactly one occurrence, found {occurrences}"},
            )
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        return ToolObservation("replace_in_file", "ok", {"path": relative_path})


class OpenAICompatibleProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        api_key: str = "",
        timeout_seconds: int = 120,
    ) -> None:
        self.endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelTurn:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = requests.post(
            self.endpoint,
            headers=headers,
            json={
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "temperature": 0,
                "stream": False,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]
        calls: list[ToolCall] = []
        for raw in message.get("tool_calls") or []:
            function = raw.get("function") or {}
            arguments = function.get("arguments") or {}
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            calls.append(
                ToolCall(
                    call_id=raw.get("id") or f"call_{len(calls) + 1}",
                    name=function.get("name", ""),
                    arguments=arguments,
                )
            )
        return ModelTurn(content=message.get("content") or "", tool_calls=calls)


class ScriptedProvider:
    """Deterministic offline provider for a reliable classroom run."""

    def __init__(self) -> None:
        self.counter = 0

    def _call(self, name: str, arguments: dict[str, Any]) -> ModelTurn:
        self.counter += 1
        return ModelTurn(
            tool_calls=[ToolCall(f"scripted_{self.counter}", name, arguments)]
        )

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelTurn:
        observations: list[dict[str, Any]] = []
        for message in messages:
            if message.get("role") != "tool":
                continue
            try:
                observations.append(json.loads(message.get("content", "{}")))
            except json.JSONDecodeError:
                continue
        names = [item.get("tool") for item in observations]
        if "list_files" not in names:
            return self._call("list_files", {"path": "."})
        reads = [item.get("path") for item in observations if item.get("tool") == "read_file"]
        if "calculator.py" not in reads:
            return self._call("read_file", {"path": "calculator.py"})
        if "tests/test_calculator.py" not in reads:
            return self._call("read_file", {"path": "tests/test_calculator.py"})
        test_runs = [item for item in observations if item.get("tool") == "run_tests"]
        if not test_runs:
            return self._call("run_tests", {"target": "."})
        successful_edits = [
            item
            for item in observations
            if item.get("tool") == "replace_in_file" and item.get("status") == "ok"
        ]
        if not successful_edits:
            return self._call(
                "replace_in_file",
                {
                    "path": "calculator.py",
                    "old": "    return sum(numbers) / len(numbers)\n",
                    "new": (
                        "    if not numbers:\n"
                        "        return 0.0\n"
                        "    return sum(numbers) / len(numbers)\n"
                    ),
                },
            )
        if not any(item.get("passed") is True for item in test_runs):
            return self._call("run_tests", {"target": "."})
        return self._call(
            "finish",
            {
                "summary": "Handle an empty list explicitly and verify the change with pytest.",
                "changed_files": ["calculator.py"],
                "verified": True,
            },
        )


class AgentRunner:
    def __init__(
        self,
        provider: ModelProvider,
        registry: ToolRegistry,
        *,
        max_steps: int = 12,
    ) -> None:
        self.provider = provider
        self.registry = registry
        self.max_steps = max_steps

    def run(
        self,
        task: str,
        *,
        approval_callback: Callable[[ToolObservation], bool] | None = None,
    ) -> RunResult:
        state = AgentState(
            task=task,
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": task},
            ],
        )
        definitions = tool_definitions()

        for model_step in range(1, self.max_steps + 1):
            try:
                turn = self.provider.complete(state.messages, definitions)
            except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError) as exc:
                return RunResult("provider_error", str(exc), state)

            if not turn.tool_calls:
                state.trace.append(
                    {"step": model_step, "event": "model_text", "content": turn.content}
                )
                return RunResult(
                    "unverified_model_stop",
                    "Model stopped without the required finish tool.",
                    state,
                )

            state.messages.append(
                {
                    "role": "assistant",
                    "content": turn.content,
                    "tool_calls": [
                        {
                            "id": call.call_id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments, ensure_ascii=False),
                            },
                        }
                        for call in turn.tool_calls
                    ],
                }
            )

            for call in turn.tool_calls:
                if call.name == "finish":
                    error = validate_arguments("finish", call.arguments)
                    if error:
                        observation = ToolObservation(
                            "finish", "invalid_arguments", {"error": error}
                        )
                    elif call.arguments["verified"] and not state.last_tests_passed:
                        observation = ToolObservation(
                            "finish",
                            "rejected",
                            {"error": "verified=true requires observed passing tests"},
                        )
                    else:
                        state.trace.append(
                            {
                                "step": model_step,
                                "tool": "finish",
                                "arguments": call.arguments,
                                "status": "ok",
                            }
                        )
                        return RunResult(
                            "complete",
                            call.arguments["summary"],
                            state,
                            final=call.arguments,
                        )
                else:
                    observation = self.registry.execute(call.name, call.arguments)

                state.trace.append(
                    {
                        "step": model_step,
                        "tool": call.name,
                        "arguments": call.arguments,
                        "observation": observation.as_dict(),
                    }
                )
                state.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.call_id,
                        "content": observation.as_json(),
                    }
                )

                if call.name == "run_tests" and observation.status == "ok":
                    state.last_tests_passed = bool(observation.data.get("passed"))

                if observation.status == "approval_required":
                    if approval_callback and approval_callback(observation):
                        self.registry.allow_write = True
                        state.messages.append(
                            {
                                "role": "system",
                                "content": (
                                    "The user approved the proposed write for this run. "
                                    "Retry the exact write action, then verify with tests."
                                ),
                            }
                        )
                    else:
                        return RunResult(
                            "approval_required",
                            "Write action is waiting for approval.",
                            state,
                        )
                if observation.status in {"timeout"}:
                    return RunResult("tool_timeout", observation.as_json(), state)

        return RunResult(
            "max_steps",
            f"Stopped after {self.max_steps} model steps.",
            state,
        )


def print_result(result: RunResult) -> None:
    print(f"status: {result.status}")
    print(f"summary: {result.summary}")
    print("trace:")
    for item in result.state.trace:
        print(json.dumps(item, ensure_ascii=False))
    if result.final:
        print("final:")
        print(json.dumps(result.final, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal verified coding agent")
    parser.add_argument("--provider", choices=["scripted", "local"], default="scripted")
    parser.add_argument("--workspace", type=Path, default=Path(__file__).parent / "sample_repo")
    parser.add_argument(
        "--task",
        default="Fix average(): an empty list must return 0.0. Verify with tests.",
    )
    parser.add_argument("--approve", action="store_true", help="Approve write tools")
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--base-url", default=os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1"))
    parser.add_argument("--model", default=os.getenv("LOCAL_LLM_MODEL", "qwen3"))
    parser.add_argument("--api-key", default=os.getenv("LOCAL_LLM_API_KEY", ""))
    args = parser.parse_args()

    if args.provider == "scripted":
        provider: ModelProvider = ScriptedProvider()
    else:
        provider = OpenAICompatibleProvider(args.base_url, args.model, api_key=args.api_key)

    registry = ToolRegistry(args.workspace, allow_write=False)
    runner = AgentRunner(provider, registry, max_steps=args.max_steps)
    callback = (lambda observation: True) if args.approve else None
    result = runner.run(args.task, approval_callback=callback)
    print_result(result)
    return 0 if result.status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
