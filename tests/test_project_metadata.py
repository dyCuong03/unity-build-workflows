"""
test_project_metadata.py
========================
Tests for scripts/common/extract_project_metadata.sh.

Strategy
--------
Each test creates a minimal ProjectSettings.asset in a tmp_path directory
and runs the script with PROJECT_PATH=<tmp_path>, then parses the KEY=value
stdout and asserts individual output fields.

Covered assertions
------------------
M1  product-name parsed from productName
M2  app-version parsed from bundleVersion
M3  bundle-id-android from applicationIdentifier.Android
M4  bundle-id equals bundle-id-android when android id present;
    falls back to Standalone when android absent
M5  scripting-backend=IL2CPP when scriptingBackend.Android=1
M6  scripting-backend=Mono  when scriptingBackend.Android=0
M7  scripting-backend=Mono  when scriptingBackend block absent entirely
M8  android-arch: bitmask 2 → ARM64; 1 → ARMv7; 3 → ARMv7+ARM64
M9  orientation: defaultScreenOrientation mapping (0→Portrait, 2→LandscapeRight, etc.)
M10 define-symbols-count: "A;B;C" → 3; "A" → 1; "" → 0
M11 store-link-android: play.google.com URL from bundle-id-android
M12 store-link-android empty when no bundle-id-android
M13 missing ProjectSettings.asset → all keys emitted with empty value, exit 0
M14 all expected output keys always present in stdout
"""

import os
import subprocess
from pathlib import Path
from typing import Dict

import pytest

REPO_ROOT = Path(__file__).parent.parent
META_SCRIPT = REPO_ROOT / "scripts" / "common" / "extract_project_metadata.sh"

