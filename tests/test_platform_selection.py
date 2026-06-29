"""
test_platform_selection.py
==========================
Validates the `if:` selection logic in the consumer Unity build workflow
(.github/workflows/unity-build.yml) without running GitHub Actions.

Strategy
--------
1. Parse the consumer YAML to extract each job's `if:` expression.
2. Evaluate those expressions with mock inputs/needs via a tiny GHA-subset
   evaluator that handles the exact operators used in the workflow.
3. Assert the rules from EXPLICIT_PLATFORM_FLOW_SPEC.md §6 + §3.3.

Covered rules
-------------
R1  platform=All          → all 5 build-<platform> if: True
R2  platform=Android      → only build-android True; others False
R3  platform=WebGL        → only build-webgl True
R4  platform=Linux64      → only build-linux64 True
R5  platform=LinuxServer  → only build-linuxserver True
R6  platform=iOS          → only build-ios True
R7  run-tests=false       → unity-tests if: False (skipped)
R8  run-tests=true        → unity-tests if: True (runs)
R9  build-addressables=false → build-addressables if: False;
                               platform builds still True (accept 'skipped')
R10 UNITY_LICENSE declared optional (required: false) in all reusable workflows
R11 No UNITY_SERIAL anywhere in consumer or reusable-build-platform.yml
R12 final-report if: always() evaluates True regardless of context
R13 validate-project failure → all platform build if: False
"""

import re
import textwrap
from pathlib import Path
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent          # …/unity-build-workflows/
CONSUMER_WF = REPO_ROOT.parent / ".github" / "workflows" / "unity-build.yml"
REUSABLE_BUILD = REPO_ROOT / ".github" / "workflows" / "reusable-build-platform.yml"
REUSABLE_TESTS = REPO_ROOT / ".github" / "workflows" / "reusable-unity-tests.yml"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def consumer_workflow():
    if not CONSUMER_WF.exists():
        pytest.skip(
            f"Consumer workflow not found — expected at {CONSUMER_WF}\n"
            "Run this test from a checkout that includes both the toolkit repo "
            "(unity-build-workflows/) and the consumer repo (.github/workflows/unity-build.yml)."
        )
    return yaml.safe_load(CONSUMER_WF.read_text())


@pytest.fixture(scope="module")
def job_ifs(consumer_workflow):
    """Dict mapping job_id → raw if-expression string (or None)."""
    jobs = consumer_workflow.get("jobs", {})
    return {job_id: job.get("if") for job_id, job in jobs.items()}


@pytest.fixture(scope="module")
def reusable_build_wf():
    assert REUSABLE_BUILD.exists(), f"Missing: {REUSABLE_BUILD}"
    return yaml.safe_load(REUSABLE_BUILD.read_text())


@pytest.fixture(scope="module")
def reusable_tests_wf():
    assert REUSABLE_TESTS.exists(), f"Missing: {REUSABLE_TESTS}"
    return yaml.safe_load(REUSABLE_TESTS.read_text())


# ---------------------------------------------------------------------------
# GHA expression evaluator
# ---------------------------------------------------------------------------

class NeedsProxy(dict):
    """Returns {'result': 'skipped'} for jobs not explicitly in the dict."""
    def __missing__(self, key):
        return {"result": "skipped"}


