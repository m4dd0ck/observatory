"""The dashboard command must find the app inside the package and run it with this interpreter."""

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import observatory
from observatory.cli import app

runner = CliRunner()
PACKAGE_DIR = Path(observatory.__file__).parent


def test_dashboard_runs_streamlit_on_the_packaged_app(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], check: bool) -> SimpleNamespace:
        calls.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.invoke(app, ["dashboard", "--db", "results.db", "--port", "9000"])

    assert result.exit_code == 0
    command = calls[0]
    assert command[:4] == [sys.executable, "-m", "streamlit", "run"]
    assert Path(command[4]) == PACKAGE_DIR / "dashboard" / "app.py"
    assert Path(command[4]).is_file()
    assert command[5:] == ["--server.port", "9000", "--", "--db", "results.db"]


def test_dashboard_passes_streamlit_exit_code_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(subprocess, "run", lambda command, check: SimpleNamespace(returncode=3))

    result = runner.invoke(app, ["dashboard"])

    assert result.exit_code == 3


def test_dashboard_explains_the_missing_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)

    result = runner.invoke(app, ["dashboard"])

    assert result.exit_code == 1
    # Reason: Rich wraps the message at the runner's 80-column width
    assert "uv sync --extra dashboard" in " ".join(result.output.split())
