"""Lint floor — `ruff check .` must stay clean (config: pyproject.toml).

Skips (not fails) when ruff is not installed in the interpreter running the
suite. Added 2026-08-31 alongside the MarketReport equivalent.
"""
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_ruff_check_is_clean():
    probe = subprocess.run([sys.executable, "-m", "ruff", "--version"],
                           capture_output=True, text=True, cwd=REPO_ROOT)
    if probe.returncode != 0:
        pytest.skip("ruff not installed in this interpreter")
    result = subprocess.run([sys.executable, "-m", "ruff", "check", ".", "--output-format", "concise"],
                            capture_output=True, text=True, cwd=REPO_ROOT)
    assert result.returncode == 0, "ruff findings (run `python -m ruff check .`):\n" + result.stdout