EXPECTED_META_KEYS = {
    "product-name",
    "app-version",
    "bundle-id-android",
    "bundle-id",
    "scripting-backend",
    "android-arch",
    "orientation",
    "define-symbols-count",
    "store-link-android",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_meta(project_path: Path, timeout: int = 10) -> subprocess.CompletedProcess:
    """Run extract_project_metadata.sh with a controlled environment."""
    env: Dict[str, str] = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "PROJECT_PATH": str(project_path),
    }
    return subprocess.run(
        ["bash", str(META_SCRIPT)],
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


def write_asset(tmp_path: Path, content: str) -> Path:
    """Write ProjectSettings.asset and return the project root (tmp_path)."""
    ps_dir = tmp_path / "ProjectSettings"
    ps_dir.mkdir(parents=True, exist_ok=True)
    (ps_dir / "ProjectSettings.asset").write_text(content)
    return tmp_path


def minimal_asset(
    product_name: str = "TestGame",
    bundle_version: str = "1.2.3",
    bundle_android: str = "com.test.game",
    bundle_standalone: str = "com.test.game.standalone",
    scripting_backend_android: str = "1",
    arch: int = 2,
    orientation: int = 2,
    defines_android: str = "A;B;C",
) -> str:
    """Return a minimal ProjectSettings.asset fixture (text-serialized Unity YAML)."""
    # The script uses awk/grep on raw text — whitespace structure matters.
    # Mirror the indentation Unity itself uses.
    return f"""\
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!129 &1
PlayerSettings:
  serializedVersion: 6
  productName: {product_name}
  bundleVersion: {bundle_version}
  defaultScreenOrientation: {orientation}
  AndroidTargetArchitectures: {arch}
  applicationIdentifier:
    Android: {bundle_android}
    Standalone: {bundle_standalone}
  scriptingBackend:
    Android: {scripting_backend_android}
  scriptingDefineSymbols:
    Android: {defines_android}
  buildNumber:
    Standalone: 0
    iPhone: 0
    tvOS: 0
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _require_script():
    if not META_SCRIPT.exists():
        pytest.skip(f"Metadata script not found: {META_SCRIPT}")


# ---------------------------------------------------------------------------
# M1-M4: Basic scalars + bundle id
# ---------------------------------------------------------------------------

class TestBasicScalars:
    def test_m1_product_name(self, tmp_path):
        """M1: product-name extracted from productName field."""
        proj = write_asset(tmp_path, minimal_asset(product_name="MyAwesomeGame"))
        out = parse_outputs(run_meta(proj).stdout)
        assert out["product-name"] == "MyAwesomeGame"

    def test_m2_app_version(self, tmp_path):
        """M2: app-version extracted from bundleVersion field."""
        proj = write_asset(tmp_path, minimal_asset(bundle_version="2.5.1"))
        out = parse_outputs(run_meta(proj).stdout)
        assert out["app-version"] == "2.5.1"

    def test_m3_bundle_id_android(self, tmp_path):
        """M3: bundle-id-android from applicationIdentifier.Android block."""
        proj = write_asset(tmp_path, minimal_asset(bundle_android="com.example.mygame"))
        out = parse_outputs(run_meta(proj).stdout)
        assert out["bundle-id-android"] == "com.example.mygame"

    def test_m4_bundle_id_equals_android_when_present(self, tmp_path):
        """M4: bundle-id is same as bundle-id-android when android id present."""
        proj = write_asset(tmp_path, minimal_asset(bundle_android="com.example.mygame"))
        out = parse_outputs(run_meta(proj).stdout)
        assert out["bundle-id"] == "com.example.mygame"
        assert out["bundle-id"] == out["bundle-id-android"]

    def test_m4_bundle_id_falls_back_to_standalone(self, tmp_path):
        """M4: bundle-id falls back to Standalone when Android id absent.

        scriptingDefineSymbols is placed BEFORE applicationIdentifier so the
        awk scanning for Android: after the applicationIdentifier: block doesn't
        accidentally pick up scriptingDefineSymbols.Android.
        """
        asset = """\
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!129 &1
PlayerSettings:
  productName: FallbackGame
  bundleVersion: 1.0.0
  defaultScreenOrientation: 0
  AndroidTargetArchitectures: 2
  scriptingDefineSymbols:
    Android: ""
  applicationIdentifier:
    Standalone: com.fallback.standalone
  buildNumber:
    Standalone: 0
"""
        proj = write_asset(tmp_path, asset)
        out = parse_outputs(run_meta(proj).stdout)
        assert out["bundle-id-android"] == ""
        assert out["bundle-id"] == "com.fallback.standalone"


# ---------------------------------------------------------------------------
# M5-M7: scripting-backend
# ---------------------------------------------------------------------------

class TestScriptingBackend:
    def test_m5_il2cpp_when_android_backend_1(self, tmp_path):
        """M5: scriptingBackend.Android=1 → scripting-backend=IL2CPP."""
        proj = write_asset(tmp_path, minimal_asset(scripting_backend_android="1"))
        out = parse_outputs(run_meta(proj).stdout)
        assert out["scripting-backend"] == "IL2CPP"

    def test_m6_mono_when_android_backend_0(self, tmp_path):
        """M6: scriptingBackend.Android=0 → scripting-backend=Mono."""
        proj = write_asset(tmp_path, minimal_asset(scripting_backend_android="0"))
        out = parse_outputs(run_meta(proj).stdout)
        assert out["scripting-backend"] == "Mono"

    def test_m7_mono_when_scripting_backend_absent(self, tmp_path):
        """M7: No scriptingBackend block at all → scripting-backend=Mono (default)."""
        asset = """\
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!129 &1
PlayerSettings:
  productName: NoBackend
  bundleVersion: 1.0.0
  defaultScreenOrientation: 0
  AndroidTargetArchitectures: 2
  applicationIdentifier:
    Android: com.test.nobackend
  scriptingDefineSymbols:
    Android: ""
"""
        proj = write_asset(tmp_path, asset)
        out = parse_outputs(run_meta(proj).stdout)
        assert out["scripting-backend"] == "Mono"


# ---------------------------------------------------------------------------
# M8: android-arch bitmask mapping
# ---------------------------------------------------------------------------

class TestAndroidArch:
    @pytest.mark.parametrize("bitmask,expected", [
        (1,  "ARMv7"),
        (2,  "ARM64"),
        (3,  "ARMv7+ARM64"),
        (4,  "x86"),
        (8,  "x86_64"),
    ])
    def test_m8_arch_mapping(self, tmp_path, bitmask, expected):
        """M8: AndroidTargetArchitectures bitmask → human-readable arch string."""
        proj = write_asset(tmp_path, minimal_asset(arch=bitmask))
        out = parse_outputs(run_meta(proj).stdout)
        assert out["android-arch"] == expected, (
            f"M8: bitmask {bitmask} should map to {expected!r}, got {out['android-arch']!r}"
        )


# ---------------------------------------------------------------------------
# M9: orientation mapping
# ---------------------------------------------------------------------------

class TestOrientation:
    @pytest.mark.parametrize("raw,expected", [
        (0, "Portrait"),
        (1, "PortraitUpsideDown"),
        (2, "LandscapeRight"),
        (3, "LandscapeLeft"),
        (4, "AutoRotation"),
    ])
    def test_m9_orientation_mapping(self, tmp_path, raw, expected):
        """M9: defaultScreenOrientation int → human-readable orientation string."""
        proj = write_asset(tmp_path, minimal_asset(orientation=raw))
        out = parse_outputs(run_meta(proj).stdout)
        assert out["orientation"] == expected, (
            f"M9: orientation {raw} should be {expected!r}, got {out['orientation']!r}"
        )


# ---------------------------------------------------------------------------
# M10: define-symbols-count
# ---------------------------------------------------------------------------

class TestDefineSymbolsCount:
    def test_m10_three_symbols(self, tmp_path):
        """M10: 'A;B;C' → define-symbols-count=3."""
        proj = write_asset(tmp_path, minimal_asset(defines_android="A;B;C"))
        out = parse_outputs(run_meta(proj).stdout)
        assert out["define-symbols-count"] == "3"

    def test_m10_one_symbol(self, tmp_path):
        """M10: 'A' → define-symbols-count=1."""
        proj = write_asset(tmp_path, minimal_asset(defines_android="A"))
        out = parse_outputs(run_meta(proj).stdout)
        assert out["define-symbols-count"] == "1"

    def test_m10_empty_defines(self, tmp_path):
        """M10: empty string → define-symbols-count=0."""
        proj = write_asset(tmp_path, minimal_asset(defines_android=""))
        out = parse_outputs(run_meta(proj).stdout)
        assert out["define-symbols-count"] == "0"

    def test_m10_many_symbols(self, tmp_path):
        """M10: 'A;B;C;D;E' → define-symbols-count=5."""
        proj = write_asset(tmp_path, minimal_asset(defines_android="A;B;C;D;E"))
        out = parse_outputs(run_meta(proj).stdout)
        assert out["define-symbols-count"] == "5"

    def test_m10_trailing_semicolon_not_counted(self, tmp_path):
        """M10: trailing semicolons produce empty tokens that are excluded from count."""
        # 'A;B;' has 2 non-empty tokens
        proj = write_asset(tmp_path, minimal_asset(defines_android="A;B;"))
        out = parse_outputs(run_meta(proj).stdout)
        assert out["define-symbols-count"] == "2"


# ---------------------------------------------------------------------------
# M11-M12: store-link-android
# ---------------------------------------------------------------------------

class TestStoreLink:
    def test_m11_store_link_from_bundle_id(self, tmp_path):
        """M11: store-link-android is play.google.com URL built from bundle-id-android."""
        proj = write_asset(tmp_path, minimal_asset(bundle_android="com.example.mygame"))
        out = parse_outputs(run_meta(proj).stdout)
        assert out["store-link-android"] == (
            "https://play.google.com/store/apps/details?id=com.example.mygame"
        )

    def test_m12_store_link_empty_when_no_bundle_id(self, tmp_path):
        """M12: store-link-android is empty when no bundle-id-android.

        scriptingDefineSymbols placed BEFORE applicationIdentifier so the awk
        scanning for Android: after applicationIdentifier doesn't find a stray
        Android: line in scriptingDefineSymbols and mistake it for the bundle id.
        """
        asset = """\
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!129 &1
PlayerSettings:
  productName: NoBundle
  bundleVersion: 1.0.0
  defaultScreenOrientation: 0
  AndroidTargetArchitectures: 2
  scriptingDefineSymbols:
    Android: ""
  applicationIdentifier:
    Standalone: com.nolink.standalone
  buildNumber:
    Standalone: 0
"""
        proj = write_asset(tmp_path, asset)
        out = parse_outputs(run_meta(proj).stdout)
        assert out["store-link-android"] == ""


# ---------------------------------------------------------------------------
# M13: missing ProjectSettings.asset → empty values, exit 0
# ---------------------------------------------------------------------------

class TestMissingProjectSettings:
    def test_m13_exit_zero_when_file_missing(self, tmp_path):
        """M13: No ProjectSettings.asset → exit 0 (best-effort, never fails caller)."""
        # tmp_path has no ProjectSettings dir at all
        r = run_meta(tmp_path)
        assert r.returncode == 0, (
            f"M13: Script should exit 0 when file missing, got {r.returncode}\n"
            f"stderr: {r.stderr}"
        )

    def test_m13_all_keys_emitted_when_file_missing(self, tmp_path):
        """M13: Even when missing, all output keys are emitted (with empty values)."""
        r = run_meta(tmp_path)
        assert r.returncode == 0
        out = parse_outputs(r.stdout)
        missing_keys = EXPECTED_META_KEYS - set(out.keys())
        assert not missing_keys, (
            f"M13: Missing output keys when file absent: {missing_keys}"
        )

    def test_m13_all_values_empty_when_file_missing(self, tmp_path):
        """M13: All emitted values are empty strings when file is absent."""
        r = run_meta(tmp_path)
        out = parse_outputs(r.stdout)
        non_empty = {k: v for k, v in out.items() if v != ""}
        assert not non_empty, (
            f"M13: Expected all-empty values, got non-empty: {non_empty}"
        )


# ---------------------------------------------------------------------------
# M14: all expected keys always present in stdout
# ---------------------------------------------------------------------------

class TestAllKeysPresent:
    def test_m14_all_keys_present_with_full_asset(self, tmp_path):
        """M14: Full asset → all expected output keys present in stdout."""
        proj = write_asset(tmp_path, minimal_asset())
        out = parse_outputs(run_meta(proj).stdout)
        missing = EXPECTED_META_KEYS - set(out.keys())
        assert not missing, f"M14: Missing output keys: {missing}"

    def test_m14_exit_zero_with_full_asset(self, tmp_path):
        """M14: Script exits 0 with valid asset."""
        proj = write_asset(tmp_path, minimal_asset())
        r = run_meta(proj)
        assert r.returncode == 0, f"M14: Exit {r.returncode}\nstderr: {r.stderr}"

    def test_m14_no_diagnostic_in_stdout(self, tmp_path):
        """M14: stdout contains only KEY=value lines (diagnostics go to stderr)."""
        proj = write_asset(tmp_path, minimal_asset())
        r = run_meta(proj)
        for line in r.stdout.splitlines():
            line = line.strip()
            if line:
                assert "=" in line, (
                    f"M14: Non KEY=value line in stdout: {line!r}"
                )
