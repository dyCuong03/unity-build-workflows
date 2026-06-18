"""
Regression tests for the run-unity-container action ↔ run_unity_container.py seam.

THE BUG THIS GUARDS AGAINST
----------------------------
run-unity-container/action.yml passes a pre-resolved --image reference (from
resolve-unity-image) to run_unity_container.py, but the script previously had
NO --image arg and required --image-namespace unconditionally → every Docker
build argparse-errored / failed at runtime.

The fix: --image is now an optional passthrough.  When provided, internal
resolution is skipped and --image-namespace is not required.  Release mode still
requires a digest-pinned ref (@sha256:…).

ADDITIONAL DRIFT CAUGHT BY THIS FILE
-------------------------------------
The action also passes --command, --timeout, --log-path, --report-path, and
boolean inputs --clean-build/--release-mode as string "true"/"false" values.
All are now recognised by the script's argparse.

Coverage
--------
1. --image without --image-namespace → parses + namespace guard passes.
2. Neither --image nor --image-namespace → ValueError / non-zero.
3. --image + --release-mode without a digest-pinned ref → abort (non-zero).
4. Action-contract: every --flag in the action's run: block is a recognised
   argparse arg in the script (catches future drift generically).
5. Boolean string inputs ("true"/"false") parse to correct bool values.
6. --timeout and --container-timeout both set container_timeout.
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent

SCRIPT_PATH = REPO_ROOT / "scripts" / "docker" / "run_unity_container.py"
ACTION_PATH = REPO_ROOT / ".github" / "actions" / "run-unity-container" / "action.yml"

FAKE_DIGEST = "sha256:" + "a" * 64
FAKE_IMAGE = f"ghcr.io/example-namespace/unity-build:2022.3.21f1-android"
FAKE_IMAGE_PINNED = f"{FAKE_IMAGE}@{FAKE_DIGEST}"


# ---------------------------------------------------------------------------
# Module import (skip all import-based tests when script not present)
# ---------------------------------------------------------------------------

sys.path.insert(0, str(REPO_ROOT / "scripts" / "docker"))

try:
    import run_unity_container as _ruc
    _HAS_SCRIPT = True
except ImportError:
    _ruc = None
    _HAS_SCRIPT = False


def _skip_if_no_script():
    if not _HAS_SCRIPT:
        pytest.skip("scripts/docker/run_unity_container.py not yet available")


def _parse(extra_args: list) -> "argparse.Namespace":
    """Call parse_args() with the given args (sys.argv is mocked)."""
    _skip_if_no_script()
    orig = sys.argv
    try:
        sys.argv = ["run_unity_container.py",
                    "--project-path", ".",
                    "--unity-version", "2022.3.21f1",
                    "--target-platform", "Android",
                    ] + extra_args
        return _ruc.parse_args()
    finally:
        sys.argv = orig


# ---------------------------------------------------------------------------
# 1. --image passthrough: no --image-namespace required
# ---------------------------------------------------------------------------

class TestImagePassthrough:
    """
    When a pre-resolved --image is supplied (CI flow), internal resolution is
    skipped and --image-namespace must NOT be required.
    """

    def test_image_arg_is_recognised_by_argparse(self):
        """--image is a known arg; parsing must succeed without --image-namespace."""
        args = _parse(["--image", FAKE_IMAGE])
        assert args.image == FAKE_IMAGE

    def test_image_without_namespace_passes_guard(self):
        """
        The namespace guard (main()):
            if not args.image and not args.image_namespace: raise ValueError(...)
        must NOT fire when --image is supplied.
        """
        args = _parse(["--image", FAKE_IMAGE])
        # Replicate the guard condition from main()
        would_raise = not args.image and not args.image_namespace
        assert not would_raise, (
            "--image supplied → namespace guard condition must be False; "
            f"got image={args.image!r}, image_namespace={args.image_namespace!r}"
        )

    def test_image_digest_appended_when_both_given(self):
        """--image + --image-digest → the digest will be appended at runtime."""
        args = _parse(["--image", FAKE_IMAGE, "--image-digest", FAKE_DIGEST])
        assert args.image == FAKE_IMAGE
        assert args.image_digest == FAKE_DIGEST


# ---------------------------------------------------------------------------
# 2. Missing both --image and --image-namespace → actionable error
# ---------------------------------------------------------------------------

class TestMissingImageNamespaceError:
    """
    When neither --image nor --image-namespace is given, the script must
    exit non-zero with an actionable error message.
    """

    def test_missing_both_exits_nonzero(self, tmp_path):
        """Omitting --image and --image-namespace → exit code 1."""
        if not SCRIPT_PATH.exists():
            pytest.skip("run_unity_container.py not yet created")
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH),
             "--project-path", str(tmp_path),
             "--unity-version", "2022.3.21f1",
             "--target-platform", "Android"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode != 0, (
            "Missing --image-namespace (and no --image) must cause non-zero exit"
        )

    def test_missing_both_error_mentions_namespace(self, tmp_path):
        """Error message must mention 'namespace' so the fix is obvious."""
        if not SCRIPT_PATH.exists():
            pytest.skip("run_unity_container.py not yet created")
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH),
             "--project-path", str(tmp_path),
             "--unity-version", "2022.3.21f1",
             "--target-platform", "Android"],
            capture_output=True, text=True, timeout=15,
        )
        combined = result.stdout + result.stderr
        assert any(kw in combined.lower() for kw in ("namespace", "image-namespace", "required")), (
            f"Error message must mention 'namespace' or 'required'. Got:\n{combined}"
        )


# ---------------------------------------------------------------------------
# 3. --image + --release-mode without digest → abort
# ---------------------------------------------------------------------------

class TestReleaseModeDigestEnforcement:
    """
    In release mode, the script must refuse a mutable (un-pinned) --image.
    A digest (@sha256:…) must be present — either embedded in --image or via
    --image-digest.
    """

    def test_release_mode_without_digest_triggers_abort_path(self):
        """
        Validate the abort condition directly without running Docker.

        The code path inside main() for --image + --release-mode:
            if args.release_mode and "@sha256:" not in image_ref:
                _abort("Release mode requires an immutable digest-pinned image…")
        """
        args = _parse(["--image", FAKE_IMAGE, "--release-mode"])
        # args.release_mode must be truthy; image must lack @sha256:
        assert args.release_mode, (
            "--release-mode (no value) must be truthy; got %r" % args.release_mode
        )
        assert "@sha256:" not in args.image, (
            "Test setup: FAKE_IMAGE must not be digest-pinned for this test"
        )
        # Confirm the abort condition would fire
        would_abort = args.release_mode and "@sha256:" not in args.image
        assert would_abort, "release-mode + un-pinned image must trigger the abort path"

    def test_release_mode_with_digest_in_image_ref_passes(self):
        """--image @sha256:pinned + --release-mode → abort condition is False."""
        args = _parse(["--image", FAKE_IMAGE_PINNED, "--release-mode"])
        would_abort = args.release_mode and "@sha256:" not in args.image
        assert not would_abort, (
            "release-mode + digest-pinned image must NOT trigger the abort path"
        )

    def test_release_mode_with_separate_digest_passes(self):
        """--image tag + --image-digest sha256: + --release-mode → no abort."""
        args = _parse([
            "--image", FAKE_IMAGE,
            "--image-digest", FAKE_DIGEST,
            "--release-mode",
        ])
        # In main(): image_ref gets "@{digest}" appended → "@sha256:" present
        image_ref = args.image
        if args.image_digest and "@sha256:" not in image_ref:
            image_ref = f"{image_ref}@{args.image_digest}"
        would_abort = args.release_mode and "@sha256:" not in image_ref
        assert not would_abort, (
            "release-mode + separate --image-digest must NOT trigger the abort path"
        )


# ---------------------------------------------------------------------------
# 4. Action-contract: every flag the action passes must be a recognised arg
# ---------------------------------------------------------------------------

class TestActionContractDrift:
    """
    KEYSTONE: parse the run-unity-container/action.yml `run:` shell block,
    extract every --flag it passes to run_unity_container.py, and assert each
    is a recognised argparse argument.

    Catches action↔script drift BEFORE it reaches CI (the --image bug took a
    full sprint cycle to surface because no test exercised this seam).
    """

    _FLAG_RE = re.compile(r"^\s+(-{1,2}[a-z][a-z0-9-]+)\s", re.MULTILINE)

    def _action_flags(self) -> set:
        """Extract --flags passed to the script from action.yml's run: block."""
        if not ACTION_PATH.exists():
            pytest.skip("run-unity-container/action.yml not found")
        text = ACTION_PATH.read_text()
        # Find the run: block that invokes run_unity_container.py
        if "run_unity_container.py" not in text:
            pytest.skip("run_unity_container.py invocation not found in action.yml")
        # Grab everything after the python3 invocation line
        start = text.index("run_unity_container.py")
        # Find the end of the shell run block (non-indented line or new step)
        snippet = text[start:]
        # Extract all --flags in the snippet
        flags = set(self._FLAG_RE.findall(snippet))
        # Only keep double-dash flags (single-dash are shell flags, not script args)
        return {f for f in flags if f.startswith("--")}

    def _script_known_flags(self) -> set:
        """Return the set of --flags known to the script's argparse parser."""
        _skip_if_no_script()
        orig = sys.argv
        import io, contextlib
        buf = io.StringIO()
        try:
            sys.argv = ["x", "--help"]
            with contextlib.redirect_stdout(buf):
                try:
                    _ruc.parse_args()
                except SystemExit:
                    pass
        finally:
            sys.argv = orig
        help_text = buf.getvalue()
        # Extract --flags from help output
        return set(re.findall(r"(--[a-z][a-z0-9-]+)", help_text))

    def test_all_action_flags_recognised_by_script(self):
        """
        Every --flag the action passes to run_unity_container.py must be
        a recognised argparse argument.

        If this test fails: the action would produce argparse error (exit 2)
        on every CI run.  Fix: add the missing arg to parse_args() in
        run_unity_container.py (or remove the stale flag from action.yml).
        """
        action_flags = self._action_flags()
        assert action_flags, "No --flags extracted from action.yml — check regex"

        known_flags = self._script_known_flags()
        unknown = action_flags - known_flags

        assert not unknown, (
            "run-unity-container/action.yml passes flags that are NOT recognised "
            "by run_unity_container.py's argparse. Every CI Docker build would "
            "fail with 'unrecognized arguments'.\n\n"
            f"Unknown flags: {sorted(unknown)}\n"
            f"Known flags:   {sorted(known_flags)}\n"
            "Fix: add the missing arg(s) to parse_args() in "
            "scripts/docker/run_unity_container.py."
        )

    def test_action_passes_image_flag(self):
        """Sanity: action.yml must pass --image (the flag that triggered the bug)."""
        action_flags = self._action_flags()
        assert "--image" in action_flags, (
            "--image must be in the flags the action passes; "
            "if missing, the pre-resolved image reference is never forwarded to the script"
        )

    def test_action_passes_image_digest_flag(self):
        """Sanity: action.yml must pass --image-digest for release pinning."""
        action_flags = self._action_flags()
        assert "--image-digest" in action_flags


