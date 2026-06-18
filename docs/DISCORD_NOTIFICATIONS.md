# Discord Build Notifications

This document describes the optional Discord build-completion notification system for the `unity-build-workflows` platform.

---

## Overview

The `.github/actions/discord-notify` composite action posts a Discord embed to a configured webhook URL at the end of each build run. It uses `curl` directly — no third-party GitHub Action is involved, eliminating supply-chain risk.

Notifications are **optional**: if `DISCORD_WEBHOOK_URL` is not set the action no-ops silently and the build succeeds normally. A webhook misconfiguration or Discord service outage will never fail your pipeline.

---

## Secret: `DISCORD_WEBHOOK_URL`

| Secret | Scope | Required |
|---|---|---|
| `DISCORD_WEBHOOK_URL` | Repository or Environment | No (optional) |

The webhook URL is read from the `DISCORD_WEBHOOK_URL` environment variable inside the action — it is **never** an action `input`. This keeps the value away from workflow inputs (which can appear in run summaries and API responses) and limits exposure to the job environment.

### How to create a Discord webhook

1. Open your Discord server → **Server Settings → Integrations → Webhooks**.
2. Click **New Webhook**, give it a name (e.g. `Unity CI`), select the target channel, and copy the URL.
3. In your GitHub repository: **Settings → Secrets and variables → Actions → New repository secret**.
4. Name: `DISCORD_WEBHOOK_URL` — Value: the copied webhook URL.

For production builds using GitHub Environments, add the secret to the environment instead of the repository if you want channel-level isolation between development and production.

---

## Which Workflows Notify

| Workflow | Job | Condition | Platform(s) |
|---|---|---|---|
| `unity-build.yml` | `report` | `if: always()` — fires on success, failure, and cancelled | Android, WebGL, Linux64, LinuxServer, iOS (via orchestrator) |
| `unity-build-ios.yml` | `build` | `if: always()` — fires on success, failure, and cancelled | iOS (direct caller) |
| `unity-release-ios.yml` | `release-build` | `if: always()` — fires on success, failure, and cancelled | iOS production release |
| `unity-release.yml` | `notify` (dedicated job) | `if: always()` — fires on success, failure, and cancelled | Android, WebGL, Linux64 production release |

The `unity-build.yml` orchestrator report job also covers iOS when called via `unity-build.yml`. `unity-build-ios.yml` called directly (e.g. from your project workflow) sends its own notification.

---

## Behavior by Build Status

| Status | Embed colour | Emoji | Description |
|---|---|---|---|
| `success` | Green (`#2ECC71`) | ✅ | Build completed successfully |
| `failure` | Red (`#E74C3C`) | ❌ | Build failed — includes platform, version, and a link to the failed run |
| `cancelled` | Grey (`#9B9B9B`) | ⚠️ | Workflow was cancelled mid-run |

Any unrecognised status value is treated as `cancelled` (grey / ⚠️).

---

## No-op When Unset

If `DISCORD_WEBHOOK_URL` is empty or unset the action writes a `::notice::` log line and exits with code `0`. The build outcome is unchanged. No network call is made.

This means:
- Projects that don't configure Discord work with zero changes.
- Removing the secret disables notifications without touching workflow YAML.
- CI forks (e.g. open-source PRs) that don't have the secret skip notifications automatically.

---

## Embed Fields

Each notification embed includes:

| Field | Value |
|---|---|
| Repository | `owner/repo` |
| Platform | Target platform (iOS, Android, WebGL, …) |
| Environment | Build environment (development, staging, production) |
| Version | Resolved build version string |
| Commit | Short SHA (first 7 characters) |
| Triggered by | `github.actor` (person or bot that triggered the run) |
| Artifact | Artifact name — included when available (success builds) |

The embed title links to the GitHub Actions run page.

---

## Example Embed

```
✅ Build Success — iOS / production
──────────────────────────────────────────────────
Repository   owner/my-game       Platform     iOS
Environment  production          Version      1.4.2
Commit       `a3f7c9d`           Triggered by cuongnd
Artifact     ios-release-ipa-1.4.2-42
──────────────────────────────────────────────────
```

A failed build looks the same with a red embed and ❌ in the title.

---

## Security Notes

1. **Webhook URL never logged.** The action calls `set +x` before any reference to the URL and calls `::add-mask::` to add the value to GitHub's log masker. Even if the value somehow leaks to output, Actions redacts it.
2. **No third-party action.** All HTTP calls go through `curl` in a `bash` step — no code from an external action repository is executed.
3. **Failure is non-fatal.** `curl` errors (network timeouts, non-2xx responses) log a `::warning::` and exit `0`. A Discord outage cannot block a release.
4. **Payload validated before sending.** The JSON payload is validated with `python3 -c "import json,sys; json.load(sys.stdin)"` before the `curl` call. If validation fails the notification is skipped (not a pipeline failure).
5. **No sensitive build values in payload.** The embed contains version strings, commit SHAs, actor names, and platform names — nothing from signing secrets or license files.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| No notification, no warning | `DISCORD_WEBHOOK_URL` not set in repo secrets | Add the secret (see above) |
| `::warning:: Discord notify: unexpected HTTP 401` | Invalid or revoked webhook | Regenerate the webhook in Discord and update the secret |
| `::warning:: Discord notify: unexpected HTTP 404` | Webhook deleted in Discord | Recreate the webhook |
| `::warning:: Discord notify: curl failed` | Network timeout / runner DNS issue | Transient — retry or check runner network; build is unaffected |
| Embed posted but fields are empty | `github.*` context not available (unusual) | File an issue with the workflow name and trigger |
