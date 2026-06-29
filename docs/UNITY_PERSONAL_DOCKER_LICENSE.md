# Unity Personal / Free License — Docker CI Activation

This document describes how Unity Personal (free) licenses are activated inside
ephemeral Docker containers in the unity-build-workflows CI system.

Related docs:
- [GITHUB\_ACTIONS\_BUILD\_RUNBOOK.md](GITHUB_ACTIONS_BUILD_RUNBOOK.md) — end-to-end build operations
- [UNITY\_VERSION\_UPGRADE.md](UNITY_VERSION_UPGRADE.md) — upgrading the Unity version

---

## Overview

Unity Personal licenses are machine-bound. A `.ulf` file issued on one machine
cannot be used standalone on another — attempting to do so fails with
`TimeStamp validation failed`. Conversely, providing only account credentials
(email + password) in a Docker container without a `.ulf` present results in
`0 entitlements`.

**The only reliable path for Unity Personal/free in ephemeral Docker is the
`personal-combined` strategy: provide `UNITY_LICENSE` (raw `.ulf` contents),
`UNITY_EMAIL`, and `UNITY_PASSWORD` together.**  This is the approach used by
[GameCI](https://game.ci/) and is implemented in this toolkit.

---

## The `personal-combined` Strategy

### How it works

Implemented in:
- `docker/unity/activate-license.sh` — execution
- `scripts/common/resolve_activation_strategy.sh` — strategy selection

**Strategy selection** (in `activate-license.sh`, lines 103–151):

When `UNITY_LICENSE`, `UNITY_EMAIL`, and `UNITY_PASSWORD` are **all** set,
`personal-combined` is selected immediately, before any other logic runs.
No strategy resolver call is needed.

In `resolve_activation_strategy.sh` the same condition is evaluated as
Strategy 0 — the highest-priority auto strategy.

**Execution** (`personal-combined` case in `activate-license.sh`):

1. The `.ulf` content from `UNITY_LICENSE` is written to
   `~/.local/share/unity3d/Unity/Unity_lic.ulf` (permissions `600`).
   - If that path already contains a `.ulf` (e.g. a host-mounted pre-activated
     file), it is reused without overwriting.
   - Encoding is handled automatically (see [Raw vs Base64](#raw-vs-base64)).
2. Unity is invoked in batch mode with `-username` and `-password`:
   ```
   unity-editor -batchmode -nographics \
     -username <UNITY_EMAIL> \
     -password <UNITY_PASSWORD> \
     -logFile /tmp/unity-home/Editor.log \
     -quit
   ```
3. On success, Unity exits 0 and logs `Activation successful`.
4. On failure, the failure class is determined from `Editor.log` and a fallback
   to `manual-ulf` is attempted; if that also fails, the build exits 1.

### Why all three secrets are required

| Secrets provided | Result |
|---|---|
| `UNITY_LICENSE` only (`.ulf` alone) | `TimeStamp validation failed` — file is machine-bound |
| `UNITY_EMAIL` + `UNITY_PASSWORD` only | `0 entitlements` — no seat entitlement found |
| All three together (`personal-combined`) | `Activation successful` |

---

## Required Secrets

Set these three secrets in the **consumer** repository
(`Settings → Secrets and variables → Actions`):

| Secret | Description |
|---|---|
| `UNITY_LICENSE` | Raw `.ulf` file contents (see below for how to find it) |
| `UNITY_EMAIL` | Email address of the Unity account that owns the license |
| `UNITY_PASSWORD` | Password of the Unity account |

> **Security:** Never print, log, or commit secret values. The scripts
> deliberately redact all secret content from logs — only presence (set/unset)
> is ever logged.

---

## Finding Your Local `Unity_lic.ulf` File

Unity Hub writes the `.ulf` license file to a platform-specific path after
license activation. On a Windows host accessed from WSL:

```bash
# Search common Windows/WSL Unity license locations
find /mnt/c/ProgramData/Unity /mnt/c/Users ~/.local/share/unity3d \
  -iname "Unity_lic.ulf" -type f -size +0c 2>/dev/null
```

Typical paths:

| OS | Path |
|---|---|
| Windows | `C:\ProgramData\Unity\Unity_lic.ulf` |
| macOS | `/Library/Application Support/Unity/Unity_lic.ulf` |
| Linux | `~/.local/share/unity3d/Unity/Unity_lic.ulf` |

The file is a signed XML document beginning with `<?xml`. Do **not** modify it.

---

## Recommended Secret Setup Commands

```bash
# 1. Set UNITY_LICENSE — pipe the raw .ulf file contents directly
#    (replace the path with the actual location found above)
ULF="/mnt/c/ProgramData/Unity/Unity_lic.ulf"
gh secret set UNITY_LICENSE --repo dyCuong03/NDC-Unity-Template < "$ULF"

# 2. Set UNITY_EMAIL — enter interactively when prompted
gh secret set UNITY_EMAIL --repo dyCuong03/NDC-Unity-Template

# 3. Set UNITY_PASSWORD — enter interactively when prompted
gh secret set UNITY_PASSWORD --repo dyCuong03/NDC-Unity-Template
```

> Pipe `UNITY_LICENSE` from the file rather than copy-pasting to avoid
> shell escaping issues and accidental whitespace changes.

---

## Verifying Secrets Are Set

Check that all three secrets are present (names only — values are never shown):

```bash
gh secret list --repo dyCuong03/NDC-Unity-Template \
  | grep -E 'UNITY_LICENSE|UNITY_EMAIL|UNITY_PASSWORD'
```

Expected output (timestamps will vary):

```
UNITY_EMAIL      Updated 2026-06-29
UNITY_LICENSE    Updated 2026-06-29
UNITY_PASSWORD   Updated 2026-06-29
```

---

## Raw vs Base64 (`UNITY_LICENSE_ENCODING`)

| Value | Behavior |
|---|---|
| *(unset / default)* | `auto` — tries base64 decode; falls back to raw if decode fails |
| `raw` | Treat `UNITY_LICENSE` as-is (raw XML) |
| `base64` | Force base64 decode before writing the `.ulf` |

**Default is raw.** A standard `.ulf` file starts with `<?xml` which is not
valid base64, so `auto` falls through to raw automatically.

**Do NOT base64-encode the `.ulf` when setting the secret.** Pipe the raw file
directly (as shown above). Base64-encoding is NOT required and is incompatible
with the GameCI-style activation path.

```bash
# CORRECT — raw file contents
gh secret set UNITY_LICENSE --repo dyCuong03/NDC-Unity-Template < Unity_lic.ulf

# WRONG — do not base64-encode
gh secret set UNITY_LICENSE --repo dyCuong03/NDC-Unity-Template \
  <<< "$(base64 Unity_lic.ulf)"
```

---

## Troubleshooting

### Failure classification

`activate-license.sh` classifies failures by scanning `Editor.log` for known
patterns. The classified failure name appears in CI logs as:
```
[ERROR] activate-license: License activation failed (personal-combined): <CLASS>
```

### Troubleshooting table

| Symptom / Log String | Cause | Fix |
|---|---|---|
| `TimeStamp validation failed` | `UNITY_LICENSE` set but `UNITY_EMAIL`/`UNITY_PASSWORD` missing — `.ulf` alone is machine-bound | Set all three secrets; use `personal-combined` strategy |
| `0 entitlements` | `UNITY_EMAIL`/`UNITY_PASSWORD` set but `UNITY_LICENSE` missing — no seat entitlement without `.ulf` | Add `UNITY_LICENSE` secret (raw `.ulf` contents) |
| `LICENSE_FILE_INVALID` / `license.*invalid` in log | `UNITY_LICENSE` contains invalid XML, wrong file type, or empty value | Re-export the `.ulf` from Unity Hub; verify `find` command above finds a non-empty file |
| `UNITY_LICENSE contains UnityEntitlementLicense XML (not a .ulf)` | A `.xml` entitlement file was set instead of a `.ulf` | Use the `.ulf` file, **not** `UnityEntitlementLicense.xml` |
| `UNITY_LICENSE decoded to empty file` | Secret is set to an empty string or whitespace | Delete the secret and re-set it: `gh secret set UNITY_LICENSE --repo dyCuong03/NDC-Unity-Template < Unity_lic.ulf` |
| `UNITY_LICENSE accidentally base64-encoded` | `UNITY_LICENSE_ENCODING` forced to `base64` but value is raw, or vice-versa | Remove `UNITY_LICENSE_ENCODING` override; set secret as raw `.ulf` file |
| `AUTH_FAILED` / `invalid.*password\|auth.*fail` in log | Wrong email or password in secrets | Re-set `UNITY_EMAIL` / `UNITY_PASSWORD`; confirm credentials work at id.unity.com |
| `MFA_OR_2FA_REQUIRED` / `two.factor\|2fa` in log | The Unity account has MFA/2FA enabled | Disable 2FA on the CI Unity account, or use a dedicated CI account without 2FA |
| `ACTIVATION_LIMIT_REACHED` / `activation.*limit` in log | Maximum number of activations for this license exceeded | Return a seat in Unity Hub (Manage License → Return License) then retry |
| `PERSONAL_LICENSE_ONLINE_ACTIVATION_UNSUPPORTED` | Certain Unity versions block online Personal activation | Use the `UNITY_LICENSE` `.ulf` (all three secrets) to avoid online-only activation |
| `UNITY_SERVICE_UNAVAILABLE` / `service.*unavailable\|connect.*fail\|timeout` | Unity license server temporarily unreachable | Retry the workflow; check status.unity.com |
| `No valid Unity license found` in log at build step | Activation succeeded but the license file was cleaned up, or activation was skipped | Verify all three secrets are set and non-empty; check activation step log |
| Wrong Unity version image | Docker image built for a different Unity version than `ProjectVersion.txt` | Rebuild images for the correct version — see [UNITY\_VERSION\_UPGRADE.md](UNITY_VERSION_UPGRADE.md) |

### What NOT to do

- Do **not** set `UNITY_SERIAL` — this is a Pro/Plus/Enterprise field; Personal
  licenses do not have a serial number.
- Do **not** use `UnityEntitlementLicense.xml` as `UNITY_LICENSE`.
- Do **not** pass a `.alf` (activation request file) as `UNITY_LICENSE`.
- Do **not** print or log secret values when debugging.
