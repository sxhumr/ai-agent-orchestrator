"""Runs the real Claude Code CLI. Opt in with FORGEFLOW_LIVE=1 (makes a small paid call)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from forgeflow.config import AdapterConfig
from forgeflow.models.execution import RunStatus, TaskSpec
from forgeflow.runtime.claude_code import ClaudeCodeAdapter

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.environ.get("FORGEFLOW_LIVE") != "1", reason="set FORGEFLOW_LIVE=1"),
]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def test_bounded_file_creation(repo: Path) -> None:
    adapter = ClaudeCodeAdapter(AdapterConfig(timeout_s=180))
    result = adapter.run(
        TaskSpec(
            prompt="Create a file named hello.txt containing exactly the text: hi",
            workspace=repo,
            allowed_tools=["Write", "Read"],
            max_budget_usd=0.25,
        )
    )
    assert result.status is RunStatus.SUCCEEDED, result.error_details
    assert result.exit_code == 0
    assert result.session_id
    assert (repo / "hello.txt").read_text().strip() == "hi"


def test_disallowed_action_is_denied_not_hung(repo: Path) -> None:
    """With no tools allowed, a write attempt must be denied rather than block on a prompt."""
    adapter = ClaudeCodeAdapter(AdapterConfig(timeout_s=180))
    result = adapter.run(
        TaskSpec(
            prompt="Create a file named nope.txt containing: x. Do not ask for confirmation.",
            workspace=repo,
            allowed_tools=[],
            max_budget_usd=0.25,
        )
    )
    assert result.status is not RunStatus.TIMED_OUT
    assert not (repo / "nope.txt").exists()
