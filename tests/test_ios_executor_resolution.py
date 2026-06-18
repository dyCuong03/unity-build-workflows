"""
Tests for platform→executor resolution (scripts/common/resolve_platform_executor.py).

Contract:
  - iOS  →  executor: macos-unity-xcode
  - Docker platforms (Android, WebGL, StandaloneLinux64, LinuxServer) → executor: docker-unity
  - iOS rejected when runner-os == linux  (exits non-zero, contract error)
  - Android/WebGL/Linux rejected when runner-os == macos  (wrong executor lane)
  - Approved iOS native allowlist is honoured

PENDING TEAMMATE: scripts/common/resolve_platform_executor.py is produced by
the architect-resolver teammate.  Tests skip gracefully if the file is absent
and fail clearly (not error) once it lands so the suite is always runnable.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
RESOLVER_PATH = REPO_ROOT / "scripts" / "common" / "resolve_platform_executor.py"

# -------------------------------------------------------------------
# Skip markers
# -------------------------------------------------------------------

RESOLVER_MISSING = not RESOLVER_PATH.exists()

_SKIP_NO_RESOLVER = pytest.mark.skipif(
    RESOLVER_MISSING,
    reason=(
        "scripts/common/resolve_platform_executor.py not yet created "
        "(pending architect-resolver teammate)"
    ),
)


def _run_resolver(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run the resolver script as a subprocess and return the result."""
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run(
        [sys.executable, str(RESOLVER_PATH), *args],
        capture_output=True,
        text=True,
        timeout=15,
        env=e,
    )


# -------------------------------------------------------------------
# Resolver file existence
# -------------------------------------------------------------------

class TestResolverFileExists:

    def test_resolver_file_exists(self):
        """
        Fails clearly if the resolver has not been created yet.
        This test gives a direct, actionable failure message rather than
        a confusing ImportError or FileNotFoundError from other tests.
        """
        assert RESOLVER_PATH.exists(), (
            f"PENDING TEAMMATE: {RESOLVER_PATH} does not exist yet. "
            "The architect-resolver teammate must create it."
        )


# -------------------------------------------------------------------
# iOS → macos-unity-xcode
# -------------------------------------------------------------------

@_SKIP_NO_RESOLVER
class TestIOSExecutorResolution:

    def test_ios_resolves_to_macos_unity_xcode(self):
        result = _run_resolver("--target-platform", "iOS", "--runner-os", "macos")
        assert result.returncode == 0, (
            f"iOS on macos must resolve successfully.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "macos-unity-xcode" in result.stdout, (
            f"iOS executor must be 'macos-unity-xcode', got: {result.stdout!r}"
        )

    def test_ios_executor_output_is_clean(self):
        """Resolver output must be a clean executor name with no extra whitespace."""
        result = _run_resolver("--target-platform", "iOS", "--runner-os", "macos")
        if result.returncode != 0:
            pytest.skip("Resolver failed — skipping output format check")
        output = result.stdout.strip()
        assert output == "macos-unity-xcode", (
            f"Expected clean output 'macos-unity-xcode', got: {output!r}"
        )


# -------------------------------------------------------------------
# Docker platforms → docker-unity
# -------------------------------------------------------------------

@_SKIP_NO_RESOLVER
class TestDockerPlatformResolution:

    @pytest.mark.parametrize("platform", [
        "Android",
        "WebGL",
        "StandaloneLinux64",
        "LinuxServer",
    ])
    def test_docker_platforms_resolve_to_docker_unity(self, platform):
        result = _run_resolver("--target-platform", platform, "--runner-os", "linux")
        assert result.returncode == 0, (
            f"{platform} on linux must resolve successfully.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "docker-unity" in result.stdout, (
            f"{platform} executor must be 'docker-unity', got: {result.stdout!r}"
        )


# -------------------------------------------------------------------
# iOS rejected on Linux runner
# -------------------------------------------------------------------

