"""
Shared pytest fixtures for unity-build-workflows test suite.
"""
import json
import os
import sys
from pathlib import Path

import pytest

# Repository root (one level up from tests/)
REPO_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures"
SCHEMA_PATH = REPO_ROOT / "schemas" / "unity-build-config.schema.json"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
SCRIPTS_COMMON = REPO_ROOT / "scripts" / "common"

# Make scripts importable
sys.path.insert(0, str(REPO_ROOT / "scripts" / "common"))


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def schema():
    """Load the Unity build config JSON schema once per session."""
    assert SCHEMA_PATH.exists(), f"Schema not found: {SCHEMA_PATH}"
    with SCHEMA_PATH.open() as f:
        return json.load(f)


@pytest.fixture(scope="session")
def schema_validator(schema):
    """Return a jsonschema Draft7Validator bound to the schema."""
    import jsonschema
    try:
        # jsonschema >= 4.18: use referencing library
        from jsonschema import Draft7Validator
        from referencing import Registry, Resource
        resource = Resource.from_contents(schema)
        registry = Registry().with_resource(SCHEMA_PATH.as_uri(), resource)
        return Draft7Validator(schema, registry=registry)
    except (ImportError, TypeError):
        # Fallback for older jsonschema
        resolver = jsonschema.RefResolver(
            base_uri=SCHEMA_PATH.as_uri(),
            referrer=schema,
        )
        return jsonschema.Draft7Validator(schema, resolver=resolver)


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------

def _load_fixture(name: str) -> dict:
    path = FIXTURES_DIR / name
    assert path.exists(), f"Fixture not found: {path}"
    with path.open() as f:
        return json.load(f)


@pytest.fixture(scope="session")
def valid_base_config():
    return _load_fixture("valid_base_config.json")


@pytest.fixture(scope="session")
def valid_production_config():
    return _load_fixture("valid_production_config.json")


@pytest.fixture(scope="session")
def invalid_production_dev_build():
    return _load_fixture("invalid_production_dev_build.json")


@pytest.fixture(scope="session")
def invalid_empty_scenes():
    return _load_fixture("invalid_empty_scenes.json")


@pytest.fixture(scope="session")
def invalid_bundle_id():
    return _load_fixture("invalid_bundle_id.json")


@pytest.fixture(scope="session")
def minimal_config():
    return _load_fixture("minimal_config.json")


@pytest.fixture(scope="session")
def build_metadata_sample():
    return _load_fixture("build_metadata_sample.json")


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def schema_path():
    return SCHEMA_PATH


@pytest.fixture(scope="session")
def workflows_dir():
    return WORKFLOWS_DIR


@pytest.fixture(scope="session")
def repo_root():
    return REPO_ROOT
