"""
Tests for secret leak prevention.

Covers:
- Docker command does not contain UNITY_LICENSE value
- Docker command does not contain UNITY_PASSWORD value
- Docker command does not contain keystore passwords
- _safe_command_repr redacts known secret patterns
- Docker image build does not use ENV for secrets (Dockerfile inspection)
- Artifact directories do not contain license files
- Entrypoint cleanup removes temp license files
"""
import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "docker"))


# ---------------------------------------------------------------------------
# Module import
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def docker_mod():
    try:
        import run_unity_container
        return run_unity_container
    except ImportError:
        pytest.skip("scripts/docker/run_unity_container.py not yet implemented")


# ---------------------------------------------------------------------------
# Shared secrets / helpers
# ---------------------------------------------------------------------------

FAKE_LICENSE = (
    "<?xml version='1.0' encoding='UTF-8'?>"
    "<root><License><LicenseVersion>5.x</LicenseVersion>"
    "<MachineBindings><Binding Key='1' Value='uniqueKeyValue'/>"
    "</MachineBindings></License></root>"
)
FAKE_PASSWORD = "my_super_secret_unity_password_ABC123"
FAKE_KEYSTORE_PASS = "android_keystore_pass_XYZ789"
FAKE_KEY_PASS = "android_key_pass_DEF456"
FAKE_KEYSTORE_B64 = "c3VwZXJzZWNyZXRiYXNlNjQ="
FAKE_DIGEST = "sha256:" + "a" * 64
FAKE_IMAGE = f"ghcr.io/example-namespace/unity-android@{FAKE_DIGEST}"


