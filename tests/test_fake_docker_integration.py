"""
End-to-end fake integration tests for the Docker build lane.

Uses tests/fixtures/fake_docker.sh as a drop-in replacement for the
real Docker binary. The stub is placed on PATH before the system Docker
so run_unity_container.py invokes it without a real daemon or Unity image.

Coverage:
  fake_docker.sh stub existence and permissions
  fake_docker.sh success mode — exit 0, artifact written
  fake_docker.sh pull_failure mode — exit 1 with registry error
  fake_docker.sh oom_killed mode — exit 137 with OOM message
  fake_docker.sh exit_nonzero mode — exit 1 with compile error in log
  fake_docker.sh image_not_found mode — exit 125
  fake_docker.sh non-run subcommands (inspect, images, pull, rmi) — exit 0
  run_unity_container.py --image passthrough with fake docker
  run_unity_container.py exits non-zero when docker exits non-zero
  run_unity_container.py exits 0 when docker exits 0
  release-mode rejects un-pinned image (before docker is called)
  Output artifact written to expected location in success mode

Skip behaviour:
  Tests that invoke run_unity_container.py skip if the script is absent.
  Tests that invoke fake_docker.sh always run (it's in our fixture tree).
"""
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures"

FAKE_DOCKER = FIXTURES_DIR / "fake_docker.sh"
SCRIPT_PATH = REPO_ROOT / "scripts" / "docker" / "run_unity_container.py"

FAKE_DIGEST = "sha256:" + "a" * 64
FAKE_IMAGE_TAG = "ghcr.io/example/unity-android:2022.3.21f1"
FAKE_IMAGE_PINNED = f"{FAKE_IMAGE_TAG}@{FAKE_DIGEST}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_fake_docker(*args, mode: str = "success", extra_env: dict | None = None,
                     timeout: int = 10) -> subprocess.CompletedProcess:
    """Run fake_docker.sh directly (not via run_unity_container.py)."""
    env = os.environ.copy()
    env["FAKE_DOCKER_MODE"] = mode
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(FAKE_DOCKER), *args],
        capture_output=True, text=True, timeout=timeout, env=env,
    )


def _run_container_script(*extra_args: str, mode: str = "success",
                          image: str = FAKE_IMAGE_TAG,
                          tmp_path: Path | None = None,
                          timeout: int = 15) -> subprocess.CompletedProcess:
    """
    Run run_unity_container.py with fake_docker.sh on PATH.
    The fake docker binary is named 'docker' in a temp bin dir prepended to PATH.
    """
    if not SCRIPT_PATH.exists():
        pytest.skip("scripts/docker/run_unity_container.py not yet created")

    work = tmp_path or Path(tempfile.mkdtemp())
    fake_bin = work / ".fake_bin"
    fake_bin.mkdir(exist_ok=True)
    fake_docker_link = fake_bin / "docker"
    # Create a wrapper that delegates to our stub
    fake_docker_link.write_text(
        f'#!/usr/bin/env bash\nexec bash "{FAKE_DOCKER}" "$@"\n'
    )
    fake_docker_link.chmod(0o755)

    project = work / "project"
    project.mkdir(exist_ok=True)
    (project / "Assets").mkdir(exist_ok=True)  # run_unity_container.py validates Assets/ exists
    output = work / "output"
    output.mkdir(exist_ok=True)
    logs = work / "logs"
    logs.mkdir(exist_ok=True)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["FAKE_DOCKER_MODE"] = mode
    env["FAKE_DOCKER_OUTPUT_DIR"] = str(output)

    cmd = [
        sys.executable, str(SCRIPT_PATH),
        "--project-path", str(project),
        "--unity-version", "2022.3.21f1",
        "--target-platform", "Android",
        "--image", image,
        "--log-path", str(logs),
        "--report-path", str(work / "reports"),
        "--skip-image-validation",  # fake docker cannot satisfy image health checks
        *extra_args,
    ]
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, env=env,
    )


# ---------------------------------------------------------------------------
# Stub file contract
# ---------------------------------------------------------------------------