def eval_gha_expr(expr: Any, context: dict) -> bool:
    """
    Evaluate the GitHub Actions expression subset used in this workflow's if: fields.

    Supported:
      - inputs.<name>                   (hyphenated names OK)
      - needs.<job>.result              (hyphenated job names OK)
      - 'string' / "string" literals
      - true / false
      - always()                        → True
      - ==, !=
      - &&, ||
      - (...)

    context = {
        'inputs': {'platform': 'All', 'run-tests': False, ...},
        'needs':  {'validate-project': {'result': 'success'}, ...}
    }
    """
    if expr is None:
        # No if: condition → job always runs
        return True
    if isinstance(expr, bool):
        return expr

    s = str(expr)
    # Collapse folded-YAML newlines / extra whitespace
    s = " ".join(s.split())

    # GHA status-check functions:
    #   always()    → True  (always runs)
    #   cancelled() → False (assume non-cancelled context in tests)
    #   !cancelled() handled after operator rewrite below
    s = re.sub(r"\balways\(\)", "__TRUE__", s)
    s = re.sub(r"\bcancelled\(\)", "__FALSE__", s)

    # true / false literals (must come before the __PLACEHOLDER__ restore)
    s = re.sub(r"\btrue\b", "True", s, flags=re.IGNORECASE)
    s = re.sub(r"\bfalse\b", "False", s, flags=re.IGNORECASE)

    # Restore placeholders (after literal replacement so they're not matched above)
    s = s.replace("__TRUE__", "True").replace("__FALSE__", "False")

    # && → and,  || → or
    s = s.replace("&&", " and ").replace("||", " or ")

    # Logical NOT: !expr → not expr
    # Replace '!' that is NOT part of '!=' with 'not '
    s = re.sub(r"!(?!=)", "not ", s)

    # inputs.<name> → _inputs['<name>']  (names may contain hyphens)
    s = re.sub(
        r"\binputs\.([A-Za-z0-9_-]+)",
        lambda m: f"_inputs['{m.group(1)}']",
        s,
    )

    # needs.<job>.result → _needs['<job>']['result']
    s = re.sub(
        r"\bneeds\.([A-Za-z0-9_-]+)\.result\b",
        lambda m: f"_needs['{m.group(1)}']['result']",
        s,
    )

    _inputs = context.get("inputs", {})
    _needs = NeedsProxy(context.get("needs", {}))

    try:
        result = eval(  # noqa: S307  (controlled expression from own YAML)
            s,
            {"__builtins__": {}, "True": True, "False": False},
            {"_inputs": _inputs, "_needs": _needs},
        )
        return bool(result)
    except Exception as exc:
        raise ValueError(
            f"GHA evaluator failed on expression:\n  original: {str(expr)!r}\n  rewritten: {s!r}"
        ) from exc


# ---------------------------------------------------------------------------
# Helper to build mock contexts
# ---------------------------------------------------------------------------

PLATFORM_BUILD_JOBS = [
    "build-android",
    "build-webgl",
    "build-linux64",
    "build-linuxserver",
    "build-ios",
]

# build-ios only triggers on explicit 'iOS' dispatch, not on 'All'.
# The consumer workflow intentionally omits iOS from the All path until a
# self-hosted macOS runner is provisioned (spec §5 / §3.3 iOS note).
PLATFORM_BUILD_JOBS_FOR_ALL = [
    "build-android",
    "build-webgl",
    "build-linux64",
    "build-linuxserver",
]

# Baseline needs when validate-project succeeded + build-addressables skipped
def _base_needs(validate="success", addressables="skipped"):
    return {
        "resolve-config":    {"result": "success"},
        "validate-project":  {"result": validate},
        "build-addressables": {"result": addressables},
    }


def _ctx(platform="All", run_tests=False, build_addressables_input=False,
         validate="success", addressables_result="skipped"):
    return {
        "inputs": {
            "platform": platform,
            "run-tests": run_tests,
            "build-addressables": build_addressables_input,
        },
        "needs": _base_needs(validate=validate, addressables=addressables_result),
    }


# ---------------------------------------------------------------------------
# R1 – platform=All → all 5 build jobs True
# ---------------------------------------------------------------------------

def test_r1_platform_all_enables_core_builds(job_ifs):
    """R1: platform=All → Android/WebGL/Linux64/LinuxServer True; iOS False (omitted from All).

    iOS is intentionally excluded from the All path until a self-hosted macOS runner
    is provisioned (consumer workflow §3.3 iOS note).
    """
    ctx = _ctx(platform="All", addressables_result="skipped")
    for job in PLATFORM_BUILD_JOBS_FOR_ALL:
        assert job in job_ifs, f"Job {job!r} not found in consumer workflow"
        result = eval_gha_expr(job_ifs[job], ctx)
        assert result, (
            f"R1: expected {job} if: True with platform=All, got False\n"
            f"  expression: {job_ifs[job]!r}"
        )
    # build-ios must be False for platform=All (explicit iOS required)
    assert not eval_gha_expr(job_ifs["build-ios"], ctx), (
        "R1: build-ios should be False when platform=All (iOS requires explicit dispatch)"
    )


