from __future__ import annotations

import json
from pathlib import Path

import pytest

from forgeflow import cli
from tests.unit.helpers import BRIEF, FakeAdapter, valid_output


@pytest.fixture
def ff(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    db = tmp_path / "cli.db"

    def run(*args: str) -> tuple[int, str, str]:
        code = cli.main(["--db", str(db), *args])
        out, err = capsys.readouterr()
        return code, out, err

    return run


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    return root


def test_requirements_workflow(ff, project_dir: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cli, "ClaudeCodeAdapter", lambda _cfg: FakeAdapter(valid_output()))
    brief_file = tmp_path / "brief.md"
    brief_file.write_text(BRIEF)

    assert ff("project", "create", "acme", "--root", str(project_dir))[0] == 0
    assert ff("brief", "add", "acme", "--file", str(brief_file))[0] == 0

    code, out, _ = ff("requirements", "generate", "acme")
    assert code == 0
    assert "4 requirements and 3 open items from brief v1" in out
    assert "not found verbatim: REQ-004" in out

    code, out, _ = ff(
        "req",
        "edit",
        "acme",
        "REQ-003",
        "--criterion",
        "LCP < 2.5s on 4G",
        "--status",
        "accepted",
        "--note",
        "threshold agreed",
    )
    assert code == 0 and "REQ-003 is now v2" in out

    code, out, _ = ff("req", "history", "acme", "REQ-003")
    assert "v1" in out and "v2" in out and "threshold agreed" in out

    code, out, _ = ff("req", "show", "acme", "REQ-003")
    assert "AC-1  LCP < 2.5s on 4G" in out
    assert "Q-001 [open]" in out

    code, out, _ = ff("q", "resolve", "acme", "Q-001", "--answer", "2.5s LCP", "--by", "dev")
    assert code == 0 and "2 open item(s) remaining" in out

    code, out, _ = ff(
        "req",
        "add",
        "acme",
        "--title",
        "Audit log",
        "--description",
        "Log it",
        "--criterion",
        "Every booking change is logged",
    )
    assert "added REQ-005" in out

    code, out, _ = ff("req", "list", "acme", "--json")
    data = json.loads(out)
    assert [r["key"] for r in data] == ["REQ-001", "REQ-002", "REQ-003", "REQ-004", "REQ-005"]
    assert data[2]["status"] == "accepted"
    assert data[4]["origin"] == "developer"

    code, out, _ = ff("q", "list", "acme", "--all")
    assert "resolution (dev): 2.5s LCP" in out

    code, out, _ = ff("project", "show", "acme")
    assert "requirements: 5" in out and "open items:   2" in out

    out_dir = tmp_path / "export"
    assert ff("req", "export", "acme", "--out", str(out_dir))[0] == 0
    assert "REQ-005 — Audit log" in (out_dir / "requirements.md").read_text()
    exported = json.loads((out_dir / "requirements.json").read_text())
    assert len(exported["open_items"]) == 3


def test_errors_exit_nonzero(ff, project_dir: Path, tmp_path: Path) -> None:
    code, _, err = ff("req", "list", "missing")
    assert code == 1 and "no project named 'missing'" in err

    code, _, err = ff("project", "create", "x", "--root", str(tmp_path / "nope"))
    assert code == 1 and "not an existing directory" in err

    code, _, err = ff("project", "create", "bad name", "--root", str(project_dir))
    assert code == 1 and "invalid input" in err

    ff("project", "create", "acme", "--root", str(project_dir))
    code, _, err = ff("req", "edit", "acme", "REQ-001", "--title", "x")
    assert code == 1 and "no requirement REQ-001" in err

    code, _, err = ff("brief", "add", "acme", "--text", "   ")
    assert code == 1 and "brief is empty" in err


def test_generate_failure_reports_error(ff, project_dir: Path, monkeypatch) -> None:
    monkeypatch.setattr(cli, "ClaudeCodeAdapter", lambda _cfg: FakeAdapter({"summary": "x"}))
    ff("project", "create", "acme", "--root", str(project_dir))
    ff("brief", "add", "acme", "--text", BRIEF)
    code, _, err = ff("req", "generate", "acme")
    assert code == 1 and "failed validation" in err
