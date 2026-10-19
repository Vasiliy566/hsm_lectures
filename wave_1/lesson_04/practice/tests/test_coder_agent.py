from __future__ import annotations

import shutil
from pathlib import Path

from coder_agent import AgentRunner, ScriptedProvider, ToolRegistry


SAMPLE_REPO = Path(__file__).parents[1] / "sample_repo"


def copy_repo(tmp_path: Path) -> Path:
    target = tmp_path / "repo"
    shutil.copytree(SAMPLE_REPO, target)
    return target


def test_path_escape_is_blocked(tmp_path: Path) -> None:
    repo = copy_repo(tmp_path)
    result = ToolRegistry(repo).execute("read_file", {"path": "../secret.txt"})
    assert result.status == "error"
    assert "escapes workspace" in result.data["error"]


def test_write_requires_approval(tmp_path: Path) -> None:
    repo = copy_repo(tmp_path)
    result = ToolRegistry(repo).execute(
        "replace_in_file",
        {
            "path": "calculator.py",
            "old": "return sum(numbers) / len(numbers)",
            "new": "return 0.0",
        },
    )
    assert result.status == "approval_required"


def test_scripted_agent_stops_without_approval(tmp_path: Path) -> None:
    repo = copy_repo(tmp_path)
    runner = AgentRunner(ScriptedProvider(), ToolRegistry(repo))
    result = runner.run("Fix the empty-list bug")
    assert result.status == "approval_required"
    assert "if not numbers" not in (repo / "calculator.py").read_text()


def test_scripted_agent_fixes_and_verifies(tmp_path: Path) -> None:
    repo = copy_repo(tmp_path)
    runner = AgentRunner(ScriptedProvider(), ToolRegistry(repo))
    result = runner.run("Fix the empty-list bug", approval_callback=lambda _: True)
    assert result.status == "complete"
    assert result.final and result.final["verified"] is True
    assert "if not numbers" in (repo / "calculator.py").read_text()
    test_observations = [
        item["observation"]
        for item in result.state.trace
        if item.get("tool") == "run_tests"
    ]
    assert test_observations[0]["passed"] is False
    assert test_observations[-1]["passed"] is True
