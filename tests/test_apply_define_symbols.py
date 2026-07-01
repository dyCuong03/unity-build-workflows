"""
test_apply_define_symbols.py
============================
Validates scripts/common/apply_define_symbols.sh — the build-time injector that
merges per-branch Scripting Define Symbols into ProjectSettings.asset.

Contract
--------
A1  empty DEFINE_SYMBOLS → file unchanged, exit 0
A2  symbols appended (additive) to every platform group under the block
A3  existing symbols preserved; no duplicates added (idempotent)
A4  ',' and ';' separators both accepted; whitespace trimmed
A5  content OUTSIDE the scriptingDefineSymbols block is never touched
A6  missing block / missing file → warning, exit 0, no crash
A7  group keys containing spaces (e.g. "Nintendo Switch") handled
"""

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "common" / "apply_define_symbols.sh"

ASSET = """\
PlayerSettings:
  m_Something: 1
  scriptingDefineSymbols:
    Android: ODIN_INSPECTOR;DOTWEEN
    Nintendo Switch: DOTWEEN
    Standalone: DOTWEEN
    WebGL:
  additionalCompilerArguments: {}
  m_After: 2
"""


@pytest.fixture(autouse=True)
def _require_script():
    if not SCRIPT.exists():
        pytest.skip(f"apply script not found: {SCRIPT}")


def run_apply(project_path: Path, symbols, timeout: int = 10):
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "PROJECT_PATH": str(project_path),
    }
    if symbols is not None:
        env["DEFINE_SYMBOLS"] = symbols
    return subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, timeout=timeout, env=env
    )


def _project(tmp_path: Path, content: str = ASSET) -> Path:
    ps_dir = tmp_path / "ProjectSettings"
    ps_dir.mkdir()
    (ps_dir / "ProjectSettings.asset").write_text(content)
    return tmp_path


def _asset(project: Path) -> str:
    return (project / "ProjectSettings" / "ProjectSettings.asset").read_text()


def _group(asset: str, key: str) -> str:
    for line in asset.splitlines():
        s = line.strip()
        if s.startswith(f"{key}:"):
            return s[len(key) + 1:].strip()
    raise AssertionError(f"group {key!r} not found")


class TestApplyDefineSymbols:
    def test_empty_is_noop(self, tmp_path):
        proj = _project(tmp_path)
        before = _asset(proj)
        r = run_apply(proj, "")
        assert r.returncode == 0
        assert _asset(proj) == before

    def test_unset_is_noop(self, tmp_path):
        proj = _project(tmp_path)
        before = _asset(proj)
        r = run_apply(proj, None)
        assert r.returncode == 0
        assert _asset(proj) == before

    def test_appends_to_every_group(self, tmp_path):
        proj = _project(tmp_path)
        assert run_apply(proj, "STAGING").returncode == 0
        asset = _asset(proj)
        for key in ("Android", "Nintendo Switch", "Standalone"):
            assert "STAGING" in _group(asset, key)

    def test_empty_group_gets_symbol(self, tmp_path):
        proj = _project(tmp_path)
        run_apply(proj, "STAGING")
        assert _group(_asset(proj), "WebGL") == "STAGING"

    def test_preserves_existing_and_dedups(self, tmp_path):
        proj = _project(tmp_path)
        run_apply(proj, "DOTWEEN;STAGING")
        android = _group(_asset(proj), "Android")
        assert "ODIN_INSPECTOR" in android
        assert android.split(";").count("DOTWEEN") == 1
        assert "STAGING" in android

    def test_idempotent(self, tmp_path):
        proj = _project(tmp_path)
        run_apply(proj, "STAGING;PROFILER")
        first = _asset(proj)
        run_apply(proj, "STAGING;PROFILER")
        assert _asset(proj) == first

    def test_comma_separator_and_whitespace(self, tmp_path):
        proj = _project(tmp_path)
        run_apply(proj, " A , B ;C ")
        android = _group(_asset(proj), "Android")
        for sym in ("A", "B", "C"):
            assert sym in android.split(";")

    def test_outside_block_untouched(self, tmp_path):
        proj = _project(tmp_path)
        run_apply(proj, "STAGING")
        asset = _asset(proj)
        assert "  m_Something: 1" in asset
        assert "  additionalCompilerArguments: {}" in asset
        assert "  m_After: 2" in asset
        # the trailing root keys must NOT have gained symbols
        assert "STAGING" not in _group(asset, "additionalCompilerArguments")

    def test_missing_block_is_noop(self, tmp_path):
        proj = _project(tmp_path, "PlayerSettings:\n  m_X: 1\n")
        before = _asset(proj)
        r = run_apply(proj, "STAGING")
        assert r.returncode == 0
        assert _asset(proj) == before

    def test_missing_file_exits_zero(self, tmp_path):
        r = run_apply(tmp_path, "STAGING")  # no ProjectSettings dir
        assert r.returncode == 0