def test_r1_platform_all_with_addressables_success(job_ifs):
    """R1 variant: build-addressables result=success also enables core platform builds."""
    ctx = _ctx(platform="All", addressables_result="success")
    for job in PLATFORM_BUILD_JOBS_FOR_ALL:
        assert eval_gha_expr(job_ifs[job], ctx), (
            f"R1: {job} should be True when addressables=success"
        )


# ---------------------------------------------------------------------------
# R2-R6 – Single-platform dispatch
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("selected_platform,expected_true_job", [
    ("Android",     "build-android"),
    ("WebGL",       "build-webgl"),
    ("Linux64",     "build-linux64"),
    ("LinuxServer", "build-linuxserver"),
    ("iOS",         "build-ios"),
])
def test_r2_r6_single_platform(job_ifs, selected_platform, expected_true_job):
    """R2-R6: dispatch with a single platform → only that build job is True."""
    ctx = _ctx(platform=selected_platform)
    for job in PLATFORM_BUILD_JOBS:
        result = eval_gha_expr(job_ifs[job], ctx)
        if job == expected_true_job:
            assert result, (
                f"R{PLATFORM_BUILD_JOBS.index(job)+2}: expected {job} True "
                f"when platform={selected_platform}, got False"
            )
        else:
            assert not result, (
                f"R{PLATFORM_BUILD_JOBS.index(job)+2}: expected {job} False "
                f"when platform={selected_platform}, got True"
            )


# ---------------------------------------------------------------------------
# R7/R8 – run-tests gate
# ---------------------------------------------------------------------------

def test_r7_run_tests_false_skips_unity_tests(job_ifs):
    """R7: run-tests=false → unity-tests if: evaluates False (job skipped)."""
    assert "unity-tests" in job_ifs, "unity-tests job not found in consumer workflow"
    ctx = _ctx(run_tests=False, validate="success")
    assert not eval_gha_expr(job_ifs["unity-tests"], ctx), (
        "R7: unity-tests if: should be False when run-tests=false"
    )


def test_r8_run_tests_true_enables_unity_tests(job_ifs):
    """R8: run-tests=true + validate-project success → unity-tests if: True."""
    ctx = _ctx(run_tests=True, validate="success")
    assert eval_gha_expr(job_ifs["unity-tests"], ctx), (
        "R8: unity-tests if: should be True when run-tests=true and validate succeeded"
    )


def test_r8_run_tests_true_but_validate_failed_skips(job_ifs):
    """R8 edge: run-tests=true but validate-project failed → unity-tests still False."""
    ctx = _ctx(run_tests=True, validate="failure")
    assert not eval_gha_expr(job_ifs["unity-tests"], ctx), (
        "unity-tests should not run when validate-project failed"
    )


# ---------------------------------------------------------------------------
# R9 – build-addressables=false gate
# ---------------------------------------------------------------------------

def test_r9_build_addressables_false_skips_addressables_job(job_ifs):
    """R9a: build-addressables=false → build-addressables job if: False."""
    assert "build-addressables" in job_ifs, "build-addressables job not found"
    ctx = _ctx(build_addressables_input=False, validate="success")
    assert not eval_gha_expr(job_ifs["build-addressables"], ctx), (
        "R9: build-addressables job if: should be False when input build-addressables=false"
    )


def test_r9_build_addressables_false_platform_builds_still_run(job_ifs):
    """R9b: build-addressables skipped → core platform builds still True (accept 'skipped')."""
    # When build-addressables=false, the job is skipped → result='skipped'
    ctx = _ctx(platform="All", build_addressables_input=False,
               addressables_result="skipped")
    for job in PLATFORM_BUILD_JOBS_FOR_ALL:
        assert eval_gha_expr(job_ifs[job], ctx), (
            f"R9: {job} should run when build-addressables is skipped"
        )