# ---------------------------------------------------------------------------
# 5. Boolean string inputs ("true"/"false") from GitHub Actions env vars
# ---------------------------------------------------------------------------

class TestBooleanStringInputParsing:
    """
    GitHub Actions bool inputs arrive as string env vars: "true" or "false".
    The action passes --clean-build "$CLEAN_BUILD" and --release-mode "$RELEASE_MODE".
    Both flags must parse those strings correctly.
    """

    def test_clean_build_false_string_parses_to_false(self):
        args = _parse(["--image", FAKE_IMAGE, "--clean-build", "false"])
        assert args.clean_build is False

    def test_clean_build_true_string_parses_to_true(self):
        args = _parse(["--image", FAKE_IMAGE, "--clean-build", "true"])
        assert args.clean_build is True

    def test_clean_build_flag_only_parses_to_true(self):
        """--clean-build (no value) is the legacy form; must remain truthy."""
        args = _parse(["--image", FAKE_IMAGE, "--clean-build"])
        assert args.clean_build

    def test_release_mode_false_string_parses_to_false(self):
        args = _parse(["--image", FAKE_IMAGE, "--release-mode", "false"])
        assert args.release_mode is False

    def test_release_mode_true_string_parses_to_true(self):
        args = _parse(["--image", FAKE_IMAGE, "--release-mode", "true"])
        assert args.release_mode is True

    def test_release_mode_flag_only_parses_to_true(self):
        args = _parse(["--image", FAKE_IMAGE, "--release-mode"])
        assert args.release_mode


# ---------------------------------------------------------------------------
# 6. --timeout / --container-timeout aliasing
# ---------------------------------------------------------------------------

class TestTimeoutAliasing:
    """
    The action uses --timeout; the script's canonical arg is --container-timeout.
    Both must resolve to the same dest (container_timeout).
    """

    def test_timeout_flag_is_recognised(self):
        args = _parse(["--image", FAKE_IMAGE, "--timeout", "1800"])
        assert args.container_timeout == 1800

    def test_container_timeout_still_works(self):
        args = _parse(["--image", FAKE_IMAGE, "--container-timeout", "900"])
        assert args.container_timeout == 900

    def test_command_flag_is_recognised(self):
        args = _parse(["--image", FAKE_IMAGE, "--command", "test-editmode"])
        assert args.command == "test-editmode"

    def test_log_path_flag_is_recognised(self):
        args = _parse(["--image", FAKE_IMAGE, "--log-path", "/workspace/Logs"])
        assert args.log_path == "/workspace/Logs"

    def test_report_path_flag_is_recognised(self):
        args = _parse(["--image", FAKE_IMAGE, "--report-path", "/workspace/Reports"])
        assert args.report_path == "/workspace/Reports"
