"""
test_build_flow.py
==================
Validates resolve_build_flow.sh by invoking it via subprocess with controlled
environment and asserting KEY=value outputs against the BRANCH_FLOW_CONTRACT.md
rules table.

Covered scenarios
-----------------
F1   PR → develop    flow-type=pr-develop,  validation only, tests
F2   PR → staging    flow-type=pr-staging,  validation only, tests
F3   PR → release-*  flow-type=pr-release,  addressables, tests, no binary builds
F4   push → develop  flow-type=push-develop, android+webgl, env=development
F5   push → staging  flow-type=push-staging, android+webgl+linux64+linuxserver
F6   push → release-1.2   flow-type=push-release, all 4 platforms, signing
F7   push → release/1.2   same as F6 (alternate branch naming convention)
F8   dispatch All          4 core platforms true, ios false
F9   dispatch Android      only build-android true
F10  dispatch iOS          only build-ios true
F11  run-tests=false forces test-mode=None
F12  push → main (no-match) flow-type=none, all build-* false
F13  build-ios is never true except manual iOS dispatch
"""

import os
import subprocess
from pathlib import Path
from typing import Dict

import pytest

REPO_ROOT = Path(__file__).parent.parent
FLOW_SCRIPT = REPO_ROOT / "scripts" / "common" / "resolve_build_flow.sh"

EXPECTED_KEYS = {
    "flow-type",
    "environment",
    "run-tests",
    "test-mode",
    "build-addressables",
    "build-android",
    "build-webgl",
    "build-linux64",
    "build-linuxserver",
    "build-ios",
    "signing",
}