def test_r9_build_addressables_true_enables_job(job_ifs):
    """R9c: build-addressables=true + validate success → build-addressables if: True."""
    ctx = _ctx(build_addressables_input=True, validate="success")
    assert eval_gha_expr(job_ifs["build-addressables"], ctx), (
        "build-addressables job should run when input=true and validate succeeded"
    )


def test_r9_build_addressables_failure_blocks_platform_builds(job_ifs):
    """R9d: build-addressables job failed → core platform builds False."""
    ctx = _ctx(platform="All", addressables_result="failure")
    for job in PLATFORM_BUILD_JOBS_FOR_ALL:
        assert not eval_gha_expr(job_ifs[job], ctx), (
            f"R9: {job} should be blocked when build-addressables failed"
        )


# ---------------------------------------------------------------------------
# R10 – UNITY_LICENSE must be optional in reusable workflow declarations
# ---------------------------------------------------------------------------

def _get_workflow_call_secrets(wf: dict) -> dict:
    """
    Extract on.workflow_call.secrets from a parsed YAML workflow dict.

    PyYAML parses the 'on:' key as the boolean True (YAML keyword), so we
    must probe both True and the string 'on'.
    """
    on_block = wf.get(True, wf.get("on", {})) or {}
    return on_block.get("workflow_call", {}).get("secrets", {})


def test_r10_unity_license_optional_in_reusable_build(reusable_build_wf):
    """R10: reusable-build-platform.yml declares UNITY_LICENSE with required: false."""
    secrets = _get_workflow_call_secrets(reusable_build_wf)
    assert "UNITY_LICENSE" in secrets, (
        "R10: UNITY_LICENSE not declared in reusable-build-platform.yml secrets"
    )
    assert secrets["UNITY_LICENSE"].get("required") is False, (
        "R10: UNITY_LICENSE must be 'required: false' in reusable-build-platform.yml"
    )


def test_r10_unity_license_optional_in_reusable_tests(reusable_tests_wf):
    """R10: reusable-unity-tests.yml declares UNITY_LICENSE with required: false."""
    secrets = _get_workflow_call_secrets(reusable_tests_wf)
    assert "UNITY_LICENSE" in secrets, (
        "R10: UNITY_LICENSE not declared in reusable-unity-tests.yml secrets"
    )
    assert secrets["UNITY_LICENSE"].get("required") is False, (
        "R10: UNITY_LICENSE must be 'required: false' in reusable-unity-tests.yml"
    )


def test_r10_no_unity_license_required_true_in_new_reusables():
    """R10: the two NEW reusable workflow files do not mark UNITY_LICENSE required: true.

    Note: legacy workflows (unity-build-gameci.yml, etc.) are intentionally excluded —
    they predate the Personal/free decision and are kept as fallback per the spec.
    """
    new_reusables = [REUSABLE_BUILD, REUSABLE_TESTS]
    violators = []
    for wf_file in new_reusables:
        wf = yaml.safe_load(wf_file.read_text())
        secrets = _get_workflow_call_secrets(wf)
        lic = secrets.get("UNITY_LICENSE", {}) or {}
        if lic.get("required") is True:
            violators.append(wf_file.name)
    assert not violators, (
        f"R10: UNITY_LICENSE marked required:true in new reusable files: {violators}"
    )


# ---------------------------------------------------------------------------
# R11 – No UNITY_SERIAL anywhere
# ---------------------------------------------------------------------------

def test_r11_no_unity_serial_in_consumer_workflow():
    """R11: UNITY_SERIAL must not appear in the consumer workflow."""
    if not CONSUMER_WF.exists():
        pytest.skip("Consumer workflow not found")
    text = CONSUMER_WF.read_text()
    assert "UNITY_SERIAL" not in text, (
        "R11: UNITY_SERIAL found in consumer workflow — must not be used (Personal/free license)"
    )


def test_r11_no_unity_serial_in_reusable_build():
    """R11: UNITY_SERIAL must not appear in reusable-build-platform.yml."""
    text = REUSABLE_BUILD.read_text()
    assert "UNITY_SERIAL" not in text, (
        "R11: UNITY_SERIAL found in reusable-build-platform.yml"
    )


