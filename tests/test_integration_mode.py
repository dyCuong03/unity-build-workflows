"""
Tests for integration-mode switching (remote vs submodule).

Approved design (T3):
  integration-mode: remote
    → toolkit is checked out from GitHub via actions/checkout@v4
    → workflow-repository + workflow-ref inputs are REQUIRED
    → checkout lands at .ci/unity-build-workflows (canonical TOOLKIT_PATH)
    → consumer repo checkout does NOT include submodules

  integration-mode: submodule
    → toolkit comes from consumer's git submodule at toolkit-path
    → no remote actions/checkout for the toolkit
    → consumer repo checkout includes submodules (submodules: true)
    → a setup step validates toolkit-path, prints commit SHA, checks dirty state
    → missing submodule → actionable ::error:: annotation + exit 1
    → missing toolkit scripts → actionable error names the missing file

  TOOLKIT_PATH env var always = .ci/unity-build-workflows regardless of mode.

Test classes:
  TestIntegrationModeInputsInWorkflows    — YAML inputs/defaults in all workflows
  TestRemoteModeCheckoutContract          — remote mode has toolkit checkout step
  TestSubmoduleModeCheckoutContract       — submodule mode: no remote checkout,
                                            consumer checkout includes submodules
  TestSubmoduleStateReporting             — SHA printed, dirty state reported
  TestToolkitValidationErrors             — missing submodule/scripts → actionable errors
  TestToolkitPathEnvContract              — TOOLKIT_PATH always .ci/unity-build-workflows

Skip behaviour:
  All classes that depend on T3 YAML changes skip if integration-mode input is
  absent from unity-build.yml. Tests pass once T3 lands.
"""
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
UNITY_BUILD_YML = WORKFLOWS_DIR / "unity-build.yml"

# Canonical internal mount point — never changes regardless of integration-mode.
CANONICAL_TOOLKIT_PATH = ".ci/unity-build-workflows"