ALL_BUILD_PLATFORM_KEYS = [
    "build-android",
    "build-webgl",
    "build-linux64",
    "build-linuxserver",
    "build-ios",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_flow(env_overrides: dict, timeout: int = 10) -> subprocess.CompletedProcess:
    """Run the flow resolver with a clean, controlled environment."""
    env: Dict[str, str] = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
    }
    env.update({k: str(v) for k, v in env_overrides.items()})
    return subprocess.run(
        ["bash", str(FLOW_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def parse_outputs(stdout: str) -> Dict[str, str]:
    """Parse KEY=value lines from script stdout."""
    result: Dict[str, str] = {}
    for line in stdout.splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def assert_all_builds_false(outputs: Dict[str, str], msg: str = ""):
    """Assert every build-<platform> output is 'false'."""
    for key in ALL_BUILD_PLATFORM_KEYS:
        assert outputs.get(key) == "false", (
            f"{msg} — expected {key}=false, got {outputs.get(key)!r}"
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _require_script():
    if not FLOW_SCRIPT.exists():
        pytest.skip(f"Flow script not found: {FLOW_SCRIPT}")


@pytest.fixture(scope="module")
def _check_script_once():
    if not FLOW_SCRIPT.exists():
        pytest.skip(f"Flow script not found: {FLOW_SCRIPT}")


# ---------------------------------------------------------------------------
# Smoke — script runs and emits all expected keys
# ---------------------------------------------------------------------------

class TestScriptSmoke:
    def test_exits_zero_for_unknown_event(self):
        r = run_flow({"EVENT_NAME": "schedule"})
        assert r.returncode == 0

    def test_emits_all_expected_output_keys(self):
        r = run_flow({"EVENT_NAME": "push", "REF_NAME": "develop"})
        assert r.returncode == 0
        outputs = parse_outputs(r.stdout)
        missing = EXPECTED_KEYS - set(outputs.keys())
        assert not missing, f"Script missing output keys: {missing}"

    def test_all_values_are_non_empty(self):
        r = run_flow({"EVENT_NAME": "push", "REF_NAME": "develop"})
        outputs = parse_outputs(r.stdout)
        empty = [k for k in EXPECTED_KEYS if outputs.get(k, "") == ""]
        assert not empty, f"Empty output values for keys: {empty}"

    def test_diagnostic_goes_to_stderr_not_stdout(self):
        r = run_flow({"EVENT_NAME": "push", "REF_NAME": "develop"})
        # stdout must contain ONLY KEY=value lines (no log lines)
        for line in r.stdout.splitlines():
            line = line.strip()
            if line:
                assert "=" in line, (
                    f"Non KEY=value line found in stdout: {line!r}"
                )


# ---------------------------------------------------------------------------
# F1 – PR → develop
# ---------------------------------------------------------------------------

class TestPRDevelop:
    @pytest.fixture(autouse=True)
    def _result(self):
        r = run_flow({"EVENT_NAME": "pull_request", "BASE_REF": "develop"})
        assert r.returncode == 0
        self.out = parse_outputs(r.stdout)

    def test_flow_type(self):
        assert self.out["flow-type"] == "pr-develop"

    def test_environment_is_development(self):
        assert self.out["environment"] == "development"

    def test_run_tests_true(self):
        assert self.out["run-tests"] == "true"

    def test_no_binary_builds(self):
        assert_all_builds_false(self.out, "F1 PR→develop")

    def test_build_addressables_false(self):
        assert self.out["build-addressables"] == "false"

    def test_signing_none(self):
        assert self.out["signing"] == "none"


# ---------------------------------------------------------------------------
# F2 – PR → staging
# ---------------------------------------------------------------------------

class TestPRStaging:
    @pytest.fixture(autouse=True)
    def _result(self):
        r = run_flow({"EVENT_NAME": "pull_request", "BASE_REF": "staging"})
        assert r.returncode == 0
        self.out = parse_outputs(r.stdout)

    def test_flow_type(self):
        assert self.out["flow-type"] == "pr-staging"

    def test_environment_is_staging(self):
        assert self.out["environment"] == "staging"

    def test_run_tests_true(self):
        assert self.out["run-tests"] == "true"

    def test_no_binary_builds(self):
        assert_all_builds_false(self.out, "F2 PR→staging")

    def test_signing_none(self):
        assert self.out["signing"] == "none"


# ---------------------------------------------------------------------------
# F3 – PR → release-*  (using release-1.2)
# ---------------------------------------------------------------------------

class TestPRRelease:
    @pytest.fixture(autouse=True)
    def _result(self):
        r = run_flow({"EVENT_NAME": "pull_request", "BASE_REF": "release-1.2"})
        assert r.returncode == 0
        self.out = parse_outputs(r.stdout)

    def test_flow_type(self):
        assert self.out["flow-type"] == "pr-release"

    def test_environment_is_production(self):
        assert self.out["environment"] == "production"

    def test_run_tests_true(self):
        assert self.out["run-tests"] == "true"

    def test_build_addressables_true(self):
        assert self.out["build-addressables"] == "true"

    def test_no_binary_builds(self):
        assert_all_builds_false(self.out, "F3 PR→release-1.2")

    def test_signing_none(self):
        assert self.out["signing"] == "none"


# ---------------------------------------------------------------------------
# F4 – push → develop
# ---------------------------------------------------------------------------

class TestPushDevelop:
    @pytest.fixture(autouse=True)
    def _result(self):
        r = run_flow({"EVENT_NAME": "push", "REF_NAME": "develop"})
        assert r.returncode == 0
        self.out = parse_outputs(r.stdout)

    def test_flow_type(self):
        assert self.out["flow-type"] == "push-develop"

    def test_environment_is_development(self):
        assert self.out["environment"] == "development"

    def test_run_tests_true(self):
        assert self.out["run-tests"] == "true"

    def test_build_android_true(self):
        assert self.out["build-android"] == "true"

    def test_build_webgl_true(self):
        assert self.out["build-webgl"] == "true"

    def test_build_linux64_false(self):
        assert self.out["build-linux64"] == "false"

    def test_build_linuxserver_false(self):
        assert self.out["build-linuxserver"] == "false"

    def test_build_ios_false(self):
        assert self.out["build-ios"] == "false"

    def test_build_addressables_false(self):
        assert self.out["build-addressables"] == "false"

    def test_signing_none(self):
        assert self.out["signing"] == "none"


# ---------------------------------------------------------------------------
# F5 – push → staging
# ---------------------------------------------------------------------------

class TestPushStaging:
    @pytest.fixture(autouse=True)
    def _result(self):
        r = run_flow({"EVENT_NAME": "push", "REF_NAME": "staging"})
        assert r.returncode == 0
        self.out = parse_outputs(r.stdout)

    def test_flow_type(self):
        assert self.out["flow-type"] == "push-staging"

    def test_environment_is_staging(self):
        assert self.out["environment"] == "staging"

    def test_run_tests_true(self):
        assert self.out["run-tests"] == "true"

    def test_build_android_true(self):
        assert self.out["build-android"] == "true"

    def test_build_webgl_true(self):
        assert self.out["build-webgl"] == "true"

    def test_build_linux64_true(self):
        assert self.out["build-linux64"] == "true"

    def test_build_linuxserver_true(self):
        assert self.out["build-linuxserver"] == "true"

    def test_build_ios_false(self):
        assert self.out["build-ios"] == "false"

    def test_build_addressables_false(self):
        assert self.out["build-addressables"] == "false"

    def test_signing_none(self):
        assert self.out["signing"] == "none"


# ---------------------------------------------------------------------------
# F6 – push → release-1.2
# ---------------------------------------------------------------------------

class TestPushReleaseDash:
    """push → release-1.2 (hyphen-separated branch name)."""

    @pytest.fixture(autouse=True)
    def _result(self):
        r = run_flow({"EVENT_NAME": "push", "REF_NAME": "release-1.2"})
        assert r.returncode == 0
        self.out = parse_outputs(r.stdout)

    def test_flow_type(self):
        assert self.out["flow-type"] == "push-release"

    def test_environment_is_production(self):
        assert self.out["environment"] == "production"

    def test_run_tests_true(self):
        assert self.out["run-tests"] == "true"

    def test_build_addressables_true(self):
        assert self.out["build-addressables"] == "true"

    def test_build_android_true(self):
        assert self.out["build-android"] == "true"

    def test_build_webgl_true(self):
        assert self.out["build-webgl"] == "true"

    def test_build_linux64_true(self):
        assert self.out["build-linux64"] == "true"

    def test_build_linuxserver_true(self):
        assert self.out["build-linuxserver"] == "true"

    def test_build_ios_false(self):
        assert self.out["build-ios"] == "false"

    def test_signing_android_release(self):
        assert self.out["signing"] == "android-release"


# ---------------------------------------------------------------------------
# F7 – push → release/1.2  (slash-separated branch name)
# ---------------------------------------------------------------------------

class TestPushReleaseSlash:
    """push → release/1.2 (slash-separated — alternate naming convention)."""

    @pytest.fixture(autouse=True)
    def _result(self):
        r = run_flow({"EVENT_NAME": "push", "REF_NAME": "release/1.2"})
        assert r.returncode == 0
        self.out = parse_outputs(r.stdout)

    def test_flow_type(self):
        assert self.out["flow-type"] == "push-release"

    def test_environment_is_production(self):
        assert self.out["environment"] == "production"

    def test_all_core_platforms_true(self):
        for key in ["build-android", "build-webgl", "build-linux64", "build-linuxserver"]:
            assert self.out[key] == "true", f"Expected {key}=true for push→release/1.2"

    def test_build_ios_false(self):
        assert self.out["build-ios"] == "false"

    def test_signing_android_release(self):
        assert self.out["signing"] == "android-release"


# ---------------------------------------------------------------------------
# F8 – workflow_dispatch / IN_PLATFORM=All
# ---------------------------------------------------------------------------

class TestDispatchAll:
    @pytest.fixture(autouse=True)
    def _result(self):
        r = run_flow({
            "EVENT_NAME": "workflow_dispatch",
            "IN_PLATFORM": "All",
            "IN_ENVIRONMENT": "production",
            "IN_RUN_TESTS": "false",
            "IN_TEST_MODE": "All",
            "IN_BUILD_ADDRESSABLES": "false",
        })
        assert r.returncode == 0
        self.out = parse_outputs(r.stdout)

    def test_flow_type_manual(self):
        assert self.out["flow-type"] == "manual"

    def test_environment_passed_through(self):
        assert self.out["environment"] == "production"

    def test_build_android_true(self):
        assert self.out["build-android"] == "true"

    def test_build_webgl_true(self):
        assert self.out["build-webgl"] == "true"

    def test_build_linux64_true(self):
        assert self.out["build-linux64"] == "true"

    def test_build_linuxserver_true(self):
        assert self.out["build-linuxserver"] == "true"

    def test_build_ios_false_for_all(self):
        """iOS must be excluded from 'All' — never auto-built."""
        assert self.out["build-ios"] == "false"


# ---------------------------------------------------------------------------
# F9 – workflow_dispatch / IN_PLATFORM=Android
# ---------------------------------------------------------------------------

class TestDispatchAndroid:
    @pytest.fixture(autouse=True)
    def _result(self):
        r = run_flow({
            "EVENT_NAME": "workflow_dispatch",
            "IN_PLATFORM": "Android",
            "IN_ENVIRONMENT": "development",
            "IN_RUN_TESTS": "false",
            "IN_TEST_MODE": "All",
            "IN_BUILD_ADDRESSABLES": "false",
        })
        assert r.returncode == 0
        self.out = parse_outputs(r.stdout)

    def test_only_android_true(self):
        assert self.out["build-android"] == "true"

    def test_other_platforms_false(self):
        for key in ["build-webgl", "build-linux64", "build-linuxserver", "build-ios"]:
            assert self.out[key] == "false", f"Expected {key}=false for Android dispatch"


# ---------------------------------------------------------------------------
# F10 – workflow_dispatch / IN_PLATFORM=iOS
# ---------------------------------------------------------------------------

class TestDispatchIOS:
    @pytest.fixture(autouse=True)
    def _result(self):
        r = run_flow({
            "EVENT_NAME": "workflow_dispatch",
            "IN_PLATFORM": "iOS",
            "IN_ENVIRONMENT": "production",
            "IN_RUN_TESTS": "false",
            "IN_TEST_MODE": "All",
            "IN_BUILD_ADDRESSABLES": "false",
        })
        assert r.returncode == 0
        self.out = parse_outputs(r.stdout)

    def test_build_ios_true(self):
        """Only manual iOS dispatch should set build-ios=true."""
        assert self.out["build-ios"] == "true"

    def test_core_platforms_false(self):
        for key in ["build-android", "build-webgl", "build-linux64", "build-linuxserver"]:
            assert self.out[key] == "false", f"Expected {key}=false for iOS dispatch"


# ---------------------------------------------------------------------------
# F11 – run-tests=false forces test-mode=None
# ---------------------------------------------------------------------------

class TestRunTestsFalseNormalization:
    def test_push_develop_run_tests_false_test_mode_none(self):
        """F11: Even automatic push-develop, if run-tests were false, test-mode=None."""
        # Simulate push→develop but force run-tests context by setting env
        # (script always sets run_tests=true for push-develop;
        # the normalisation rule fires when run_tests=false regardless of how it's set)
        # Use dispatch with run-tests=false to exercise the normalisation path.
        r = run_flow({
            "EVENT_NAME": "workflow_dispatch",
            "IN_PLATFORM": "Android",
            "IN_ENVIRONMENT": "development",
            "IN_RUN_TESTS": "false",
            "IN_TEST_MODE": "EditMode",  # would be overridden to None
            "IN_BUILD_ADDRESSABLES": "false",
        })
        assert r.returncode == 0
        out = parse_outputs(r.stdout)
        assert out["run-tests"] == "false"
        assert out["test-mode"] == "None", (
            f"F11: test-mode should be 'None' when run-tests=false, got {out['test-mode']!r}"
        )

    def test_push_develop_preserves_test_mode_when_run_tests_true(self):
        """F11 inverse: push→develop sets run-tests=true → test-mode=All (not None)."""
        r = run_flow({"EVENT_NAME": "push", "REF_NAME": "develop"})
        assert r.returncode == 0
        out = parse_outputs(r.stdout)
        assert out["run-tests"] == "true"
        assert out["test-mode"] != "None", (
            f"test-mode should not be None when run-tests=true, got {out['test-mode']!r}"
        )


# ---------------------------------------------------------------------------
# F12 – push → main (no-match branch) → flow-type=none, all builds false
# ---------------------------------------------------------------------------

class TestNoMatchBranch:
    @pytest.fixture(autouse=True)
    def _result(self):
        r = run_flow({"EVENT_NAME": "push", "REF_NAME": "main"})
        assert r.returncode == 0
        self.out = parse_outputs(r.stdout)

    def test_flow_type_none(self):
        assert self.out["flow-type"] == "none"

    def test_all_builds_false(self):
        assert_all_builds_false(self.out, "F12 push→main")

    def test_build_addressables_false(self):
        assert self.out["build-addressables"] == "false"

    def test_run_tests_false(self):
        assert self.out["run-tests"] == "false"

    def test_signing_none(self):
        assert self.out["signing"] == "none"


# ---------------------------------------------------------------------------
# F13 – build-ios is never true except manual iOS dispatch
# ---------------------------------------------------------------------------

class TestIOSNeverAutomatic:
    """F13: build-ios must be false for all automatic triggers."""

    @pytest.mark.parametrize("env", [
        {"EVENT_NAME": "push", "REF_NAME": "develop"},
        {"EVENT_NAME": "push", "REF_NAME": "staging"},
        {"EVENT_NAME": "push", "REF_NAME": "release-1.2"},
        {"EVENT_NAME": "push", "REF_NAME": "release/2.0"},
        {"EVENT_NAME": "pull_request", "BASE_REF": "develop"},
        {"EVENT_NAME": "pull_request", "BASE_REF": "staging"},
        {"EVENT_NAME": "pull_request", "BASE_REF": "release-3.0"},
        {"EVENT_NAME": "workflow_dispatch", "IN_PLATFORM": "All",
         "IN_ENVIRONMENT": "production", "IN_RUN_TESTS": "false",
         "IN_TEST_MODE": "All", "IN_BUILD_ADDRESSABLES": "false"},
        {"EVENT_NAME": "workflow_dispatch", "IN_PLATFORM": "Android",
         "IN_ENVIRONMENT": "production", "IN_RUN_TESTS": "false",
         "IN_TEST_MODE": "All", "IN_BUILD_ADDRESSABLES": "false"},
    ])
    def test_build_ios_false(self, env):
        r = run_flow(env)
        assert r.returncode == 0
        out = parse_outputs(r.stdout)
        assert out["build-ios"] == "false", (
            f"F13: build-ios must be false for {env}, got {out['build-ios']!r}"
        )

    def test_build_ios_true_only_for_ios_dispatch(self):
        r = run_flow({
            "EVENT_NAME": "workflow_dispatch",
            "IN_PLATFORM": "iOS",
            "IN_ENVIRONMENT": "production",
            "IN_RUN_TESTS": "false",
            "IN_TEST_MODE": "All",
            "IN_BUILD_ADDRESSABLES": "false",
        })
        assert r.returncode == 0
        out = parse_outputs(r.stdout)
        assert out["build-ios"] == "true", (
            "F13: build-ios should be true for explicit iOS dispatch"
        )


# ---------------------------------------------------------------------------
# Dispatch — all single-platform variants
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("platform,expected_true", [
    ("WebGL",       "build-webgl"),
    ("Linux64",     "build-linux64"),
    ("LinuxServer", "build-linuxserver"),
])
def test_dispatch_single_platform_exclusive(platform, expected_true):
    """Each single-platform dispatch enables exactly one build-* key."""
    r = run_flow({
        "EVENT_NAME": "workflow_dispatch",
        "IN_PLATFORM": platform,
        "IN_ENVIRONMENT": "development",
        "IN_RUN_TESTS": "false",
        "IN_TEST_MODE": "All",
        "IN_BUILD_ADDRESSABLES": "false",
    })
    assert r.returncode == 0
    out = parse_outputs(r.stdout)
    assert out[expected_true] == "true", f"Expected {expected_true}=true for {platform}"
    for key in ALL_BUILD_PLATFORM_KEYS:
        if key != expected_true:
            assert out[key] == "false", f"Expected {key}=false for {platform} dispatch"
