"""
Tests for Unity activation strategy resolver.

Covers all documented activation strategy resolution cases:
  1. No secrets → blocked
  2. Valid-looking UNITY_LICENSE only → manual-ulf
  3. Invalid XML-like UNITY_LICENSE + no fallback → blocked
  4. Invalid XML-like UNITY_LICENSE + UNITY_EMAIL + UNITY_PASSWORD → account fallback
  5. UNITY_SERIAL + UNITY_EMAIL + UNITY_PASSWORD → serial
  6. UNITY_EMAIL + UNITY_PASSWORD only → account
  7. Forced strategy manual-license with no UNITY_LICENSE → blocked
  8. Forced strategy account with no credentials → blocked
  9. Preactivated runner detection path → skipped (no Unity in CI)

Security: no secret values appear in logs or output.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
STRATEGY_SCRIPT = REPO_ROOT / "scripts" / "common" / "resolve_activation_strategy.sh"


def run_strategy(env_overrides: dict, timeout: int = 10) -> subprocess.CompletedProcess:
    """Run the strategy resolver with controlled environment."""
    # Start with a clean environment — no inherited secrets
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
    }
    env.update(env_overrides)

    return subprocess.run(
        ["bash", str(STRATEGY_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


@pytest.fixture(autouse=True)
def _check_script_exists():
    """Skip if strategy script doesn't exist yet."""
    if not STRATEGY_SCRIPT.exists():
        pytest.skip(f"Strategy script not found: {STRATEGY_SCRIPT}")


# ── Case 1: No secrets → blocked ────────────────────────────────────────────

class TestNoSecrets:
    def test_returns_blocked(self):
        result = run_strategy({})
        assert result.returncode == 0  # Script itself succeeds
        assert result.stdout.strip() == "blocked"

    def test_logs_all_missing(self):
        result = run_strategy({})
        stderr = result.stderr
        assert "UNITY_LICENSE:  false" in stderr
        assert "UNITY_SERIAL:   false" in stderr
        assert "UNITY_EMAIL:    false" in stderr
        assert "UNITY_PASSWORD: false" in stderr

    def test_no_secrets_leaked(self):
        result = run_strategy({})
        # Ensure no actual secret values appear (just in case)
        assert "password" not in result.stdout.lower() or "missing" in result.stdout.lower()


# ── Case 2: Valid UNITY_LICENSE only → manual-ulf ────────────────────────────

class TestValidLicenseOnly:
    @pytest.fixture
    def valid_ulf_content(self):
        """Minimal valid-looking .ulf content (not real license)."""
        return '<?xml version="1.0" encoding="UTF-8"?><root><License id="terms">license content</License></root>'

    def test_returns_manual_ulf(self, valid_ulf_content):
        result = run_strategy({"UNITY_LICENSE": valid_ulf_content})
        assert result.stdout.strip() == "manual-ulf"

    def test_base64_encoded_ulf(self, valid_ulf_content):
        import base64
        encoded = base64.b64encode(valid_ulf_content.encode()).decode()
        result = run_strategy({"UNITY_LICENSE": encoded})
        assert result.stdout.strip() == "manual-ulf"

    def test_license_reported_present(self, valid_ulf_content):
        result = run_strategy({"UNITY_LICENSE": valid_ulf_content})
        assert "UNITY_LICENSE:  true" in result.stderr
        assert "unity-license-valid-ulf=yes" in result.stderr


# ── Case 3: Invalid XML UNITY_LICENSE + no fallback → blocked ────────────────

class TestInvalidLicenseNoFallback:
    def test_entitlement_xml_rejected(self):
        bad_content = '<root><UnityEntitlementLicense>fake</UnityEntitlementLicense></root>'
        result = run_strategy({"UNITY_LICENSE": bad_content})
        assert result.stdout.strip() == "blocked"
        assert "unity-license-valid-ulf=no" in result.stderr

    def test_generic_xml_rejected(self):
        bad_content = '<?xml version="1.0"?><root><data>random config file</data></root>'
        result = run_strategy({"UNITY_LICENSE": bad_content})
        assert result.stdout.strip() == "blocked"

    def test_empty_license_rejected(self):
        result = run_strategy({"UNITY_LICENSE": ""})
        # Empty string means HAS_LICENSE=false → blocked
        assert result.stdout.strip() == "blocked"


# ── Case 4: Invalid XML UNITY_LICENSE + email/password → account fallback ────

