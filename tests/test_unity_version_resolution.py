"""
Tests for Unity version resolution.

Covers the resolver script (scripts/common/resolve_unity_version.sh) and
the canonical config (config/unity-build-defaults.json).

Precedence verified:
  1. UNITY_VERSION_INPUT env var (explicit override) — wins over config default
  2. No input → reads .unityVersion from config/unity-build-defaults.json
  3. Missing/empty config + no input → fails with non-zero exit and error on stderr
  4. Resolved value is exactly the version string (no extra log noise on stdout)

Also verifies config/unity-build-defaults.json imageVariants are correct.
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
RESOLVER_SCRIPT = REPO_ROOT / "scripts" / "common" / "resolve_unity_version.sh"
CONFIG_FILE = REPO_ROOT / "config" / "unity-build-defaults.json"


def run_resolver(env_overrides: dict, config_path: str | None = None, timeout: int = 10) -> subprocess.CompletedProcess:
    """Run the Unity version resolver with a controlled environment."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
    }
    env.update(env_overrides)

    # If a custom config path is provided, patch the script to use it by
    # injecting REPO_ROOT_OVERRIDE so we can write isolated temp configs.
    # Since the script computes CONFIG_FILE relative to SCRIPT_DIR, we test
    # by temporarily symlinking or by passing the version via env.
    # Simpler approach: the script respects UNITY_VERSION_INPUT which is the
    # override path; for config-path tests we use a wrapper approach.
    return subprocess.run(
        ["bash", str(RESOLVER_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


@pytest.fixture(autouse=True)
def _check_script_exists():
    """Skip all tests if the resolver script does not exist."""
    if not RESOLVER_SCRIPT.exists():
        pytest.skip(f"Resolver script not found: {RESOLVER_SCRIPT}")


# ── Case 1: Explicit input wins ──────────────────────────────────────────────

class TestExplicitInputWins:
    def test_explicit_input_overrides_config(self):
        """UNITY_VERSION_INPUT takes priority over the config default."""
        result = run_resolver({"UNITY_VERSION_INPUT": "2022.3.99f1"})
        assert result.returncode == 0
        assert result.stdout.strip() == "2022.3.99f1"

    def test_explicit_input_is_exact_on_stdout(self):
        """stdout contains only the version string, nothing else."""
        result = run_resolver({"UNITY_VERSION_INPUT": "6000.1.0f1"})
        assert result.returncode == 0
        assert result.stdout.strip() == "6000.1.0f1"
        # No extra tokens on stdout (log lines go to stderr)
        stdout_lines = [l for l in result.stdout.splitlines() if l.strip()]
        assert len(stdout_lines) == 1

    def test_explicit_input_logs_source_to_stderr(self):
        """The resolver should log where the version came from (to stderr)."""
        result = run_resolver({"UNITY_VERSION_INPUT": "6000.0.26f1"})
        assert "UNITY_VERSION_INPUT" in result.stderr


# ── Case 2: No input → reads from config ────────────────────────────────────

class TestConfigFallback:
    def test_reads_config_default(self):
        """With no input, resolver reads .unityVersion from the config file."""
        result = run_resolver({})
        assert result.returncode == 0
        version = result.stdout.strip()
        # Must be a non-empty version-like string
        assert version, "Expected a version string on stdout"
        # Rough format check: X.Y.Zf1 or similar
        assert "." in version and len(version) >= 5

    def test_config_default_matches_known_value(self):
        """The default version should match what's in the config file."""
        with open(CONFIG_FILE) as f:
            config = json.load(f)
        expected = config["unityVersion"]

        result = run_resolver({})
        assert result.returncode == 0
        assert result.stdout.strip() == expected

    def test_config_fallback_logs_config_path_to_stderr(self):
        """Resolver should mention the config file path in its stderr log."""
        result = run_resolver({})
        # The log should mention the config file
        assert "unity-build-defaults.json" in result.stderr


# ── Case 3: No input + missing/empty config → fails clearly ─────────────────

class TestMissingConfigFails:
    def test_nonexistent_config_returns_nonzero(self):
        """If the config file is missing and there is no input, exit code must be non-zero."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a minimal fake repo structure with NO config file
            fake_scripts_common = Path(tmpdir) / "scripts" / "common"
            fake_scripts_common.mkdir(parents=True)
            fake_config_dir = Path(tmpdir) / "config"
            # Intentionally do NOT create fake_config_dir/unity-build-defaults.json

            # Write a minimal clone of the resolver that uses tmpdir as repo root
            wrapper = Path(tmpdir) / "wrapper.sh"
            wrapper.write_text(
                "#!/usr/bin/env bash\n"
                "set -Eeuo pipefail\n"
                f"export SCRIPT_DIR='{fake_scripts_common}'\n"
                f"export REPO_ROOT='{tmpdir}'\n"
                # Source the real resolver logic but with overridden CONFIG_FILE
                # Easier: just override CONFIG_FILE via env and run the real script
                # The real script computes CONFIG_FILE from SCRIPT_DIR — we can't
                # override it via env directly. Instead, we point to a non-existent path
                # by symlinking the script into fake_scripts_common.
            )

            # Symlink the real script into fake_scripts_common so SCRIPT_DIR resolves
            # to fake_scripts_common, making REPO_ROOT = tmpdir (no config there)
            import shutil
            shutil.copy(str(RESOLVER_SCRIPT), str(fake_scripts_common / "resolve_unity_version.sh"))

            env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": os.environ.get("HOME", "/tmp"),
            }
            result = subprocess.run(
                ["bash", str(fake_scripts_common / "resolve_unity_version.sh")],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )
        assert result.returncode != 0, "Expected non-zero exit when config is missing"

    def test_missing_config_error_mentions_config_path(self):
        """The error output should name the config path for the user."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import shutil
            fake_scripts_common = Path(tmpdir) / "scripts" / "common"
            fake_scripts_common.mkdir(parents=True)
            shutil.copy(str(RESOLVER_SCRIPT), str(fake_scripts_common / "resolve_unity_version.sh"))

            env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": os.environ.get("HOME", "/tmp"),
            }
            result = subprocess.run(
                ["bash", str(fake_scripts_common / "resolve_unity_version.sh")],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )
        assert result.returncode != 0
        assert "unity-build-defaults.json" in result.stderr or "config" in result.stderr.lower()

    def test_empty_config_file_returns_nonzero(self):
        """A config file with no 'unityVersion' field causes a non-zero exit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import shutil
            fake_scripts_common = Path(tmpdir) / "scripts" / "common"
            fake_scripts_common.mkdir(parents=True)
            fake_config_dir = Path(tmpdir) / "config"
            fake_config_dir.mkdir()
            # Write a config file missing the unityVersion key
            (fake_config_dir / "unity-build-defaults.json").write_text(
                '{"imageVariants": ["android"]}\n'
            )
            shutil.copy(str(RESOLVER_SCRIPT), str(fake_scripts_common / "resolve_unity_version.sh"))

            env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": os.environ.get("HOME", "/tmp"),
            }
            result = subprocess.run(
                ["bash", str(fake_scripts_common / "resolve_unity_version.sh")],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )
        assert result.returncode != 0


# ── Case 4: stdout cleanliness ───────────────────────────────────────────────

class TestStdoutCleanliness:
    """Verify that stdout contains only the version string — log goes to stderr."""

    def test_no_log_prefix_on_stdout(self):
        result = run_resolver({})
        assert result.returncode == 0
        # Log lines from log_info contain a timestamp bracket pattern
        assert "[INFO]" not in result.stdout
        assert "[WARN]" not in result.stdout
        assert "[ERROR]" not in result.stdout

    def test_single_line_on_stdout(self):
        result = run_resolver({"UNITY_VERSION_INPUT": "6000.0.26f1"})
        assert result.returncode == 0
        non_empty = [l for l in result.stdout.splitlines() if l.strip()]
        assert len(non_empty) == 1


# ── Config: imageVariants assertion ─────────────────────────────────────────

class TestConfigImageVariants:
    """Validate the canonical config file content."""

    def test_config_file_exists(self):
        assert CONFIG_FILE.exists(), f"Config file not found: {CONFIG_FILE}"

    def test_image_variants_are_correct(self):
        with open(CONFIG_FILE) as f:
            config = json.load(f)
        assert config["imageVariants"] == ["android", "webgl", "linux"]

    def test_config_has_required_fields(self):
        with open(CONFIG_FILE) as f:
            config = json.load(f)
        required_fields = ["unityVersion", "unityChangeset", "imageVariants", "registry", "imageNamespace"]
        for field in required_fields:
            assert field in config, f"Missing required field in config: {field}"

    def test_unity_version_format(self):
        with open(CONFIG_FILE) as f:
            config = json.load(f)
        version = config["unityVersion"]
        # Must look like X.Y.Zf1 (Unity version format)
        assert "." in version
        assert "f" in version or "a" in version or "b" in version

    def test_changeset_is_hex(self):
        with open(CONFIG_FILE) as f:
            config = json.load(f)
        changeset = config["unityChangeset"]
        assert len(changeset) == 12, f"Changeset should be 12 hex chars, got: {changeset!r}"
        int(changeset, 16)  # Raises ValueError if not valid hex