@_SKIP_NO_RESOLVER
class TestIOSRejectedOnLinux:

    def test_ios_on_linux_exits_nonzero(self):
        """iOS cannot run on a Linux runner — resolver must exit non-zero."""
        result = _run_resolver("--target-platform", "iOS", "--runner-os", "linux")
        assert result.returncode != 0, (
            "iOS on linux must be rejected (non-zero exit).\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_ios_on_linux_error_mentions_macos(self):
        """Error message must guide user to use macOS runner."""
        result = _run_resolver("--target-platform", "iOS", "--runner-os", "linux")
        combined = (result.stdout + result.stderr).lower()
        assert "macos" in combined or "xcode" in combined or "ios" in combined, (
            f"Error for iOS-on-Linux must mention macOS/Xcode/iOS.\n"
            f"Output: {result.stdout + result.stderr}"
        )

    def test_ios_on_linux_contract_error_present(self):
        """Contract error string must be present in output."""
        result = _run_resolver("--target-platform", "iOS", "--runner-os", "linux")
        combined = result.stdout + result.stderr
        # The contract says the resolver exits non-zero with a contract error message
        assert len(combined.strip()) > 0, (
            "Resolver must emit a diagnostic message when rejecting iOS-on-Linux"
        )


# -------------------------------------------------------------------
# Docker platforms rejected on macOS (wrong lane)
# -------------------------------------------------------------------

@_SKIP_NO_RESOLVER
class TestDockerPlatformsRejectedOnMacOS:

    @pytest.mark.parametrize("platform", [
        "Android",
        "WebGL",
        "StandaloneLinux64",
    ])
    def test_docker_platform_on_macos_runner_exits_nonzero(self, platform):
        """
        Docker platforms require docker-unity executor.
        Requesting them on a macos runner is a misconfiguration.
        """
        result = _run_resolver("--target-platform", platform, "--runner-os", "macos")
        assert result.returncode != 0, (
            f"{platform} on macos should be rejected (docker platforms need Linux).\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


# -------------------------------------------------------------------
# Unknown platform
# -------------------------------------------------------------------

@_SKIP_NO_RESOLVER
class TestUnknownPlatform:

    def test_unknown_platform_exits_nonzero(self):
        result = _run_resolver("--target-platform", "PS5", "--runner-os", "linux")
        assert result.returncode != 0, (
            "Unknown platform must exit non-zero.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_unknown_platform_error_is_helpful(self):
        result = _run_resolver("--target-platform", "PS5", "--runner-os", "linux")
        combined = result.stdout + result.stderr
        assert len(combined.strip()) > 0, (
            "Unknown platform must emit a diagnostic message."
        )


# -------------------------------------------------------------------
# Missing required arguments
# -------------------------------------------------------------------

@_SKIP_NO_RESOLVER
class TestMissingArguments:

    def test_missing_target_platform_exits_nonzero(self):
        result = _run_resolver("--runner-os", "linux")
        assert result.returncode != 0, (
            "Missing --target-platform must cause non-zero exit"
        )

    def test_missing_runner_os_still_resolves_ios(self):
        """
        --runner-os is optional; omitting it skips cross-validation.
        iOS without --runner-os must still resolve to macos-unity-xcode.
        """
        result = _run_resolver("--target-platform", "iOS")
        assert result.returncode == 0, (
            "iOS without --runner-os must resolve (no cross-validation).\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "macos-unity-xcode" in result.stdout, (
            f"iOS must resolve to macos-unity-xcode even without --runner-os. "
            f"Got: {result.stdout!r}"
        )

    def test_no_args_exits_nonzero(self):
        result = _run_resolver()
        assert result.returncode != 0, (
            "No arguments must cause non-zero exit"
        )


# -------------------------------------------------------------------
# Approved iOS native allowlist
# -------------------------------------------------------------------

@_SKIP_NO_RESOLVER
class TestApprovedIOSNativeAllowlist:
    """
    The iOS lane is only approved for specific known platforms.
    Any platform NOT in the iOS-approved set must not accidentally
    resolve to the macOS executor.
    """

    @pytest.mark.parametrize("non_ios_platform", [
        "Android",
        "WebGL",
        "StandaloneLinux64",
        "LinuxServer",
        "Windows64",
        "StandaloneWindows64",
        "StandaloneOSX",
    ])
    def test_non_ios_platform_does_not_get_macos_executor(self, non_ios_platform):
        """Non-iOS platforms must never resolve to macos-unity-xcode."""
        result = _run_resolver(
            "--target-platform", non_ios_platform,
            "--runner-os", "linux",
        )
        # Either it fails (unknown/wrong lane) or resolves to docker-unity
        output = result.stdout
        assert "macos-unity-xcode" not in output, (
            f"{non_ios_platform} must not resolve to macos-unity-xcode. "
            f"Got: {output!r}"
        )