class TestInvalidLicenseWithFallback:
    def test_falls_back_to_account(self):
        bad_content = '<root><UnityEntitlementLicense>fake</UnityEntitlementLicense></root>'
        result = run_strategy({
            "UNITY_LICENSE": bad_content,
            "UNITY_EMAIL": "test@example.com",
            "UNITY_PASSWORD": "secret123",
        })
        assert result.stdout.strip() == "account"

    def test_invalid_ulf_warning_logged(self):
        bad_content = '<root><UnityEntitlementLicense>fake</UnityEntitlementLicense></root>'
        result = run_strategy({
            "UNITY_LICENSE": bad_content,
            "UNITY_EMAIL": "test@example.com",
            "UNITY_PASSWORD": "secret123",
        })
        assert "invalid" in result.stderr.lower() or "skipping manual-ulf" in result.stderr.lower()


# ── Case 5: UNITY_SERIAL + email + password → serial ────────────────────────

class TestSerialActivation:
    def test_returns_serial(self):
        result = run_strategy({
            "UNITY_SERIAL": "XX-XXXX-XXXX-XXXX-XXXX-XXXX",
            "UNITY_EMAIL": "test@example.com",
            "UNITY_PASSWORD": "secret123",
        })
        assert result.stdout.strip() == "serial"

    def test_serial_takes_priority_over_account(self):
        """Serial should be selected even though account is also possible."""
        result = run_strategy({
            "UNITY_SERIAL": "XX-XXXX-XXXX-XXXX-XXXX-XXXX",
            "UNITY_EMAIL": "test@example.com",
            "UNITY_PASSWORD": "secret123",
        })
        assert result.stdout.strip() == "serial"

    def test_serial_without_email_not_selected(self):
        result = run_strategy({
            "UNITY_SERIAL": "XX-XXXX-XXXX-XXXX-XXXX-XXXX",
            "UNITY_PASSWORD": "secret123",
        })
        # Incomplete serial credentials — should not select serial
        assert result.stdout.strip() != "serial"


# ── Case 6: UNITY_EMAIL + UNITY_PASSWORD only → account ─────────────────────

class TestAccountActivation:
    def test_returns_account(self):
        result = run_strategy({
            "UNITY_EMAIL": "test@example.com",
            "UNITY_PASSWORD": "secret123",
        })
        assert result.stdout.strip() == "account"

    def test_email_only_is_blocked(self):
        result = run_strategy({"UNITY_EMAIL": "test@example.com"})
        assert result.stdout.strip() == "blocked"

    def test_password_only_is_blocked(self):
        result = run_strategy({"UNITY_PASSWORD": "secret123"})
        assert result.stdout.strip() == "blocked"


# ── Case 7: Forced manual-license with no UNITY_LICENSE → blocked ────────────

class TestForcedManualNoLicense:
    def test_forced_manual_ulf_blocked(self):
        result = run_strategy({"UNITY_ACTIVATION_STRATEGY": "manual-ulf"})
        assert result.stdout.strip() == "blocked"

    def test_forced_manual_license_blocked(self):
        result = run_strategy({"UNITY_ACTIVATION_STRATEGY": "manual-license"})
        assert result.stdout.strip() == "blocked"

    def test_blocked_reason_mentions_not_set(self):
        result = run_strategy({"UNITY_ACTIVATION_STRATEGY": "manual-ulf"})
        assert "not set" in result.stderr.lower() or "UNITY_LICENSE" in result.stderr


# ── Case 8: Forced account with no credentials → blocked ────────────────────

class TestForcedAccountNoCreds:
    def test_forced_account_blocked(self):
        result = run_strategy({"UNITY_ACTIVATION_STRATEGY": "account"})
        assert result.stdout.strip() == "blocked"

    def test_blocked_reason_mentions_credentials(self):
        result = run_strategy({"UNITY_ACTIVATION_STRATEGY": "account"})
        assert "UNITY_EMAIL" in result.stderr or "UNITY_PASSWORD" in result.stderr


# ── Case 9: Preactivated runner (skipped in CI — no Unity) ──────────────────

class TestPreactivatedDetection:
    def test_forced_preactivated_returns_preactivated(self):
        """Forced preactivated should succeed regardless."""
        result = run_strategy({"UNITY_ACTIVATION_STRATEGY": "preactivated"})
        assert result.stdout.strip() == "preactivated"


# ── Strategy 'none' ─────────────────────────────────────────────────────────

class TestNoneStrategy:
    def test_forced_none(self):
        result = run_strategy({"UNITY_ACTIVATION_STRATEGY": "none"})
        assert result.stdout.strip() == "none"


# ── Security: no secrets in output ──────────────────────────────────────────

