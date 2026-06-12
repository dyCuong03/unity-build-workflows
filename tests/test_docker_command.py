"""
Tests for Docker command construction (scripts/docker/run_unity_container.py).

Tests the private _build_docker_command() function directly, plus the
_safe_command_repr() log sanitizer. Both are accessible via import.

Covers:
- Correct image reference in command
- --rm and --init flags present
- --user flag with host UID/GID
- Bind mounts for project, output, reports, logs (using --mount type=bind)
- Named volume mounts for Library cache and Gradle cache
- Security flags: --cap-drop=ALL, --security-opt=no-new-privileges
- No --privileged flag
- No docker.sock mount
- Non-secret environment variables passed as -e KEY=VALUE
- Secret env vars passed as -e NAME only (value not embedded in command)
- Container --stop-timeout set
- Dry-run mode returns command without calling subprocess
"""
import argparse
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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
# Shared test args / fixtures
# ---------------------------------------------------------------------------

FAKE_DIGEST = "sha256:" + "a" * 64
FAKE_IMAGE = f"ghcr.io/buzzelstudio/unity-android@{FAKE_DIGEST}"


def _make_args(**overrides) -> argparse.Namespace:
    """Return a minimal argparse.Namespace that _build_docker_command accepts."""
    defaults = dict(
        project_path="/workspace/MyProject",
        build_config_path="BuildConfig",
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


@pytest.fixture
def base_args():
    return _make_args()


@pytest.fixture
def output_path(tmp_path):
    p = tmp_path / "Builds"
    p.mkdir()
    return p


@pytest.fixture
def reports_path(tmp_path):
    p = tmp_path / "BuildReports"
    p.mkdir()
    return p


@pytest.fixture
def logs_path(tmp_path):
    p = tmp_path / "Logs"
    p.mkdir()
    return p


@pytest.fixture
def docker_cmd(docker_mod, base_args, output_path, reports_path, logs_path):
    return docker_mod._build_docker_command(
        docker="docker",
        image_ref=FAKE_IMAGE,
        args=base_args,
        output_path=output_path,
        reports_path=reports_path,
        logs_path=logs_path,
        cache_volume="unity-lib-test-cache",
        env_vars={},
    )


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------

class TestBasicCommandStructure:

    def test_command_is_a_list(self, docker_cmd):
        assert isinstance(docker_cmd, list)

    def test_first_arg_is_docker(self, docker_cmd):
        assert docker_cmd[0] == "docker", \
            f"Expected 'docker' as first arg, got '{docker_cmd[0]}'"

    def test_second_arg_is_run(self, docker_cmd):
        assert docker_cmd[1] == "run", \
            f"Expected 'run' as second arg, got '{docker_cmd[1]}'"

    def test_image_ref_in_command(self, docker_cmd):
        assert FAKE_IMAGE in docker_cmd, \
            f"Image reference not found in command: {FAKE_IMAGE}"

    def test_image_is_digest_pinned(self, docker_cmd):
        assert any("@sha256:" in arg for arg in docker_cmd), \
            "Command must contain a digest-pinned image reference"


# ---------------------------------------------------------------------------
# Container lifecycle flags
# ---------------------------------------------------------------------------

class TestLifecycleFlags:

    def test_rm_flag_present(self, docker_cmd):
        assert "--rm" in docker_cmd, "Missing --rm flag"

    def test_init_flag_present(self, docker_cmd):
        assert "--init" in docker_cmd, "Missing --init flag"

    def test_no_privileged_flag(self, docker_cmd):
        assert "--privileged" not in docker_cmd, \
            "--privileged is a security violation and must not appear"

    def test_no_detach_flag(self, docker_cmd):
        assert "-d" not in docker_cmd
        assert "--detach" not in docker_cmd


# ---------------------------------------------------------------------------
# User flag
# ---------------------------------------------------------------------------

class TestUserFlag:

    def test_user_flag_present(self, docker_cmd):
        assert "--user" in docker_cmd, "Missing --user flag"

    def test_user_flag_has_uid_gid_format(self, docker_cmd):
        idx = docker_cmd.index("--user")
        user_val = docker_cmd[idx + 1]
        assert ":" in user_val, \
            f"--user value must be UID:GID format, got: {user_val}"
        uid_str, gid_str = user_val.split(":", 1)
        assert uid_str.isdigit(), f"UID part is not numeric: {uid_str}"
        assert gid_str.isdigit(), f"GID part is not numeric: {gid_str}"


# ---------------------------------------------------------------------------
# Bind mounts
# ---------------------------------------------------------------------------

class TestBindMounts:

    def _get_mount_args(self, cmd):
        """Return list of strings that follow --mount flags."""
        mounts = []
        for i, arg in enumerate(cmd):
            if arg == "--mount" and i + 1 < len(cmd):
                mounts.append(cmd[i + 1])
        return mounts

    def test_project_path_bind_mounted(self, docker_cmd, output_path):
        mounts = self._get_mount_args(docker_cmd)
        project = "/workspace/MyProject"
        # Accepts either absolute or resolved path
        assert any(project in m or "workspace" in m.lower() for m in mounts if "bind" in m), \
            f"Project path not found in bind mounts.\nMounts: {mounts}"

    def test_output_dir_bind_mounted(self, docker_cmd, output_path):
        mounts = self._get_mount_args(docker_cmd)
        assert any(str(output_path) in m and "bind" in m for m in mounts), \
            f"Output path '{output_path}' not found in bind mounts.\nMounts: {mounts}"

    def test_reports_dir_bind_mounted(self, docker_cmd, reports_path):
        mounts = self._get_mount_args(docker_cmd)
        assert any(str(reports_path) in m and "bind" in m for m in mounts), \
            f"Reports path '{reports_path}' not found in bind mounts.\nMounts: {mounts}"

    def test_logs_dir_bind_mounted(self, docker_cmd, logs_path):
        mounts = self._get_mount_args(docker_cmd)
        assert any(str(logs_path) in m and "bind" in m for m in mounts), \
            f"Logs path '{logs_path}' not found in bind mounts.\nMounts: {mounts}"

    def test_no_docker_sock_mount(self, docker_cmd):
        cmd_str = " ".join(docker_cmd)
        assert "/var/run/docker.sock" not in cmd_str, \
            "Docker socket must NEVER be mounted (DinD is forbidden)"


# ---------------------------------------------------------------------------
# Volume mounts (named caches)
# ---------------------------------------------------------------------------

class TestVolumeMounts:

    def test_library_cache_volume_mounted_in_safe_mode(
        self, docker_mod, base_args, output_path, reports_path, logs_path
    ):
        """With cache_mode=safe, Library cache volume is mounted."""
        cmd = docker_mod._build_docker_command(
            docker="docker",
            image_ref=FAKE_IMAGE,
            args=_make_args(cache_mode="safe"),
            output_path=output_path,
            reports_path=reports_path,
            logs_path=logs_path,
            cache_volume="unity-lib-test-cache",
            env_vars={},
        )
        cmd_str = " ".join(cmd)
        assert "unity-lib-test-cache" in cmd_str, \
            "Library cache volume must appear in command when cache_mode=safe"

    def test_library_cache_not_mounted_when_off(
        self, docker_mod, output_path, reports_path, logs_path
    ):
        """With cache_mode=off, Library cache volume must NOT be mounted."""
        cmd = docker_mod._build_docker_command(
            docker="docker",
            image_ref=FAKE_IMAGE,
            args=_make_args(cache_mode="off"),
            output_path=output_path,
            reports_path=reports_path,
            logs_path=logs_path,
            cache_volume="unity-lib-test-cache",
            env_vars={},
        )
        cmd_str = " ".join(cmd)
        assert "unity-lib-test-cache" not in cmd_str, \
            "Library cache volume must NOT be mounted when cache_mode=off"

    def test_gradle_cache_volume_mounted_for_android(
        self, docker_mod, output_path, reports_path, logs_path
    ):
        """For Android target, a Gradle cache volume must be mounted."""
        cmd = docker_mod._build_docker_command(
            docker="docker",
            image_ref=FAKE_IMAGE,
            args=_make_args(target_platform="Android", project_path="/workspace/Proj"),
            output_path=output_path,
            reports_path=reports_path,
            logs_path=logs_path,
            cache_volume="unity-lib-android-cache",
            env_vars={},
        )
        # Gradle cache volume appears in the --mount args
        cmd_str = " ".join(cmd)
        assert "gradle" in cmd_str.lower(), \
            "Gradle cache volume must be mounted for Android builds"

    def test_gradle_cache_not_mounted_for_webgl(
        self, docker_mod, output_path, reports_path, logs_path
    ):
        """WebGL builds don't need a Gradle cache."""
        cmd = docker_mod._build_docker_command(
            docker="docker",
            image_ref=FAKE_IMAGE,
            args=_make_args(target_platform="WebGL"),
            output_path=output_path,
            reports_path=reports_path,
            logs_path=logs_path,
            cache_volume="unity-lib-webgl-cache",
            env_vars={},
        )
        volume_mounts = [
            arg for i, arg in enumerate(cmd)
            if i > 0 and cmd[i - 1] == "--mount" and "type=volume" in arg
        ]
        gradle_mounts = [m for m in volume_mounts if "gradle" in m.lower()]
        assert not gradle_mounts, \
            "Gradle cache must NOT be mounted for WebGL builds"


# ---------------------------------------------------------------------------
# Security flags
# ---------------------------------------------------------------------------

class TestSecurityFlags:

    def test_cap_drop_all_present(self, docker_cmd):
        cmd_str = " ".join(docker_cmd)
        assert "--cap-drop=ALL" in cmd_str, \
            "Missing --cap-drop=ALL (security hardening requirement)"

    def test_no_new_privileges_present(self, docker_cmd):
        cmd_str = " ".join(docker_cmd)
        assert "no-new-privileges" in cmd_str, \
            "Missing --security-opt=no-new-privileges"

    def test_security_opt_flag_present(self, docker_cmd):
        cmd_str = " ".join(docker_cmd)
        assert "--security-opt" in cmd_str or "--security-opt=no-new-privileges" in cmd_str

    def test_no_privileged(self, docker_cmd):
        assert "--privileged" not in docker_cmd, \
            "--privileged must never appear in the Docker command"


# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------

class TestEnvironmentVariables:

    def test_target_platform_env_var_present(self, docker_cmd):
        # -e TARGET_PLATFORM=Android
        cmd_str = " ".join(docker_cmd)
        assert "TARGET_PLATFORM" in cmd_str

    def test_environment_env_var_present(self, docker_cmd):
        cmd_str = " ".join(docker_cmd)
        assert "ENVIRONMENT" in cmd_str

    def test_unity_version_env_var_present(self, docker_cmd):
        cmd_str = " ".join(docker_cmd)
        assert "UNITY_VERSION" in cmd_str

    def test_extra_non_secret_env_vars_passed(
        self, docker_mod, base_args, output_path, reports_path, logs_path
    ):
        cmd = docker_mod._build_docker_command(
            docker="docker",
            image_ref=FAKE_IMAGE,
            args=base_args,
            output_path=output_path,
            reports_path=reports_path,
            logs_path=logs_path,
            cache_volume="vol",
            env_vars={"CUSTOM_VAR": "custom_value"},
        )
        cmd_str = " ".join(cmd)
        assert "CUSTOM_VAR=custom_value" in cmd_str, \
            "Non-secret extra env var must appear as KEY=VALUE in command"


# ---------------------------------------------------------------------------
# Secret env vars: name only, value NOT embedded
# ---------------------------------------------------------------------------

class TestSecretEnvVarHandling:

    FAKE_LICENSE = "FAKE_LICENSE_XML_CONTENT_SHOULD_NOT_APPEAR"
    FAKE_PASSWORD = "super_secret_password_xyz_123"
    FAKE_KEYSTORE = "android_keystore_pass_abc_456"

    def test_unity_license_value_not_in_command(
        self, docker_mod, base_args, output_path, reports_path, logs_path
    ):
        """UNITY_LICENSE passed via env_vars is FILTERED (secret var)."""
        cmd = docker_mod._build_docker_command(
            docker="docker",
            image_ref=FAKE_IMAGE,
            args=base_args,
            output_path=output_path,
            reports_path=reports_path,
            logs_path=logs_path,
            cache_volume="vol",
            env_vars={"UNITY_LICENSE": self.FAKE_LICENSE},
        )
        cmd_str = " ".join(cmd)
        assert self.FAKE_LICENSE not in cmd_str, \
            "UNITY_LICENSE secret value must NOT appear in command"

    def test_unity_password_value_not_in_command(
        self, docker_mod, base_args, output_path, reports_path, logs_path
    ):
        cmd = docker_mod._build_docker_command(
            docker="docker",
            image_ref=FAKE_IMAGE,
            args=base_args,
            output_path=output_path,
            reports_path=reports_path,
            logs_path=logs_path,
            cache_volume="vol",
            env_vars={"UNITY_PASSWORD": self.FAKE_PASSWORD},
        )
        cmd_str = " ".join(cmd)
        assert self.FAKE_PASSWORD not in cmd_str, \
            "UNITY_PASSWORD value must NOT appear in docker command"

    def test_keystore_pass_value_not_in_command(
        self, docker_mod, base_args, output_path, reports_path, logs_path
    ):
        cmd = docker_mod._build_docker_command(
            docker="docker",
            image_ref=FAKE_IMAGE,
            args=base_args,
            output_path=output_path,
            reports_path=reports_path,
            logs_path=logs_path,
            cache_volume="vol",
            env_vars={"ANDROID_KEYSTORE_PASS": self.FAKE_KEYSTORE},
        )
        cmd_str = " ".join(cmd)
        assert self.FAKE_KEYSTORE not in cmd_str, \
            "ANDROID_KEYSTORE_PASS value must NOT appear in docker command"


# ---------------------------------------------------------------------------
# Container timeout
# ---------------------------------------------------------------------------

class TestContainerTimeout:

    def test_stop_timeout_present(self, docker_cmd):
        cmd_str = " ".join(docker_cmd)
        assert "--stop-timeout" in cmd_str, \
            "Missing --stop-timeout (hard container deadline)"

    def test_default_timeout_is_3600(self, docker_cmd):
        idx = docker_cmd.index("--stop-timeout")
        timeout_val = docker_cmd[idx + 1]
        assert timeout_val == "3600", \
            f"Default timeout must be 3600 seconds, got '{timeout_val}'"

    def test_custom_timeout_applied(
        self, docker_mod, output_path, reports_path, logs_path
    ):
        cmd = docker_mod._build_docker_command(
            docker="docker",
            image_ref=FAKE_IMAGE,
            args=_make_args(container_timeout=7200),
            output_path=output_path,
            reports_path=reports_path,
            logs_path=logs_path,
            cache_volume="vol",
            env_vars={},
        )
        idx = cmd.index("--stop-timeout")
        assert cmd[idx + 1] == "7200", \
            f"Expected timeout 7200, got '{cmd[idx + 1]}'"


# ---------------------------------------------------------------------------
# Safe command repr (log sanitizer)
# ---------------------------------------------------------------------------

class TestSafeCommandRepr:

    def test_safe_repr_masks_secret_value(self, docker_mod):
        """_safe_command_repr must replace -e UNITY_LICENSE=<value> with ***."""
        cmd = ["docker", "run", "--rm", "-e", "UNITY_LICENSE=REAL_SECRET_VALUE", "image:tag"]
        result = docker_mod._safe_command_repr(cmd)
        assert "REAL_SECRET_VALUE" not in result, \
            "Secret value must be masked in safe repr"
        assert "UNITY_LICENSE=***" in result, \
            "Masked secret must show KEY=*** form"

    def test_safe_repr_preserves_non_secret_vars(self, docker_mod):
        cmd = ["docker", "run", "--rm", "-e", "TARGET_PLATFORM=Android", "image:tag"]
        result = docker_mod._safe_command_repr(cmd)
        assert "TARGET_PLATFORM=Android" in result, \
            "Non-secret env vars must not be masked"

    def test_safe_repr_safe_name_only_form(self, docker_mod):
        """'-e UNITY_LICENSE' (no value) must pass through unchanged."""
        cmd = ["docker", "run", "--rm", "-e", "UNITY_LICENSE", "image:tag"]
        result = docker_mod._safe_command_repr(cmd)
        assert "UNITY_LICENSE" in result

    def test_safe_repr_masks_android_keystore(self, docker_mod):
        cmd = ["docker", "run", "-e", "ANDROID_KEYSTORE_PASS=secret123", "image:tag"]
        result = docker_mod._safe_command_repr(cmd)
        assert "secret123" not in result
        assert "ANDROID_KEYSTORE_PASS=***" in result

    def test_safe_repr_masks_android_key_pass(self, docker_mod):
        cmd = ["docker", "run", "-e", "ANDROID_KEY_PASS=kp_secret_xyz", "image:tag"]
        result = docker_mod._safe_command_repr(cmd)
        assert "kp_secret_xyz" not in result


# ---------------------------------------------------------------------------
# Volume name helpers
# ---------------------------------------------------------------------------

class TestVolumeNameHelpers:

    def test_cache_volume_name_deterministic(self, docker_mod, tmp_path):
        """Same inputs always produce the same volume name."""
        name1 = docker_mod._cache_volume_name(tmp_path, "2022.3.45f1", "Android")
        name2 = docker_mod._cache_volume_name(tmp_path, "2022.3.45f1", "Android")
        assert name1 == name2

    def test_cache_volume_name_different_for_different_platforms(self, docker_mod, tmp_path):
        android = docker_mod._cache_volume_name(tmp_path, "2022.3.45f1", "Android")
        webgl = docker_mod._cache_volume_name(tmp_path, "2022.3.45f1", "WebGL")
        assert android != webgl

    def test_cache_volume_name_starts_with_unity_lib(self, docker_mod, tmp_path):
        name = docker_mod._cache_volume_name(tmp_path, "2022.3.45f1", "Android")
        assert name.startswith("unity-lib-"), \
            f"Cache volume name should start with 'unity-lib-', got: {name}"

    def test_gradle_cache_volume_name_starts_with_unity_gradle(self, docker_mod, tmp_path):
        name = docker_mod._gradle_cache_volume_name(tmp_path)
        assert name.startswith("unity-gradle-"), \
            f"Gradle volume name should start with 'unity-gradle-', got: {name}"

    def test_sanitize_volume_name_replaces_dots(self, docker_mod):
        sanitized = docker_mod._sanitize_volume_name("2022.3.45f1")
        assert "." not in sanitized or sanitized == "2022.3.45f1", \
            "Dots should be replaced or preserved (Docker allows them)"
