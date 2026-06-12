"""
Tests for GitHub Actions workflow YAML contract.

Covers:
- Parsing all workflow YAMLs in .github/workflows/
- unity-build.yml has all required inputs with correct types and defaults
- Required secrets are documented (not hard-coded in env blocks)
- No @main references in reusable workflow calls
- if: always() on report/log upload steps

Note: PyYAML parses the bare key `on:` as boolean True, not the string "on".
All trigger access uses the get_triggers() helper to handle both variants.
"""
from pathlib import Path

import pytest
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_workflow(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


def get_triggers(doc: dict) -> dict:
    """
    Return the workflow triggers dict.
    PyYAML parses bare `on:` as True (boolean), not the string "on".
    Try both keys so tests work regardless of how the loader behaves.
    """
    return doc.get("on") or doc.get(True) or {}


def iter_steps(workflow: dict):
    """Yield every step dict across all jobs."""
    for job in (workflow.get("jobs") or {}).values():
        for step in (job.get("steps") or []):
            yield step


def iter_uses(workflow: dict):
    """Yield every 'uses' value (reusable workflow / action calls)."""
    for step in iter_steps(workflow):
        if "uses" in step:
            yield step["uses"]
    for job in (workflow.get("jobs") or {}).values():
        if "uses" in job:
            yield job["uses"]


def load_unity_build_workflow(workflows_dir: Path):
    """Load unity-build.yml, or return None if not yet created."""
    path = workflows_dir / "unity-build.yml"
    if not path.exists():
        return None
    return load_workflow(path)


# ---------------------------------------------------------------------------
# Workflow discovery
# ---------------------------------------------------------------------------

class TestWorkflowDiscovery:

    def test_workflows_dir_exists(self, workflows_dir):
        assert workflows_dir.exists(), f"Expected .github/workflows/ at {workflows_dir}"

    def test_at_least_one_workflow_exists(self, workflows_dir):
        ymls = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
        assert ymls, "No workflow YAML files found in .github/workflows/"

    def test_all_workflow_files_are_valid_yaml(self, workflows_dir):
        for yml_path in sorted(workflows_dir.glob("*.yml")):
            try:
                doc = load_workflow(yml_path)
                assert isinstance(doc, dict), f"{yml_path.name} is not a YAML mapping"
            except yaml.YAMLError as exc:
                pytest.fail(f"YAML parse error in {yml_path.name}: {exc}")

    def test_workflow_files_have_name_field(self, workflows_dir):
        for yml_path in sorted(workflows_dir.glob("*.yml")):
            doc = load_workflow(yml_path)
            assert "name" in doc, f"{yml_path.name} is missing 'name' field"


# ---------------------------------------------------------------------------
# unity-build.yml required inputs
# ---------------------------------------------------------------------------

UNITY_BUILD_REQUIRED_INPUTS = {
    "project-path": {"type": "string"},
    "unity-version": {"type": "string", "required": True},
    "target-platform": {"type": "string", "required": True},
    "build-config-path": {"type": "string"},
    "environment": {"type": "string"},
    "cache-mode": {"type": "string"},
}


class TestUnityBuildWorkflowInputs:

    @pytest.fixture(autouse=True)
    def load_workflow(self, workflows_dir):
        doc = load_unity_build_workflow(workflows_dir)
        if doc is None:
            pytest.skip("unity-build.yml not yet implemented")
        self.doc = doc
        self.triggers = get_triggers(doc)
        self.inputs = self.triggers.get("workflow_call", {}).get("inputs", {}) or {}
        self.secrets = self.triggers.get("workflow_call", {}).get("secrets", {}) or {}

    def test_unity_build_workflow_is_reusable(self):
        assert "workflow_call" in self.triggers, \
            "unity-build.yml must use workflow_call trigger"

    def test_required_inputs_present(self):
        for input_name in UNITY_BUILD_REQUIRED_INPUTS:
            assert input_name in self.inputs, \
                f"Missing required input: '{input_name}'"

    def test_unity_version_is_required(self):
        unity_version = self.inputs.get("unity-version", {})
        assert unity_version.get("required") is True, \
            "unity-version input must be required: true"

    def test_build_target_is_required(self):
        build_target = self.inputs.get("target-platform", {})
        assert build_target.get("required") is True, \
            "target-platform input must be required: true"

    def test_input_types_are_string(self):
        for input_name, expected in UNITY_BUILD_REQUIRED_INPUTS.items():
            if input_name in self.inputs:
                actual_type = self.inputs[input_name].get("type")
                assert actual_type == expected["type"], \
                    f"Input '{input_name}' type should be '{expected['type']}', got '{actual_type}'"

    def test_project_path_has_default(self):
        project_path = self.inputs.get("project-path", {})
        assert "default" in project_path, "project-path should have a default value"

    def test_cache_mode_has_default(self):
        cache_mode = self.inputs.get("cache-mode", {})
        assert "default" in cache_mode, "cache-mode should have a default value"

    def test_all_inputs_have_descriptions(self):
        for input_name, definition in self.inputs.items():
            assert "description" in definition and definition["description"], \
                f"Input '{input_name}' is missing a description"


class TestUnityBuildWorkflowSecrets:

    @pytest.fixture(autouse=True)
    def load_workflow(self, workflows_dir):
        doc = load_unity_build_workflow(workflows_dir)
        if doc is None:
            pytest.skip("unity-build.yml not yet implemented")
        self.doc = doc
        self.triggers = get_triggers(doc)
        self.secrets = self.triggers.get("workflow_call", {}).get("secrets", {}) or {}

    def test_unity_license_secret_documented(self):
        assert "UNITY_LICENSE" in self.secrets, \
            "UNITY_LICENSE must be declared in workflow_call.secrets"

    def test_unity_license_is_required(self):
        unity_license = self.secrets.get("UNITY_LICENSE", {})
        assert unity_license.get("required") is True, \
            "UNITY_LICENSE secret must be required: true"

    def test_no_hardcoded_secrets_in_env_blocks(self):
        """Secrets must come from ${{ secrets.NAME }}, not literal values.
        Checks env: blocks in steps for secret-looking keys with bare literal values.
        """
        for step in iter_steps(self.doc):
            env_block = step.get("env") or {}
            for key, value in env_block.items():
                if not isinstance(value, str):
                    continue
                is_secret_key = any(
                    kw in key.upper()
                    for kw in ("LICENSE", "PASSWORD", "SECRET", "TOKEN",
                               "KEYSTORE", "CERTIFICATE", "KEY_PASS")
                )
                if is_secret_key:
                    assert value.startswith("${{"), (
                        f"Step '{step.get('name')}' env var '{key}' looks like "
                        f"a secret but is not a ${{{{ secrets.* }}}} expression: {value!r}"
                    )


# ---------------------------------------------------------------------------
# No @main references
# ---------------------------------------------------------------------------

class TestNoMainReferences:

    def test_no_at_main_in_unity_test(self, workflows_dir):
        path = workflows_dir / "unity-test.yml"
        if not path.exists():
            pytest.skip("unity-test.yml not present")
        doc = load_workflow(path)
        for ref in iter_uses(doc):
            assert "@main" not in ref, \
                f"@main reference found in unity-test.yml: {ref}"

    def test_no_at_main_in_unity_validate(self, workflows_dir):
        path = workflows_dir / "unity-validate.yml"
        if not path.exists():
            pytest.skip("unity-validate.yml not present")
        doc = load_workflow(path)
        for ref in iter_uses(doc):
            assert "@main" not in ref, \
                f"@main reference found in unity-validate.yml: {ref}"

    def test_no_at_main_in_unity_build(self, workflows_dir):
        doc = load_unity_build_workflow(workflows_dir)
        if doc is None:
            pytest.skip("unity-build.yml not yet implemented")
        for ref in iter_uses(doc):
            assert "@main" not in ref, \
                f"@main reference found in unity-build.yml: {ref}"

    def test_all_workflows_have_no_at_main(self, workflows_dir):
        for yml_path in sorted(workflows_dir.glob("*.yml")):
            doc = load_workflow(yml_path)
            for ref in iter_uses(doc):
                assert "@main" not in ref, \
                    f"@main reference found in {yml_path.name}: {ref}"


# ---------------------------------------------------------------------------
# if: always() on upload/report steps
# ---------------------------------------------------------------------------

class TestAlwaysConditionOnUploadSteps:
    """
    Upload and report steps must run even when earlier steps fail.
    This can be satisfied either at step level (if: always()) or at
    job level (if: always() on the containing job).
    """

    UPLOAD_STEP_KEYWORDS = (
        "upload-artifact", "upload_artifact", "upload-build-report",
        "test-reporter", "dorny/test-reporter",
    )

    def _is_upload_step(self, step: dict) -> bool:
        uses = step.get("uses", "") or ""
        name = (step.get("name", "") or "").lower()
        return (
            any(kw in uses for kw in self.UPLOAD_STEP_KEYWORDS)
            or "upload" in name
            or "report" in name
        )

    def _job_has_always(self, job_def: dict) -> bool:
        return "always()" in str(job_def.get("if", ""))

    def _check_workflow_upload_steps(self, doc: dict, workflow_name: str):
        """Assert every upload/report step is covered by always() at step or job level."""
        for job_name, job_def in (doc.get("jobs") or {}).items():
            job_always = self._job_has_always(job_def)
            for step in (job_def.get("steps") or []):
                if self._is_upload_step(step):
                    step_always = "always()" in str(step.get("if", ""))
                    assert job_always or step_always, (
                        f"{workflow_name}: upload/report step "
                        f"'{step.get('name', step.get('uses'))}' in job '{job_name}' "
                        f"is not protected by if: always() at step or job level"
                    )

    def test_upload_steps_in_test_workflow_have_always(self, workflows_dir):
        path = workflows_dir / "unity-test.yml"
        if not path.exists():
            pytest.skip("unity-test.yml not present")
        self._check_workflow_upload_steps(load_workflow(path), "unity-test.yml")

    def test_upload_steps_in_validate_workflow_have_always(self, workflows_dir):
        path = workflows_dir / "unity-validate.yml"
        if not path.exists():
            pytest.skip("unity-validate.yml not present")
        self._check_workflow_upload_steps(load_workflow(path), "unity-validate.yml")

    def test_upload_steps_in_build_workflow_have_always(self, workflows_dir):
        doc = load_unity_build_workflow(workflows_dir)
        if doc is None:
            pytest.skip("unity-build.yml not yet implemented")
        self._check_workflow_upload_steps(doc, "unity-build.yml")


# ---------------------------------------------------------------------------
# Existing workflow specific checks
# ---------------------------------------------------------------------------

class TestExistingWorkflowContracts:

    def test_unity_test_has_workflow_call_trigger(self, workflows_dir):
        path = workflows_dir / "unity-test.yml"
        if not path.exists():
            pytest.skip("unity-test.yml not present")
        doc = load_workflow(path)
        triggers = get_triggers(doc)
        assert "workflow_call" in triggers

    def test_unity_test_unity_version_input_required(self, workflows_dir):
        path = workflows_dir / "unity-test.yml"
        if not path.exists():
            pytest.skip("unity-test.yml not present")
        doc = load_workflow(path)
        triggers = get_triggers(doc)
        inputs = triggers.get("workflow_call", {}).get("inputs", {})
        assert "unity-version" in inputs
        assert inputs["unity-version"].get("required") is True

    def test_unity_test_has_unity_license_secret(self, workflows_dir):
        path = workflows_dir / "unity-test.yml"
        if not path.exists():
            pytest.skip("unity-test.yml not present")
        doc = load_workflow(path)
        triggers = get_triggers(doc)
        secrets = triggers.get("workflow_call", {}).get("secrets", {})
        assert "UNITY_LICENSE" in secrets

    def test_unity_validate_has_workflow_call_trigger(self, workflows_dir):
        path = workflows_dir / "unity-validate.yml"
        if not path.exists():
            pytest.skip("unity-validate.yml not present")
        doc = load_workflow(path)
        triggers = get_triggers(doc)
        assert "workflow_call" in triggers

    def test_unity_validate_target_platform_required(self, workflows_dir):
        path = workflows_dir / "unity-validate.yml"
        if not path.exists():
            pytest.skip("unity-validate.yml not present")
        doc = load_workflow(path)
        triggers = get_triggers(doc)
        inputs = triggers.get("workflow_call", {}).get("inputs", {})
        assert "target-platform" in inputs
        assert inputs["target-platform"].get("required") is True

    def test_unity_test_outputs_tests_passed(self, workflows_dir):
        path = workflows_dir / "unity-test.yml"
        if not path.exists():
            pytest.skip("unity-test.yml not present")
        doc = load_workflow(path)
        triggers = get_triggers(doc)
        outputs = triggers.get("workflow_call", {}).get("outputs", {})
        assert "tests-passed" in outputs, \
            "unity-test.yml must expose 'tests-passed' output"