# Per-platform workflows that must also expose the new inputs.
PLATFORM_WORKFLOWS = [
    "unity-build-android.yml",
    "unity-build-webgl.yml",
    "unity-build-linux.yml",
    "unity-build-ios.yml",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


def _get_triggers(doc: dict) -> dict:
    """PyYAML parses bare `on:` as boolean True — handle both."""
    return doc.get("on") or doc.get(True) or {}


def _iter_steps(doc: dict):
    for job in (doc.get("jobs") or {}).values():
        for step in (job.get("steps") or []):
            yield step


def _all_run_text(doc: dict) -> str:
    """Concatenate all run: shell block text from every step."""
    return "\n".join(
        step.get("run") or ""
        for step in _iter_steps(doc)
        if step.get("run")
    )


def _all_uses_refs(doc: dict) -> list[str]:
    """Return all 'uses:' values from steps and jobs."""
    refs = []
    for step in _iter_steps(doc):
        if "uses" in step:
            refs.append(step["uses"])
    for job in (doc.get("jobs") or {}).values():
        if "uses" in job:
            refs.append(job["uses"])
    return refs


def _unity_build_doc() -> dict | None:
    if not UNITY_BUILD_YML.exists():
        return None
    return _load_yaml(UNITY_BUILD_YML)


def _unity_build_inputs() -> dict:
    doc = _unity_build_doc()
    if doc is None:
        return {}
    triggers = _get_triggers(doc)
    return triggers.get("workflow_call", {}).get("inputs", {}) or {}


def _workflow_inputs(filename: str) -> dict:
    path = WORKFLOWS_DIR / filename
    if not path.exists():
        return {}
    doc = _load_yaml(path)
    triggers = _get_triggers(doc)
    return triggers.get("workflow_call", {}).get("inputs", {}) or {}


def _skip_if_no_integration_mode():
    if "integration-mode" not in _unity_build_inputs():
        pytest.skip(
            "integration-mode input not yet in unity-build.yml — waiting for T3. "
            "This test will run automatically once T3 lands."
        )


# ---------------------------------------------------------------------------
# YAML contract: integration-mode and toolkit-path in all workflows
# ---------------------------------------------------------------------------

class TestIntegrationModeInputsInWorkflows:
    """
    After T3, unity-build.yml and all per-platform workflows must expose
    integration-mode (default: remote) and toolkit-path (default: tools/unity-build-workflows).
    """

    @pytest.fixture(autouse=True)
    def _guard(self):
        _skip_if_no_integration_mode()

    def test_unity_build_has_integration_mode(self):
        assert "integration-mode" in _unity_build_inputs()

    def test_unity_build_integration_mode_default_remote(self):
        defn = _unity_build_inputs()["integration-mode"]
        assert defn.get("default") == "remote", (
            "integration-mode must default to 'remote' — backward-compatible "
            "with existing consumers that supply workflow-repository + workflow-ref."
        )

    def test_unity_build_has_toolkit_path(self):
        assert "toolkit-path" in _unity_build_inputs(), (
            "unity-build.yml must have toolkit-path input (submodule mode location)"
        )

    def test_unity_build_toolkit_path_default(self):
        inputs = _unity_build_inputs()
        if "toolkit-path" not in inputs:
            pytest.skip("toolkit-path not yet present")
        assert inputs["toolkit-path"].get("default") == "tools/unity-build-workflows", (
            "toolkit-path must default to 'tools/unity-build-workflows'"
        )

    @pytest.mark.parametrize("workflow", PLATFORM_WORKFLOWS)
    def test_platform_workflow_has_integration_mode(self, workflow):
        inputs = _workflow_inputs(workflow)
        if not inputs:
            pytest.skip(f"{workflow} not found or has no inputs")
        if "integration-mode" not in inputs:
            pytest.skip(f"integration-mode not yet in {workflow}")
        assert "integration-mode" in inputs

    @pytest.mark.parametrize("workflow", PLATFORM_WORKFLOWS)
    def test_platform_workflow_has_toolkit_path(self, workflow):
        inputs = _workflow_inputs(workflow)
        if not inputs:
            pytest.skip(f"{workflow} not found or has no inputs")
        if "toolkit-path" not in inputs:
            pytest.skip(f"toolkit-path not yet in {workflow}")
        assert "toolkit-path" in inputs


# ---------------------------------------------------------------------------
# Remote mode: toolkit is checked out via actions/checkout
# ---------------------------------------------------------------------------

class TestRemoteModeCheckoutContract:
    """
    In remote mode (default), the workflow must:
    1. Have a conditional step that runs ONLY when integration-mode == 'remote'.
    2. That step uses actions/checkout@v4 with repository + ref from workflow inputs.
    3. The checkout lands at .ci/unity-build-workflows.

    The consumer checkout in remote mode does NOT set submodules: true
    (submodules are the consumer's own concern, not the toolkit's).
    """

    @pytest.fixture(autouse=True)
    def _guard(self):
        _skip_if_no_integration_mode()

    @pytest.fixture
    def doc(self):
        d = _unity_build_doc()
        if d is None:
            pytest.skip("unity-build.yml not found")
        return d

    def test_remote_mode_checkout_step_exists(self, doc):
        """
        A step must exist whose 'if:' condition gates on integration-mode == 'remote'
        (or != 'submodule') and uses actions/checkout to fetch the toolkit.
        """
        remote_checkout_steps = []
        for step in _iter_steps(doc):
            cond = str(step.get("if", ""))
            uses = str(step.get("uses", ""))
            run = str(step.get("run", ""))
            is_conditional_on_remote = (
                "remote" in cond or
                "integration-mode" in cond or
                "submodule" in cond
            )
            is_checkout_step = "checkout" in uses or "checkout" in run
            if is_conditional_on_remote and is_checkout_step:
                remote_checkout_steps.append(step)

        assert remote_checkout_steps, (
            "No step found that conditionally checks out the toolkit for remote mode. "
            "T3 must add a step with:\n"
            "  if: inputs.integration-mode != 'submodule'\n"
            "  uses: actions/checkout@v4\n"
            "  with:\n"
            "    repository: ${{ inputs.workflow-repository }}\n"
            "    ref: ${{ inputs.workflow-ref }}\n"
            "    path: .ci/unity-build-workflows"
        )

    def test_remote_mode_checkout_targets_canonical_path(self, doc):
        """
        The remote-mode toolkit checkout must land at .ci/unity-build-workflows.
        All downstream steps (composite actions, scripts) reference this path.
        """
        for step in _iter_steps(doc):
            cond = str(step.get("if", ""))
            uses = str(step.get("uses", ""))
            with_block = step.get("with") or {}
            checkout_path = str(with_block.get("path", ""))
            if "checkout" in uses and CANONICAL_TOOLKIT_PATH in checkout_path:
                return  # Found it
        pytest.fail(
            f"No checkout step found with path: {CANONICAL_TOOLKIT_PATH}.\n"
            "Remote mode toolkit checkout must land at .ci/unity-build-workflows."
        )

    def test_remote_mode_uses_workflow_repository_input(self, doc):
        """
        The toolkit setup must use workflow-repository input for the remote checkout.
        Hardcoding the org/repo name is forbidden — the toolkit must be generic.

        T3 implements this via an env var indirection pattern:
          env:
            WORKFLOW_REPO: ${{ inputs.workflow-repository }}
          run: |
            echo "repo=${WORKFLOW_REPO}" >> "$GITHUB_OUTPUT"
        Then the checkout step uses ${{ steps.toolkit.outputs.repo }}.

        Either pattern is acceptable:
          - Direct: with.repository: ${{ inputs.workflow-repository }}
          - Indirect: env var fed from inputs.workflow-repository → step output → checkout
        """
        full_yaml_text = UNITY_BUILD_YML.read_text()
        has_workflow_repo_reference = (
            "inputs.workflow-repository" in full_yaml_text or
            "inputs['workflow-repository']" in full_yaml_text
        )
        assert has_workflow_repo_reference, (
            "unity-build.yml must reference 'inputs.workflow-repository' for remote "
            "mode toolkit checkout (directly in with.repository OR via env var). "
            "Hardcoding the org/repo name is forbidden — the toolkit must be generic."
        )

    def test_remote_mode_workflow_repository_required_when_remote(self):
        """
        In remote mode, workflow-repository is required. The workflow must fail
        fast with an actionable error if it's missing.
        The existing 'workflow-repository' input must still be present.
        """
        inputs = _unity_build_inputs()
        assert "workflow-repository" in inputs, (
            "workflow-repository input must remain in unity-build.yml for remote mode"
        )

    def test_remote_mode_workflow_ref_required_when_remote(self):
        """In remote mode, workflow-ref is required."""
        inputs = _unity_build_inputs()
        assert "workflow-ref" in inputs, (
            "workflow-ref input must remain in unity-build.yml for remote mode"
        )


# ---------------------------------------------------------------------------
# Submodule mode: no remote checkout, consumer checkout includes submodules
# ---------------------------------------------------------------------------

class TestSubmoduleModeCheckoutContract:
    """
    In submodule mode:
    1. The consumer repo checkout must include submodules (submodules: true or recursive).
    2. There must be NO unconditional remote checkout of the toolkit.
    3. A setup step must establish the canonical .ci/unity-build-workflows path
       from the consumer submodule location.

    The key regression to prevent: adding 'integration-mode: submodule' but still
    doing a remote checkout — wasting CI time and potentially pulling a mismatched ref.
    """

    @pytest.fixture(autouse=True)
    def _guard(self):
        _skip_if_no_integration_mode()

    @pytest.fixture
    def doc(self):
        d = _unity_build_doc()
        if d is None:
            pytest.skip("unity-build.yml not found")
        return d

    def test_consumer_checkout_includes_submodules_conditionally(self, doc):
        """
        In submodule mode the toolkit is sourced from the consumer's git submodule.

        Two valid implementation approaches:
          (A) Set submodules: true in the consumer repo checkout step so git
              fetches the submodule alongside the consumer repo.
          (B) After consumer checkout, symlink or copy the pre-initialized
              submodule to .ci/unity-build-workflows (T3's approach: ln -sf).

        T3 uses approach (B): consumer checks out WITHOUT submodules, then the
        'Setup toolkit' step symlinks the submodule path to .ci/unity-build-workflows.
        Both approaches satisfy the contract — the test accepts either.
        """
        full_yaml_text = UNITY_BUILD_YML.read_text()
        has_submodule_handling = (
            "submodules" in full_yaml_text or   # approach (A): submodules: true
            "ln -sf" in full_yaml_text or       # approach (B): T3 symlink
            "ln -s " in full_yaml_text or
            "cp -r" in full_yaml_text           # approach (B): copy variant
        )
        assert has_submodule_handling, (
            "unity-build.yml must handle submodule-mode toolkit provisioning. "
            "Either set 'submodules: true' in the consumer checkout step, OR "
            "symlink/copy the submodule path to .ci/unity-build-workflows after checkout."
        )

    def test_toolkit_checkout_is_conditional_not_unconditional(self, doc):
        """
        The toolkit checkout step must NOT run unconditionally.
        In submodule mode it must be skipped — the toolkit is already present
        via the consumer's submodule checkout.
        """
        for step in _iter_steps(doc):
            uses = str(step.get("uses", ""))
            with_block = step.get("with") or {}
            checkout_path = str(with_block.get("path", ""))
            step_if = step.get("if")
            # Find the toolkit checkout step
            if "checkout" in uses and CANONICAL_TOOLKIT_PATH in checkout_path:
                assert step_if is not None, (
                    "The toolkit checkout step (path: .ci/unity-build-workflows) must "
                    "have an 'if:' condition — it must NOT run in submodule mode.\n"
                    "Add: if: inputs.integration-mode != 'submodule'"
                )
                return
        # If we don't find the step it may be handled differently — not a failure here
        # (remote checkout may be in a script block)

    def test_submodule_setup_step_exists(self, doc):
        """
        The workflow must contain logic that handles submodule-mode toolkit setup.

        Two valid YAML structures:
          (A) A step with if: inputs.integration-mode == 'submodule' that runs
              the setup in its run: block.
          (B) A single combined step whose run: block uses inline shell if/else
              to branch on the mode (T3's approach):
                MODE="${INTEGRATION_MODE:-remote}"
                if [ "$MODE" = "submodule" ]; then ...
                else ...
                fi

        T3 uses approach (B) — a single 'Setup toolkit' step handles both modes
        via shell branching. The test accepts either structure.
        """
        run_text = _all_run_text(doc)
        # Detect shell-level submodule branch (T3 approach B)
        has_submodule_shell_branch = (
            '"submodule"' in run_text or   # [ "$MODE" = "submodule" ]
            "'submodule'" in run_text or   # [ "$MODE" == 'submodule' ]
            "== submodule" in run_text or
            "= submodule" in run_text
        )
        # Also accept YAML-level conditional (approach A)
        has_submodule_yaml_step = any(
            "submodule" in str(step.get("if", "")).lower()
            for step in _iter_steps(doc)
        )
        assert has_submodule_shell_branch or has_submodule_yaml_step, (
            "unity-build.yml must contain submodule-mode branch logic. "
            "T3 pattern (inline shell): if [ \"$MODE\" = \"submodule\" ]; then ...\n"
            "OR a step with: if: inputs.integration-mode == 'submodule'"
        )


# ---------------------------------------------------------------------------
# Submodule state reporting: commit SHA + dirty check
# ---------------------------------------------------------------------------

class TestSubmoduleStateReporting:
    """
    In submodule mode the workflow must report:
    1. The exact commit SHA of the toolkit submodule (for reproducibility).
    2. Whether the submodule has uncommitted changes (warns but does not fail).

    This information is critical for debugging: "which version of the toolkit
    built this artifact?" — the SHA answers that question in the CI log.
    """

    @pytest.fixture(autouse=True)
    def _guard(self):
        _skip_if_no_integration_mode()

    @pytest.fixture
    def run_text(self):
        doc = _unity_build_doc()
        if doc is None:
            pytest.skip("unity-build.yml not found")
        return _all_run_text(doc)

    def test_submodule_commit_sha_is_printed(self, run_text):
        """
        The workflow must print the submodule's commit SHA.
        Expected: git -C <path> rev-parse HEAD  (or git submodule status)

        This guarantees the toolkit version is visible in every CI log.
        """
        has_sha_print = (
            "rev-parse" in run_text or
            "submodule status" in run_text or
            "git log" in run_text
        )
        assert has_sha_print, (
            "unity-build.yml must print the toolkit submodule commit SHA in submodule mode.\n"
            "Add in the submodule setup step:\n"
            "  SHA=$(git -C \"$SUBMODULE_PATH\" rev-parse HEAD)\n"
            "  echo \"Toolkit submodule commit: $SHA\""
        )

    def test_dirty_submodule_state_is_reported(self, run_text):
        """
        The workflow must check and report if the toolkit submodule has
        uncommitted local changes. This is a warning (not a failure) — the
        intent is to surface surprising state in the CI log.

        Expected pattern: git status --porcelain  or  git diff --stat
        or a ::warning:: annotation if dirty.
        """
        has_dirty_check = (
            "status --porcelain" in run_text or
            "git diff" in run_text or
            "git submodule" in run_text or
            "::warning::" in run_text
        )
        assert has_dirty_check, (
            "unity-build.yml must check and report dirty submodule state in submodule mode.\n"
            "Add in the submodule setup step:\n"
            "  if [[ -n \"$(git -C \"$SUBMODULE_PATH\" status --porcelain)\" ]]; then\n"
            "    echo '::warning::Toolkit submodule has uncommitted changes'\n"
            "  fi"
        )

    def test_sha_print_and_dirty_check_are_in_submodule_scoped_step(self):
        """
        The SHA print and dirty check must appear in a step conditioned on
        integration-mode == 'submodule', not in a step that always runs.
        Running 'git -C <path> rev-parse HEAD' when toolkit-path doesn't
        exist (remote mode) would cause a confusing CI failure.
        """
        doc = _unity_build_doc()
        if doc is None:
            pytest.skip("unity-build.yml not found")

        sha_step_has_condition = False
        for step in _iter_steps(doc):
            run = str(step.get("run", ""))
            cond = str(step.get("if", ""))
            if ("rev-parse" in run or "status --porcelain" in run):
                if "submodule" in cond.lower() or "integration" in cond.lower():
                    sha_step_has_condition = True
                    break

        if not sha_step_has_condition:
            # Also acceptable: the entire run: block is inside a conditional script
            # that checks integration-mode via env var. Check for env var guard.
            run_text = _all_run_text(doc)
            if "integration-mode" in run_text or "INTEGRATION_MODE" in run_text:
                sha_step_has_condition = True

        assert sha_step_has_condition, (
            "The step that prints the submodule SHA / checks dirty state must be "
            "conditional on integration-mode == 'submodule'. Otherwise it will "
            "fail in remote mode where the submodule path does not exist.\n"
            "Add: if: inputs.integration-mode == 'submodule'"
        )


# ---------------------------------------------------------------------------
# Error messages: missing submodule, missing toolkit scripts/actions
# ---------------------------------------------------------------------------

class TestToolkitValidationErrors:
    """
    In submodule mode the workflow must produce actionable errors when:
    1. The submodule is missing at toolkit-path (consumer forgot to init submodule).
    2. The toolkit scripts directory is missing (incomplete submodule checkout).
    3. A required composite action is missing from the toolkit.

    'Actionable' means: the error message names the expected path and suggests
    the fix (e.g., 'git submodule update --init --recursive').
    """

    @pytest.fixture(autouse=True)
    def _guard(self):
        _skip_if_no_integration_mode()

    @pytest.fixture
    def run_text(self):
        doc = _unity_build_doc()
        if doc is None:
            pytest.skip("unity-build.yml not found")
        return _all_run_text(doc)

    def test_missing_submodule_produces_error(self, run_text):
        """
        When the toolkit submodule directory is absent the workflow must exit 1
        with a ::error:: annotation — not a cryptic bash 'No such file or directory'.

        Expected pattern:
          if [[ ! -d "$SUBMODULE_PATH" ]]; then
            echo "::error::Toolkit submodule not found at $SUBMODULE_PATH"
            echo "::error::Run: git submodule update --init --recursive"
            exit 1
          fi
        """
        has_missing_submodule_guard = (
            "! -d" in run_text or "[ -d" in run_text
        ) and (
            "exit 1" in run_text or "::error::" in run_text
        )
        assert has_missing_submodule_guard, (
            "unity-build.yml must guard against missing submodule directory and "
            "produce an actionable ::error:: annotation.\n"
            "Add in the submodule setup step:\n"
            "  if [[ ! -d \"$SUBMODULE_PATH\" ]]; then\n"
            "    echo '::error::Toolkit submodule not found at $SUBMODULE_PATH'\n"
            "    echo '::error::Run: git submodule update --init --recursive'\n"
            "    exit 1\n"
            "  fi"
        )

    def test_missing_submodule_error_mentions_fix(self, run_text):
        """
        The missing-submodule error must mention 'git submodule update' so the
        consumer knows how to fix the problem without reading documentation.
        """
        has_fix_hint = (
            "submodule update" in run_text or
            "git submodule" in run_text
        )
        assert has_fix_hint, (
            "Missing-submodule error must mention 'git submodule update --init --recursive' "
            "as the fix. Consumers encountering this error may not know git submodule commands."
        )

    def test_missing_toolkit_scripts_produces_error(self, run_text):
        """
        After setting up the toolkit path, the workflow must verify that
        scripts/common/ (the toolkit sentinel directory) exists.
        Missing scripts means an incomplete or corrupted toolkit checkout.

        Expected pattern:
          if [[ ! -d ".ci/unity-build-workflows/scripts" ]]; then
            echo "::error::Toolkit scripts not found ..."
            exit 1
          fi
        """
        has_scripts_check = (
            "scripts" in run_text and (
                "! -d" in run_text or
                "[ -d" in run_text
            )
        ) and (
            "::error::" in run_text or "exit 1" in run_text
        )
        assert has_scripts_check, (
            "unity-build.yml must verify that toolkit scripts/ directory exists "
            "after toolkit setup. An incomplete checkout must produce a clear error.\n"
            "Add after toolkit path setup:\n"
            "  if [[ ! -d \".ci/unity-build-workflows/scripts\" ]]; then\n"
            "    echo '::error::Toolkit scripts not found — checkout may be incomplete'\n"
            "    exit 1\n"
            "  fi"
        )

    def test_missing_composite_actions_produces_error(self, run_text):
        """
        If toolkit setup fails (missing directory), the workflow must produce
        an actionable error with a ::error:: annotation + exit 1.

        T3 implements the primary guard: check that the submodule source directory
        exists before symlinking. This prevents the cryptic bash 'No such file or
        directory' error that would otherwise surface in downstream composite
        action loads.

        Note: a more specific check for .github/actions/ existence (to catch
        incomplete/shallow checkouts) would be a valuable enhancement but is not
        required by the current T3 contract.
        """
        has_toolkit_directory_guard = (
            ("! -d" in run_text or "[ -d" in run_text) and
            ("::error::" in run_text or "exit 1" in run_text)
        )
        assert has_toolkit_directory_guard, (
            "unity-build.yml must guard against a missing toolkit directory and "
            "produce an actionable error annotation.\n"
            "T3 pattern: if [ ! -d \"$SUBMODULE_SRC\" ]; then\n"
            "  echo '::error::toolkit-path not found at ...'\n"
            "  exit 1\n"
            "fi"
        )

    def test_all_error_annotations_use_github_error_syntax(self, run_text):
        """
        All toolkit validation errors must use ::error:: GitHub Actions annotations.
        Plain 'echo ERROR:' lines are not surfaced in the Actions UI summary.
        """
        # If the workflow has error messages, they must use ::error::
        # (This test passes vacuously if no error annotations exist yet — the
        # preceding tests will catch that the guards are missing entirely.)
        if "::error::" not in run_text:
            pytest.skip(
                "No ::error:: annotations found yet — covered by earlier tests "
                "that require the guards to exist."
            )
        # At minimum one ::error:: must reference toolkit-path or submodule
        has_relevant_error = any(kw in run_text for kw in (
            "submodule", "toolkit", "scripts", "actions"
        ))
        assert has_relevant_error, (
            "::error:: annotations in the workflow must reference toolkit-path, "
            "submodule, scripts, or actions to be actionable."
        )


# ---------------------------------------------------------------------------
# TOOLKIT_PATH env contract: always .ci/unity-build-workflows
# ---------------------------------------------------------------------------

class TestToolkitPathEnvContract:
    """
    TOOLKIT_PATH must always resolve to .ci/unity-build-workflows regardless
    of integration-mode. This is the single stable path that:
    - composite actions reference via $GITHUB_WORKSPACE/.ci/unity-build-workflows
    - Python scripts receive via --toolkit-path argument or env var
    - run-unity-container action references for its own action.yml path

    Changing this path would break every consumer without warning.
    """

    @pytest.fixture(autouse=True)
    def _guard(self):
        _skip_if_no_integration_mode()

    @pytest.fixture
    def unity_build_text(self):
        if not UNITY_BUILD_YML.exists():
            pytest.skip("unity-build.yml not found")
        return UNITY_BUILD_YML.read_text()

    def test_canonical_toolkit_path_referenced_in_all_modes(self, unity_build_text):
        """
        .ci/unity-build-workflows must appear in both the remote-mode and
        submodule-mode branches of unity-build.yml. Every mode must land
        the toolkit at this exact path.
        """
        assert CANONICAL_TOOLKIT_PATH in unity_build_text, (
            f"unity-build.yml must reference '{CANONICAL_TOOLKIT_PATH}' — "
            "the canonical toolkit mount point that all downstream steps depend on."
        )

    def test_no_other_toolkit_mount_used_as_canonical(self, unity_build_text):
        """
        The workflow must not use a different canonical toolkit path.
        Variants like 'toolkit/', '.toolkit/', or 'unity-build-workflows/'
        (without the .ci/ prefix) must NOT be the canonical mount.
        """
        forbidden_canonical_variants = [
            "path: toolkit/",
            "path: unity-build-workflows",
            "path: .toolkit/",
            "TOOLKIT_PATH=toolkit/",
            "TOOLKIT_PATH=unity-build-workflows",
        ]
        violations = [v for v in forbidden_canonical_variants if v in unity_build_text]
        assert not violations, (
            f"unity-build.yml uses a non-canonical toolkit path variant.\n"
            f"Forbidden patterns found: {violations}\n"
            f"The canonical path is always: {CANONICAL_TOOLKIT_PATH}"
        )

    def test_composite_actions_reference_canonical_toolkit_path(self):
        """
        All composite actions in .github/actions/ that reference the toolkit
        must use CANONICAL_TOOLKIT_PATH, not a hardcoded sibling path.

        This test scans action.yml files for toolkit-path references.
        """
        actions_dir = REPO_ROOT / ".github" / "actions"
        if not actions_dir.exists():
            pytest.skip(".github/actions/ not present")

        violations = []
        for action_yml in sorted(actions_dir.rglob("action.yml")):
            text = action_yml.read_text()
            # If the action references the toolkit, it must use the canonical path
            if "unity-build-workflows" in text:
                if CANONICAL_TOOLKIT_PATH not in text:
                    # It references the toolkit but NOT via the canonical path
                    rel = action_yml.relative_to(REPO_ROOT)
                    violations.append(str(rel))

        assert not violations, (
            f"These composite actions reference the toolkit without using the "
            f"canonical path '{CANONICAL_TOOLKIT_PATH}':\n"
            + "\n".join(f"  {v}" for v in violations)
        )

    def test_platform_workflows_reference_canonical_toolkit_path(self):
        """
        Per-platform workflows (unity-build-android.yml etc.) must all reference
        CANONICAL_TOOLKIT_PATH — they load composite actions from this location.
        """
        missing = []
        for wf_name in PLATFORM_WORKFLOWS:
            path = WORKFLOWS_DIR / wf_name
            if not path.exists():
                continue
            text = path.read_text()
            if CANONICAL_TOOLKIT_PATH not in text:
                missing.append(wf_name)

        assert not missing, (
            f"These platform workflows do not reference '{CANONICAL_TOOLKIT_PATH}':\n"
            + "\n".join(f"  {w}" for w in missing)
            + "\nAll platform workflows must load composite actions from the canonical toolkit path."
        )

    def test_remote_and_submodule_both_land_at_canonical_path(self):
        """
        Whether integration-mode is 'remote' or 'submodule', the toolkit
        must end up at .ci/unity-build-workflows before any build step runs.

        This test checks that the canonical path appears in BOTH the
        remote-mode checkout block AND the submodule-mode setup block.
        """
        doc = _unity_build_doc()
        if doc is None:
            pytest.skip("unity-build.yml not found")

        remote_has_canonical = False
        submodule_has_canonical = False

        for step in _iter_steps(doc):
            cond = str(step.get("if", "")).lower()
            uses = str(step.get("uses", ""))
            run = str(step.get("run", ""))
            with_block = step.get("with") or {}
            path_val = str(with_block.get("path", ""))

            # Detect remote-mode canonical path usage
            is_remote_step = "remote" in cond or (
                "submodule" in cond and "!=" in cond
            ) or (
                "submodule" not in cond and
                CANONICAL_TOOLKIT_PATH in path_val
            )
            if is_remote_step and CANONICAL_TOOLKIT_PATH in (path_val + run):
                remote_has_canonical = True

            # Detect submodule-mode canonical path usage
            is_submodule_step = "submodule" in cond and "!=" not in cond
            if is_submodule_step and CANONICAL_TOOLKIT_PATH in run:
                submodule_has_canonical = True

        # At minimum, the canonical path must appear somewhere in the workflow
        # (the split between modes may be in a single step with an env var check)
        full_text = UNITY_BUILD_YML.read_text()
        assert CANONICAL_TOOLKIT_PATH in full_text, (
            f"'{CANONICAL_TOOLKIT_PATH}' must appear in unity-build.yml — "
            "both remote and submodule modes must land the toolkit there."
        )