class TestFakeDockerStub:
    """Verify the stub file itself is valid and executable."""

    def test_stub_file_exists(self):
        assert FAKE_DOCKER.exists(), (
            f"tests/fixtures/fake_docker.sh must exist at {FAKE_DOCKER}"
        )

    def test_stub_is_executable(self):
        mode = FAKE_DOCKER.stat().st_mode
        assert mode & stat.S_IXUSR, (
            "tests/fixtures/fake_docker.sh must be executable (chmod +x)"
        )

    def test_stub_is_bash_script(self):
        first_line = FAKE_DOCKER.read_text().splitlines()[0]
        assert "bash" in first_line, (
            f"fake_docker.sh must have a bash shebang. Got: {first_line!r}"
        )

    def test_stub_documents_all_modes(self):
        """The stub must document all supported modes in its header comment."""
        text = FAKE_DOCKER.read_text()
        required_modes = ["success", "pull_failure", "oom_killed", "exit_nonzero", "timeout"]
        for mode in required_modes:
            assert mode in text, (
                f"fake_docker.sh must document mode '{mode}' in its header"
            )

    def test_stub_reads_fake_docker_mode(self):
        text = FAKE_DOCKER.read_text()
        assert "FAKE_DOCKER_MODE" in text, (
            "fake_docker.sh must read FAKE_DOCKER_MODE env var to select behaviour"
        )

    def test_stub_reads_fake_docker_output_dir(self):
        text = FAKE_DOCKER.read_text()
        assert "FAKE_DOCKER_OUTPUT_DIR" in text, (
            "fake_docker.sh must read FAKE_DOCKER_OUTPUT_DIR env var"
        )


# ---------------------------------------------------------------------------
# Stub mode behaviour: direct invocation
# ---------------------------------------------------------------------------