def test_r11_no_unity_serial_in_reusable_tests():
    """R11: UNITY_SERIAL must not appear in reusable-unity-tests.yml."""
    text = REUSABLE_TESTS.read_text()
    assert "UNITY_SERIAL" not in text, (
        "R11: UNITY_SERIAL found in reusable-unity-tests.yml"
    )


# ---------------------------------------------------------------------------
# R12 – final-report always runs
# ---------------------------------------------------------------------------

def test_r12_final_report_if_is_always(job_ifs):
    """R12: final-report if: is always() and evaluates True in any context."""
    assert "final-report" in job_ifs, "final-report job not found in consumer workflow"
    raw = job_ifs["final-report"]
    assert raw is not None, "final-report has no if: condition — should be always()"
    assert "always()" in str(raw), (
        f"R12: final-report if: expected 'always()', got: {raw!r}"
    )
    # Evaluate in a worst-case failed context — must still be True
    worst = {
        "inputs": {"platform": "Android", "run-tests": False},
        "needs": {
            "validate-project":  {"result": "failure"},
            "build-addressables": {"result": "failure"},
            "build-android":     {"result": "failure"},
            "build-webgl":       {"result": "failure"},
            "build-linux64":     {"result": "failure"},
            "build-linuxserver": {"result": "failure"},
            "build-ios":         {"result": "failure"},
            "unity-tests":       {"result": "failure"},
        },
    }
    assert eval_gha_expr(raw, worst), (
        "R12: final-report if: must evaluate True even when all upstreams failed"
    )


# ---------------------------------------------------------------------------
# R13 – validate-project failure blocks all downstream jobs
# ---------------------------------------------------------------------------

def test_r13_validate_failure_blocks_platform_builds(job_ifs):
    """R13: validate-project=failure → all platform build jobs if: False."""
    ctx = _ctx(platform="All", validate="failure")
    for job in PLATFORM_BUILD_JOBS:
        assert not eval_gha_expr(job_ifs[job], ctx), (
            f"R13: {job} should be False when validate-project failed"
        )
    # iOS explicit too
    ctx_ios = _ctx(platform="iOS", validate="failure")
    assert not eval_gha_expr(job_ifs["build-ios"], ctx_ios), (
        "R13: build-ios should be False when validate-project failed"
    )


def test_r13_validate_failure_blocks_unity_tests(job_ifs):
    """R13: validate-project=failure → unity-tests if: False."""
    ctx = _ctx(run_tests=True, validate="failure")
    assert not eval_gha_expr(job_ifs["unity-tests"], ctx), (
        "R13: unity-tests should not run when validate-project failed"
    )


def test_r13_validate_failure_blocks_build_addressables(job_ifs):
    """R13: validate-project=failure → build-addressables if: False."""
    ctx = _ctx(build_addressables_input=True, validate="failure")
    assert not eval_gha_expr(job_ifs["build-addressables"], ctx), (
        "R13: build-addressables should not run when validate-project failed"
    )


# ---------------------------------------------------------------------------
# Structural sanity — all expected jobs exist
# ---------------------------------------------------------------------------

EXPECTED_JOBS = [
    "resolve-config",
    "validate-project",
    "unity-tests",
    "build-addressables",
    "build-android",
    "build-webgl",
    "build-linux64",
    "build-linuxserver",
    "build-ios",
    "final-report",
]


def test_all_expected_jobs_present(consumer_workflow):
    """Sanity: consumer workflow contains all expected job IDs."""
    jobs = set(consumer_workflow.get("jobs", {}).keys())
    missing = set(EXPECTED_JOBS) - jobs
    assert not missing, f"Missing jobs in consumer workflow: {missing}"


def test_job_if_expressions_are_parseable(job_ifs):
    """Smoke: every job if: expression is evaluable by the GHA evaluator."""
    ctx = _ctx(platform="All", run_tests=True, build_addressables_input=True)
    for job_id, expr in job_ifs.items():
        try:
            eval_gha_expr(expr, ctx)
        except Exception as exc:
            pytest.fail(f"Failed to evaluate if: for job {job_id!r}: {exc}")
