"""Tests for scripts/common/resolve_platform_matrix.py

Verifies:
- platform=All → all Docker platforms + iOS
- platform=Android → only Android in docker list, no iOS
- platform=WebGL → only WebGL, no iOS
- platform=Linux64 → only Linux64, no iOS
- platform=LinuxServer → only LinuxServer, no iOS
- platform=iOS → empty docker list, run_ios=True
- unsupported platform → raises ValueError
- empty docker matrix is valid JSON (for GitHub Actions matrix fromJson)
- output-format=json produces valid JSON
- GITHUB_OUTPUT is written when present
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "common" / "resolve_platform_matrix.py"

# ── Import the module directly for unit tests ─────────────────────────────────
sys.path.insert(0, str(SCRIPT.parent))
from resolve_platform_matrix import resolve, DOCKER_PLATFORMS, IOS_PLATFORM  # noqa: E402


# ── Unit tests (import-level) ─────────────────────────────────────────────────

class TestResolveFunction:
    def test_all_returns_all_docker_platforms_and_ios(self):
        docker, run_ios = resolve("All")
        assert docker == list(DOCKER_PLATFORMS)
        assert run_ios is True

    def test_android_returns_only_android_no_ios(self):
        docker, run_ios = resolve("Android")
        assert docker == ["Android"]
        assert run_ios is False

    def test_webgl_returns_only_webgl_no_ios(self):
        docker, run_ios = resolve("WebGL")
        assert docker == ["WebGL"]
        assert run_ios is False

    def test_linux64_returns_only_linux64_no_ios(self):
        docker, run_ios = resolve("Linux64")
        assert docker == ["Linux64"]
        assert run_ios is False

    def test_linuxserver_returns_only_linuxserver_no_ios(self):
        docker, run_ios = resolve("LinuxServer")
        assert docker == ["LinuxServer"]
        assert run_ios is False

    def test_ios_returns_empty_docker_and_run_ios_true(self):
        docker, run_ios = resolve("iOS")
        assert docker == []
        assert run_ios is True

    def test_unsupported_platform_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported platform"):
            resolve("Windows")

    def test_unsupported_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            resolve("")

    def test_case_sensitive_android(self):
        """Platform names are case-sensitive — 'android' != 'Android'."""
        with pytest.raises(ValueError):
            resolve("android")

    def test_empty_docker_list_is_valid_json(self):
        """Empty matrix must be valid JSON for GitHub Actions fromJson()."""
        docker, _ = resolve("iOS")
        dumped = json.dumps(docker)
        assert json.loads(dumped) == []

    def test_docker_platforms_are_json_serializable(self):
        for plat in list(DOCKER_PLATFORMS) + ["All"]:
            docker, _ = resolve(plat)
            loaded = json.loads(json.dumps(docker))
            assert isinstance(loaded, list)


# ── CLI integration tests (subprocess) ───────────────────────────────────────

def run_script(args: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    """Run resolve_platform_matrix.py as a subprocess."""
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


class TestCLIJsonFormat:
    def test_json_output_all(self):
        result = run_script(["--platform", "All", "--output-format", "json"])
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["docker-platforms"] == ["Android", "WebGL", "Linux64", "LinuxServer"]
        assert data["run-ios"] is True

    def test_json_output_ios(self):
        result = run_script(["--platform", "iOS", "--output-format", "json"])
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["docker-platforms"] == []
        assert data["run-ios"] is True

    def test_json_output_android(self):
        result = run_script(["--platform", "Android", "--output-format", "json"])
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["docker-platforms"] == ["Android"]
        assert data["run-ios"] is False

    def test_unsupported_platform_exits_nonzero(self):
        result = run_script(["--platform", "PS5", "--output-format", "json"])
        assert result.returncode != 0
        assert "Unsupported platform" in result.stderr


class TestCLIGitHubActionsFormat:
    def test_github_actions_output_all(self):
        result = run_script(["--platform", "All", "--output-format", "github-actions"])
        assert result.returncode == 0
        stdout = result.stdout
        assert 'docker-platforms=["Android","WebGL","Linux64","LinuxServer"]' in stdout
        assert "run-ios=true" in stdout

    def test_github_actions_output_ios(self):
        result = run_script(["--platform", "iOS", "--output-format", "github-actions"])
        assert result.returncode == 0
        assert "docker-platforms=[]" in result.stdout
        assert "run-ios=true" in result.stdout

    def test_github_actions_output_android(self):
        result = run_script(["--platform", "Android", "--output-format", "github-actions"])
        assert result.returncode == 0
        assert 'docker-platforms=["Android"]' in result.stdout
        assert "run-ios=false" in result.stdout

    def test_github_actions_writes_to_github_output_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            result = run_script(
                ["--platform", "Android", "--output-format", "github-actions"],
                env={"GITHUB_OUTPUT": tmp_path},
            )
            assert result.returncode == 0
            content = Path(tmp_path).read_text()
            assert 'docker-platforms=["Android"]' in content
            assert "run-ios=false" in content
        finally:
            os.unlink(tmp_path)

    def test_github_actions_ios_writes_empty_docker_platforms(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            run_script(
                ["--platform", "iOS", "--output-format", "github-actions"],
                env={"GITHUB_OUTPUT": tmp_path},
            )
            content = Path(tmp_path).read_text()
            assert "docker-platforms=[]" in content
            assert "run-ios=true" in content
        finally:
            os.unlink(tmp_path)


# ── Matrix contract tests ─────────────────────────────────────────────────────

class TestMatrixContract:
    """Verify docker-platforms output is a valid GitHub Actions matrix input."""

    @pytest.mark.parametrize("platform,expected_docker", [
        ("All",         ["Android", "WebGL", "Linux64", "LinuxServer"]),
        ("Android",     ["Android"]),
        ("WebGL",       ["WebGL"]),
        ("Linux64",     ["Linux64"]),
        ("LinuxServer", ["LinuxServer"]),
        ("iOS",         []),
    ])
    def test_docker_platforms_match_expected(self, platform, expected_docker):
        docker, _ = resolve(platform)
        assert docker == expected_docker

    @pytest.mark.parametrize("platform,expected_ios", [
        ("All",         True),
        ("Android",     False),
        ("WebGL",       False),
        ("Linux64",     False),
        ("LinuxServer", False),
        ("iOS",         True),
    ])
    def test_run_ios_flag(self, platform, expected_ios):
        _, run_ios = resolve(platform)
        assert run_ios is expected_ios

    def test_empty_matrix_is_valid_json_array(self):
        """GitHub Actions fromJson('[]') must not raise errors."""
        docker, _ = resolve("iOS")
        serialized = json.dumps(docker)
        assert serialized == "[]"
        assert json.loads(serialized) == []

    def test_all_docker_platforms_are_strings(self):
        docker, _ = resolve("All")
        assert all(isinstance(p, str) for p in docker)

    def test_no_ios_in_docker_platforms(self):
        """iOS must never appear in the docker_platforms list."""
        for platform in ["All", "Android", "WebGL", "Linux64", "LinuxServer"]:
            docker, _ = resolve(platform)
            assert "iOS" not in docker, f"iOS found in docker_platforms for platform={platform}"