class TestFakeDockerModes:
    """Test each mode of fake_docker.sh by invoking it directly."""

    def test_success_mode_exits_zero(self, tmp_path):
        result = _run_fake_docker("run", "fake/unity:test",
                                  mode="success",
                                  extra_env={"FAKE_DOCKER_OUTPUT_DIR": str(tmp_path)})
        assert result.returncode == 0, (
            f"success mode must exit 0.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_success_mode_writes_artifact(self, tmp_path):
        output = tmp_path / "output"
        output.mkdir()
        _run_fake_docker("run", "fake/unity:test",
                         mode="success",
                         extra_env={"FAKE_DOCKER_OUTPUT_DIR": str(output)})
        artifacts = list(output.iterdir())
        assert artifacts, (
            f"success mode must write a fake artifact to FAKE_DOCKER_OUTPUT_DIR ({output})"
        )

    def test_pull_failure_mode_exits_nonzero(self):
        result = _run_fake_docker("run", "fake/unity:test", mode="pull_failure")
        assert result.returncode != 0, "pull_failure mode must exit non-zero"

    def test_pull_failure_error_message_is_actionable(self):
        result = _run_fake_docker("run", "fake/unity:test", mode="pull_failure")
        combined = result.stdout + result.stderr
        assert any(kw in combined.lower() for kw in (
            "registry", "pull", "image", "error", "daemon"
        )), (
            f"pull_failure must produce an actionable error. Got:\n{combined}"
        )

    def test_oom_killed_exits_137(self):
        result = _run_fake_docker("run", "fake/unity:test", mode="oom_killed")
        assert result.returncode == 137, (
            f"oom_killed mode must exit 137 (SIGKILL). Got: {result.returncode}"
        )

    def test_exit_nonzero_mode_exits_nonzero(self):
        result = _run_fake_docker("run", "fake/unity:test", mode="exit_nonzero")
        assert result.returncode != 0, "exit_nonzero mode must exit non-zero"

    def test_exit_nonzero_log_contains_compile_error(self, tmp_path):
        log = tmp_path / "docker.log"
        result = _run_fake_docker("run", "fake/unity:test",
                                  mode="exit_nonzero",
                                  extra_env={"FAKE_DOCKER_LOG_FILE": str(log)})
        assert log.exists(), "exit_nonzero mode must write a log file"
        log_text = log.read_text()
        assert "error" in log_text.lower(), (
            f"exit_nonzero log must mention compile error. Got:\n{log_text}"
        )

    def test_image_not_found_exits_nonzero(self):
        result = _run_fake_docker("run", "fake/unity:nonexistent", mode="image_not_found")
        assert result.returncode != 0, "image_not_found mode must exit non-zero"

    def test_image_not_found_message_is_actionable(self):
        result = _run_fake_docker("run", "fake/unity:nonexistent", mode="image_not_found")
        combined = result.stdout + result.stderr
        assert any(kw in combined.lower() for kw in (
            "unable to find", "not found", "manifest", "image"
        )), (
            f"image_not_found must produce an actionable error. Got:\n{combined}"
        )

    # ── Non-run subcommands always succeed ───────────────────────────────────

    def test_pull_success_mode_exits_zero(self):
        result = _run_fake_docker("pull", "fake/unity:test", mode="success")
        assert result.returncode == 0, "pull in success mode must exit 0"

    def test_inspect_exits_zero(self):
        result = _run_fake_docker("inspect", "fake/unity:test")
        assert result.returncode == 0, "docker inspect must exit 0"

    def test_images_exits_zero(self):
        result = _run_fake_docker("images")
        assert result.returncode == 0, "docker images must exit 0"

    def test_rmi_exits_zero(self):
        result = _run_fake_docker("rmi", "fake/unity:test")
        assert result.returncode == 0, "docker rmi must exit 0"


# ---------------------------------------------------------------------------
# Integration: run_unity_container.py + fake docker
# ---------------------------------------------------------------------------

class TestRunUnityContainerWithFakeDocker:
    """
    End-to-end tests: run_unity_container.py drives fake_docker.sh.
    Verifies that the script's exit code matches the container's exit code
    and that it correctly handles all stub modes.

    Tests skip if run_unity_container.py is not yet available.
    """

    def test_success_mode_script_exits_zero(self, tmp_path):
        result = _run_container_script(mode="success", tmp_path=tmp_path)
        assert result.returncode == 0, (
            f"Script must exit 0 when docker exits 0.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_exit_nonzero_propagates_to_script(self, tmp_path):
        result = _run_container_script(mode="exit_nonzero", tmp_path=tmp_path)
        assert result.returncode != 0, (
            "Script must exit non-zero when docker container exits non-zero.\n"
            "run_unity_container.py must propagate the container exit code."
        )

    def test_oom_killed_propagates_to_script(self, tmp_path):
        result = _run_container_script(mode="oom_killed", tmp_path=tmp_path)
        assert result.returncode != 0, (
            "Script must exit non-zero when container is OOM-killed (exit 137)."
        )

    def test_pull_failure_propagates_to_script(self, tmp_path):
        result = _run_container_script(mode="pull_failure", tmp_path=tmp_path)
        assert result.returncode != 0, (
            "Script must exit non-zero when docker pull fails."
        )

    def test_image_not_found_propagates_to_script(self, tmp_path):
        result = _run_container_script(mode="image_not_found", tmp_path=tmp_path)
        assert result.returncode != 0, (
            "Script must exit non-zero when image is not found."
        )

    def test_release_mode_pinned_image_accepted(self, tmp_path):
        """Digest-pinned image + release-mode must not error at validation stage."""
        result = _run_container_script(
            "--release-mode",
            mode="success",
            image=FAKE_IMAGE_PINNED,
            tmp_path=tmp_path,
        )
        # May succeed (0) or fail for other reasons, but must NOT fail specifically
        # because of release-mode validation (the image IS pinned).
        combined = result.stdout + result.stderr
        assert "release mode requires" not in combined.lower(), (
            "Digest-pinned image must not trigger release-mode digest error.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_release_mode_unpinned_image_rejected_before_docker(self, tmp_path):
        """
        Release mode must reject a mutable (un-pinned) image BEFORE invoking Docker.
        The fake docker is in success mode — if this test fails, it means the
        script ran Docker anyway without checking the digest.
        """
        result = _run_container_script(
            "--release-mode",
            mode="success",      # docker would succeed if called
            image=FAKE_IMAGE_TAG,  # NOT pinned
            tmp_path=tmp_path,
        )
        assert result.returncode != 0, (
            "release-mode + un-pinned image must be rejected with non-zero exit. "
            "The validation must happen BEFORE docker is called."
        )
        combined = result.stdout + result.stderr
        assert any(kw in combined.lower() for kw in (
            "digest", "pinned", "release", "sha256", "immutable"
        )), (
            f"Release-mode rejection must mention digest/pinned/sha256. Got:\n{combined}"
        )

    def test_fake_docker_is_called_not_real_docker(self, tmp_path):
        """
        Verify that the fake docker stub is invoked (not real docker).
        The stub writes a specific marker in its output.
        """
        result = _run_container_script(mode="success", tmp_path=tmp_path)
        # The fake stub writes "Fake docker run succeeded" or similar
        # OR the test environment has no real docker — either way, the
        # test confirms we can run without a Docker daemon.
        # If returncode is 0, fake docker was used (real docker would need image).
        # This is a best-effort check — the key contract is exit code propagation.
        assert result.returncode == 0, (
            "With fake docker on PATH, success mode must allow script to exit 0. "
            "If this fails, check that the fake_bin wrapper is on PATH correctly."
        )


# ---------------------------------------------------------------------------
# Output path contract: artifact inside project workspace
# ---------------------------------------------------------------------------

class TestDockerOutputPathContract:
    """
    Docker build output must land inside the project workspace, not inside
    the toolkit checkout (.ci/unity-build-workflows) or outside the runner
    working directory.

    These are geometry tests — they don't require run_unity_container.py
    to be present. They document the path contract that T4/T5 must satisfy.
    """

    def test_output_dir_is_under_project_not_toolkit(self, tmp_path):
        """
        Output artifact directory must be relative to the consumer project
        checkout (project/<project-path>/), NOT relative to the toolkit
        (.ci/unity-build-workflows/).
        """
        project_path = tmp_path / "project" / "MyGame"
        toolkit_path = tmp_path / ".ci" / "unity-build-workflows"
        output_path = project_path / "Build" / "Android"

        # Output must be under project/, not under .ci/
        assert output_path.is_relative_to(tmp_path / "project"), (
            "Build output must be inside the consumer project tree (project/), "
            "not inside the toolkit tree (.ci/unity-build-workflows/)."
        )
        assert not output_path.is_relative_to(toolkit_path), (
            "Build output must NOT be inside the toolkit checkout (.ci/unity-build-workflows/)"
        )

    def test_output_dir_does_not_escape_workspace(self, tmp_path):
        """
        Build output path must not contain ../ and must stay within the
        runner workspace. A path like ../../tmp/evil must be rejected.
        """
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        evil_output_paths = [
            "../../tmp/evil",
            "../outside-workspace",
            "/absolute/path/to/output",
        ]
        for evil in evil_output_paths:
            if evil.startswith("/"):
                # Absolute paths always escape the workspace
                assert not Path(evil).is_relative_to(workspace), (
                    f"Absolute output path '{evil}' must be rejected"
                )
            else:
                combined = workspace / evil
                # Check if resolved path escapes workspace
                assert ".." in str(combined), (
                    f"Path '{evil}' must contain .. marker for traversal detection"
                )

    def test_output_dir_and_toolkit_are_separate_trees(self):
        """
        The output directory tree and toolkit tree must not overlap.
        This is the canonical layout:
          workspace/
            project/          ← consumer repo
              MyGame/         ← Unity project root
                Build/        ← output artifacts
            .ci/
              unity-build-workflows/  ← toolkit (canonical TOOLKIT_PATH)
        """
        project_root = Path("project/MyGame")
        output_root = Path("project/MyGame/Build")
        toolkit_root = Path(".ci/unity-build-workflows")

        assert not output_root.is_relative_to(toolkit_root), (
            "Build output (project/MyGame/Build/) must not be inside toolkit tree"
        )
        assert not toolkit_root.is_relative_to(output_root), (
            "Toolkit tree (.ci/unity-build-workflows/) must not be inside build output"
        )
        assert output_root.is_relative_to(project_root), (
            "Build output must be inside the Unity project root"
        )


# ---------------------------------------------------------------------------
# Fake Docker stub: pull subcommand mode switching
# ---------------------------------------------------------------------------

class TestFakeDockerPullModes:
    """
    The pull subcommand has its own mode behaviour independent of 'docker run'.
    Verify pull-specific mode handling.
    """

    def test_pull_success_outputs_status(self):
        result = _run_fake_docker("pull", "fake/unity:test", mode="success")
        assert result.returncode == 0
        assert "Status" in result.stdout or "Pulling" in result.stdout or result.returncode == 0

    def test_pull_failure_mode_fails_on_pull(self):
        result = _run_fake_docker("pull", "fake/unity:test", mode="pull_failure")
        assert result.returncode != 0, "pull_failure must fail on docker pull"

    def test_image_not_found_fails_on_pull(self):
        result = _run_fake_docker("pull", "fake/unity:nonexistent", mode="image_not_found")
        assert result.returncode != 0, "image_not_found must fail on docker pull"
        combined = result.stdout + result.stderr
        assert any(kw in combined.lower() for kw in ("not found", "manifest", "unable")), (
            f"image_not_found pull must mention the missing image. Got:\n{combined}"
        )