class TestSecurityNoLeaks:
    """Ensure actual secret values never appear in stdout or stderr."""

    def test_password_not_in_output(self):
        result = run_strategy({
            "UNITY_EMAIL": "ci-test@example.com",
            "UNITY_PASSWORD": "SUPER_SECRET_PASSWORD_12345",
        })
        assert "SUPER_SECRET_PASSWORD_12345" not in result.stdout
        assert "SUPER_SECRET_PASSWORD_12345" not in result.stderr

    def test_email_not_in_output(self):
        result = run_strategy({
            "UNITY_EMAIL": "ci-test@example.com",
            "UNITY_PASSWORD": "secret",
        })
        assert "ci-test@example.com" not in result.stdout
        assert "ci-test@example.com" not in result.stderr

    def test_serial_not_in_output(self):
        result = run_strategy({
            "UNITY_SERIAL": "AB-1234-5678-9012-3456-7890",
            "UNITY_EMAIL": "test@test.com",
            "UNITY_PASSWORD": "pass",
        })
        assert "AB-1234-5678-9012-3456-7890" not in result.stdout
        assert "AB-1234-5678-9012-3456-7890" not in result.stderr

    def test_license_content_not_in_output(self):
        license_content = '<?xml version="1.0"?><root><License id="terms">UNIQUE_LICENSE_MARKER_CONTENT</License></root>'
        result = run_strategy({"UNITY_LICENSE": license_content})
        assert "UNIQUE_LICENSE_MARKER_CONTENT" not in result.stdout
        assert "UNIQUE_LICENSE_MARKER_CONTENT" not in result.stderr


# ── Priority order validation ───────────────────────────────────────────────

class TestPriorityOrder:
    """Verify correct priority: personal-combined > manual-ulf > serial > account."""

    def test_combined_beats_everything(self):
        # Valid .ulf + account credentials → personal-combined (GameCI-style),
        # even when a serial is also present.
        ulf = '<?xml version="1.0" encoding="UTF-8"?><root><License id="x">valid</License></root>'
        result = run_strategy({
            "UNITY_LICENSE": ulf,
            "UNITY_SERIAL": "XX-XXXX-XXXX-XXXX-XXXX-XXXX",
            "UNITY_EMAIL": "test@example.com",
            "UNITY_PASSWORD": "secret",
        })
        assert result.stdout.strip() == "personal-combined"

    def test_ulf_only_is_manual_ulf(self):
        # A valid .ulf WITHOUT account credentials stays manual-ulf.
        ulf = '<?xml version="1.0" encoding="UTF-8"?><root><License id="x">valid</License></root>'
        result = run_strategy({"UNITY_LICENSE": ulf})
        assert result.stdout.strip() == "manual-ulf"

    def test_serial_beats_account(self):
        result = run_strategy({
            "UNITY_SERIAL": "XX-XXXX-XXXX-XXXX-XXXX-XXXX",
            "UNITY_EMAIL": "test@example.com",
            "UNITY_PASSWORD": "secret",
        })
        assert result.stdout.strip() == "serial"


# ── Combined Personal (GameCI-style) ────────────────────────────────────────

class TestPersonalCombined:
    """UNITY_LICENSE (.ulf) + UNITY_EMAIL + UNITY_PASSWORD → personal-combined.

    Mirrors game-ci/unity-builder: the .ulf seeds the entitlement and the
    online login binds a fresh access token. Verified to be the only reliable
    Unity Personal/free activation path in ephemeral Docker.
    """

    VALID_ULF = '<?xml version="1.0" encoding="UTF-8"?><root><License id="x">valid</License></root>'

    def test_auto_selects_combined(self):
        result = run_strategy({
            "UNITY_LICENSE": self.VALID_ULF,
            "UNITY_EMAIL": "test@example.com",
            "UNITY_PASSWORD": "secret123",
        })
        assert result.stdout.strip() == "personal-combined"

    def test_forced_combined(self):
        result = run_strategy({
            "UNITY_ACTIVATION_STRATEGY": "personal-combined",
            "UNITY_LICENSE": self.VALID_ULF,
            "UNITY_EMAIL": "test@example.com",
            "UNITY_PASSWORD": "secret123",
        })
        assert result.stdout.strip() == "personal-combined"

    def test_forced_combined_missing_creds_blocked(self):
        result = run_strategy({
            "UNITY_ACTIVATION_STRATEGY": "personal-combined",
            "UNITY_LICENSE": self.VALID_ULF,
        })
        assert result.stdout.strip() == "blocked"

    def test_invalid_ulf_with_creds_is_account_not_combined(self):
        # An invalid .ulf must NOT be promoted to personal-combined; it falls
        # back to account activation.
        bad = '<root><UnityEntitlementLicense>fake</UnityEntitlementLicense></root>'
        result = run_strategy({
            "UNITY_LICENSE": bad,
            "UNITY_EMAIL": "test@example.com",
            "UNITY_PASSWORD": "secret123",
        })
        assert result.stdout.strip() == "account"

    def test_no_secret_values_leaked(self):
        result = run_strategy({
            "UNITY_LICENSE": self.VALID_ULF,
            "UNITY_EMAIL": "leak-check@example.com",
            "UNITY_PASSWORD": "SUPERSECRETVALUE",
        })
        assert "SUPERSECRETVALUE" not in result.stdout
        assert "SUPERSECRETVALUE" not in result.stderr