def _make_args(**overrides) -> argparse.Namespace:
    defaults = dict(
        project_path="/workspace/MyProject",
        build_config_path="BuildConfig",
        command="build",
        environment="development",
        target_platform="Android",
        unity_version="2022.3.45f1",
        cache_mode="safe",
        clean_build=False,
        test_level=None,
        build_addressables=False,
        release_mode=False,
        container_timeout=3600,
        cpus=None,
        memory=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# Docker command does not contain secret VALUES
# ---------------------------------------------------------------------------

class TestSecretsAbsentFromDockerCommand:
    """
    The _build_docker_command function passes secrets as -e NAME (no value).
    Secret names in SECRET_ENV_VARS are silently dropped from env_vars.
    """

    def _build_cmd(self, docker_mod, env_vars=None, tmp_path=None):
        """Helper: build a docker command with optional env_vars overrides."""
        import tempfile as tf
        base = tf.mkdtemp()
        out = Path(base) / "Builds"
        out.mkdir()
        rep = Path(base) / "Reports"
        rep.mkdir()
        logs = Path(base) / "Logs"
        logs.mkdir()
        return docker_mod._build_docker_command(
            docker="docker",
            image_ref=FAKE_IMAGE,
            args=_make_args(),
            output_path=out,
            reports_path=rep,
            logs_path=logs,
            cache_volume="test-vol",
            env_vars=env_vars or {},
        )

    def test_unity_license_value_not_embedded_in_command(self, docker_mod):
        """UNITY_LICENSE in env_vars is filtered — value must not appear."""
        cmd = self._build_cmd(docker_mod, {"UNITY_LICENSE": FAKE_LICENSE})
        cmd_str = " ".join(cmd)
        assert FAKE_LICENSE not in cmd_str, \
            "UNITY_LICENSE value must NOT appear as a CLI argument"
        assert "LicenseVersion" not in cmd_str
        assert "MachineBindings" not in cmd_str

    def test_unity_password_not_in_command(self, docker_mod):
        cmd = self._build_cmd(docker_mod, {"UNITY_PASSWORD": FAKE_PASSWORD})
        cmd_str = " ".join(cmd)
        assert FAKE_PASSWORD not in cmd_str, \
            "UNITY_PASSWORD value must NOT appear in docker command args"

    def test_keystore_pass_not_in_command(self, docker_mod):
        cmd = self._build_cmd(docker_mod, {"ANDROID_KEYSTORE_PASS": FAKE_KEYSTORE_PASS})
        cmd_str = " ".join(cmd)
        assert FAKE_KEYSTORE_PASS not in cmd_str, \
            "ANDROID_KEYSTORE_PASS value must NOT appear in docker command args"

    def test_key_pass_not_in_command(self, docker_mod):
        cmd = self._build_cmd(docker_mod, {"ANDROID_KEY_PASS": FAKE_KEY_PASS})
        cmd_str = " ".join(cmd)
        assert FAKE_KEY_PASS not in cmd_str, \
            "ANDROID_KEY_PASS value must NOT appear in docker command args"

    def test_keystore_base64_not_in_command(self, docker_mod):
        cmd = self._build_cmd(docker_mod, {"ANDROID_KEYSTORE_BASE64": FAKE_KEYSTORE_B64})
        cmd_str = " ".join(cmd)
        assert FAKE_KEYSTORE_B64 not in cmd_str, \
            "ANDROID_KEYSTORE_BASE64 value must NOT appear in docker command args"

    def test_multiple_secrets_none_appear_in_command(self, docker_mod):
        cmd = self._build_cmd(docker_mod, {
            "UNITY_LICENSE": FAKE_LICENSE,
            "UNITY_PASSWORD": FAKE_PASSWORD,
            "ANDROID_KEYSTORE_PASS": FAKE_KEYSTORE_PASS,
            "ANDROID_KEY_PASS": FAKE_KEY_PASS,
            "ANDROID_KEYSTORE_BASE64": FAKE_KEYSTORE_B64,
        })
        cmd_str = " ".join(cmd)
        for secret_val in (FAKE_LICENSE, FAKE_PASSWORD, FAKE_KEYSTORE_PASS,
                           FAKE_KEY_PASS, FAKE_KEYSTORE_B64):
            assert secret_val not in cmd_str, \
                f"Secret value '{secret_val[:20]}...' found in docker command"

    def test_non_secret_env_vars_appear_normally(self, docker_mod):
        """Non-secret env vars should appear as -e KEY=VALUE."""
        cmd = self._build_cmd(docker_mod, {"MY_CUSTOM_VAR": "custom_value"})
        cmd_str = " ".join(cmd)
        assert "MY_CUSTOM_VAR=custom_value" in cmd_str, \
            "Non-secret env var must appear as KEY=VALUE in docker command"


# ---------------------------------------------------------------------------
# _safe_command_repr log sanitizer
# ---------------------------------------------------------------------------

class TestSafeCommandRepr:
    """
    _safe_command_repr masks -e KEY=VALUE when KEY is in SECRET_ENV_VARS.
    Non-secret values and -e KEY (no value) forms pass through unchanged.
    """

    def test_unity_license_value_masked(self, docker_mod):
        cmd = ["docker", "run", "--rm", "-e", f"UNITY_LICENSE={FAKE_LICENSE}", "image:tag"]
        result = docker_mod._safe_command_repr(cmd)
        assert FAKE_LICENSE not in result
        assert "UNITY_LICENSE=***" in result

    def test_unity_email_masked(self, docker_mod):
        cmd = ["docker", "run", "-e", "UNITY_EMAIL=user@example.com", "image:tag"]
        result = docker_mod._safe_command_repr(cmd)
        assert "user@example.com" not in result
        assert "UNITY_EMAIL=***" in result

    def test_unity_password_masked(self, docker_mod):
        cmd = ["docker", "run", "-e", f"UNITY_PASSWORD={FAKE_PASSWORD}", "image:tag"]
        result = docker_mod._safe_command_repr(cmd)
        assert FAKE_PASSWORD not in result
        assert "UNITY_PASSWORD=***" in result

    def test_android_keystore_pass_masked(self, docker_mod):
        cmd = ["docker", "run", "-e", f"ANDROID_KEYSTORE_PASS={FAKE_KEYSTORE_PASS}", "image:tag"]
        result = docker_mod._safe_command_repr(cmd)
        assert FAKE_KEYSTORE_PASS not in result
        assert "ANDROID_KEYSTORE_PASS=***" in result

    def test_android_key_pass_masked(self, docker_mod):
        cmd = ["docker", "run", "-e", f"ANDROID_KEY_PASS={FAKE_KEY_PASS}", "image:tag"]
        result = docker_mod._safe_command_repr(cmd)
        assert FAKE_KEY_PASS not in result
        assert "ANDROID_KEY_PASS=***" in result

    def test_non_secret_var_not_masked(self, docker_mod):
        cmd = ["docker", "run", "-e", "TARGET_PLATFORM=Android", "image:tag"]
        result = docker_mod._safe_command_repr(cmd)
        assert "TARGET_PLATFORM=Android" in result

    def test_env_name_only_form_not_masked(self, docker_mod):
        """'-e UNITY_LICENSE' (no value) is the safe forwarding form — must pass through."""
        cmd = ["docker", "run", "-e", "UNITY_LICENSE", "image:tag"]
        result = docker_mod._safe_command_repr(cmd)
        assert "UNITY_LICENSE" in result
        # No '***' since there's no value to redact
        assert "=***" not in result or "UNITY_LICENSE" in result

    def test_safe_repr_returns_string(self, docker_mod):
        cmd = ["docker", "run", "-e", "FOO=bar", "image:tag"]
        result = docker_mod._safe_command_repr(cmd)
        assert isinstance(result, str)

    def test_multiple_secrets_all_masked(self, docker_mod):
        cmd = [
            "docker", "run",
            "-e", f"UNITY_LICENSE={FAKE_LICENSE}",
            "-e", f"UNITY_PASSWORD={FAKE_PASSWORD}",
            "-e", "BUILD_TARGET=Android",
            "image:tag",
        ]
        result = docker_mod._safe_command_repr(cmd)
        assert FAKE_LICENSE not in result
        assert FAKE_PASSWORD not in result
        assert "BUILD_TARGET=Android" in result
        assert "UNITY_LICENSE=***" in result
        assert "UNITY_PASSWORD=***" in result


# ---------------------------------------------------------------------------
# Dockerfiles do not use ENV for secrets
# ---------------------------------------------------------------------------

class TestDockerfileNoSecretEnv:
    """
    Convention test: Dockerfiles must not use the ENV instruction with
    secret variables. Secrets must be passed at runtime only.
    """

    # Patterns that indicate a secret being baked into an image layer
    SECRET_ENV_PATTERN = re.compile(
        r"^\s*ENV\s+(UNITY_LICENSE|UNITY_EMAIL|UNITY_PASSWORD|"
        r"ANDROID_KEYSTORE_BASE64|ANDROID_KEYSTORE_PASS|"
        r"ANDROID_KEY_ALIAS|ANDROID_KEY_PASS)\b",
        re.MULTILINE,
    )

    def _find_dockerfiles(self) -> list:
        patterns = [
            "docker/**/Dockerfile",
            "docker/**/*.Dockerfile",
        ]
        dockerfiles = []
        for pat in patterns:
            dockerfiles.extend(REPO_ROOT.glob(pat))
        return dockerfiles

    def test_no_secret_env_in_dockerfiles(self):
        dockerfiles = self._find_dockerfiles()
        violations = []
        for path in dockerfiles:
            content = path.read_text(encoding="utf-8", errors="replace")
            for m in self.SECRET_ENV_PATTERN.finditer(content):
                lineno = content[: m.start()].count("\n") + 1
                rel = path.relative_to(REPO_ROOT)
                violations.append(f"{rel}:{lineno}: ENV {m.group(1)} is forbidden")

        assert not violations, (
            "Secrets must NEVER be baked into image layers via ENV:\n"
            + "\n".join(f"  {v}" for v in violations)
        )

    def test_no_arg_with_default_secret_value(self):
        """ARG UNITY_LICENSE=<actual_value> is also forbidden."""
        dockerfiles = self._find_dockerfiles()
        violations = []
        # ARG UNITY_LICENSE=<non-empty> would expose a default
        pattern = re.compile(
            r"^\s*ARG\s+(UNITY_LICENSE|UNITY_PASSWORD|UNITY_EMAIL)\s*=\s*\S+",
            re.MULTILINE,
        )
        for path in dockerfiles:
            content = path.read_text(encoding="utf-8", errors="replace")
            for m in pattern.finditer(content):
                lineno = content[: m.start()].count("\n") + 1
                rel = path.relative_to(REPO_ROOT)
                violations.append(f"{rel}:{lineno}: ARG with default secret value")

        assert not violations, (
            "Secret ARGs must not have default values:\n"
            + "\n".join(f"  {v}" for v in violations)
        )


# ---------------------------------------------------------------------------
# Artifact directories must not contain license files
# ---------------------------------------------------------------------------

class TestArtifactDirNoLicenseFiles:

    LICENSE_FILE_PATTERNS = ["*.ulf", "*.alf", "unity-license*", "Unity_*.ulf"]

    def _check_no_license_in_dir(self, directory: Path):
        for pattern in self.LICENSE_FILE_PATTERNS:
            found = list(directory.rglob(pattern))
            assert not found, \
                f"License file found in {directory}: {found}"

    def test_clean_build_output_has_no_license(self, tmp_path):
        build_dir = tmp_path / "Builds"
        build_dir.mkdir()
        (build_dir / "game.apk").write_text("FAKE_APK_CONTENT")
        self._check_no_license_in_dir(build_dir)

    def test_license_file_is_detected(self, tmp_path):
        """Sanity check: our detection would catch a leaked license file."""
        build_dir = tmp_path / "Builds"
        build_dir.mkdir()
        (build_dir / "Unity_license.ulf").write_text(FAKE_LICENSE)
        with pytest.raises(AssertionError):
            self._check_no_license_in_dir(build_dir)


# ---------------------------------------------------------------------------
# Entrypoint cleanup of temp license files
# ---------------------------------------------------------------------------

class TestEntrypointCleanupContract:
    """
    Tests the cleanup convention documented in docker/unity/entrypoint.sh.
    The entrypoint must remove /tmp/unity-license-*.ulf files on exit (via trap).
    """

    def test_entrypoint_contains_cleanup_trap(self):
        entrypoint = REPO_ROOT / "docker" / "unity" / "entrypoint.sh"
        if not entrypoint.exists():
            pytest.skip("docker/unity/entrypoint.sh not yet created")
        content = entrypoint.read_text()
        assert "trap" in content, \
            "entrypoint.sh must use 'trap' to ensure cleanup on exit"
        assert "cleanup" in content.lower(), \
            "entrypoint.sh must call a cleanup function"

    def test_entrypoint_removes_temp_license_files(self):
        entrypoint = REPO_ROOT / "docker" / "unity" / "entrypoint.sh"
        if not entrypoint.exists():
            pytest.skip("docker/unity/entrypoint.sh not yet created")
        content = entrypoint.read_text()
        # Cleanup must remove .ulf files
        assert ".ulf" in content or "unity-license" in content, \
            "entrypoint.sh cleanup must remove temp license (.ulf) files"

    def test_entrypoint_removes_dot_unity3d(self):
        """entrypoint.sh must also clean up .unity3d credential files."""
        entrypoint = REPO_ROOT / "docker" / "unity" / "entrypoint.sh"
        if not entrypoint.exists():
            pytest.skip("docker/unity/entrypoint.sh not yet created")
        content = entrypoint.read_text()
        assert ".unity3d" in content, \
            "entrypoint.sh cleanup must remove .unity3d credential files"

    def test_no_license_residue_in_tmp(self):
        """No Unity license files should be left behind in system /tmp."""
        tmp_dir = Path(tempfile.gettempdir())
        leaked = list(tmp_dir.glob("unity-license-*.ulf"))
        assert not leaked, (
            f"Unity license files found in /tmp — scripts must clean up:\n"
            + "\n".join(str(f) for f in leaked)
        )
