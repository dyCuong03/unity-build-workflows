# Adding a New Project

This guide walks through integrating a new Unity project with the Docker-mandatory `unity-build-workflows` platform.

---

## Prerequisites

- GitHub repository for your Unity project
- Unity 6 (6000.x) or Unity 2022.3 LTS or later
- GitHub Actions enabled on your repository
- Access to the `BuzzelStudio/unity-build-workflows` repository
- Docker Engine available on CI runners (GitHub-hosted `ubuntu-latest` includes Docker)

**You do not need Unity installed locally to use CI builds.** Docker handles the Unity environment.

---

## Step 1: Set Up GitHub Secrets

Navigate to **Settings → Secrets and variables → Actions** and add:

**Minimum required:**
```
UNITY_LICENSE        # Complete .ulf file content (not base64-encoded)
```

**For Android production builds:**
```
ANDROID_KEYSTORE_BASE64
ANDROID_KEYSTORE_PASS
ANDROID_KEY_ALIAS
ANDROID_KEY_PASS
```

**For Google Play deployment:**
```
GOOGLE_PLAY_SERVICE_ACCOUNT_JSON
```

See [templates/build-secrets.example.md](../templates/build-secrets.example.md) for the full list.

---

## Step 2: Create Your BuildConfig Files

Create a `BuildConfig/` directory in your repository root:

```bash
mkdir -p BuildConfig
```

Copy and adapt the templates:

```bash
cp path/to/unity-build-workflows/templates/BuildConfig.base.example.json BuildConfig/base.json
cp path/to/unity-build-workflows/templates/BuildConfig.staging.example.json BuildConfig/staging.json
cp path/to/unity-build-workflows/templates/BuildConfig.production.example.json BuildConfig/production.json
```

Edit `BuildConfig/base.json`:

| Field | Change To |
|---|---|
| `projectName` | Your project identifier |
| `companyName` | Your company name |
| `productName` | Display name of your game |
| `android.applicationId` | Your Android package name |
| `scenes` | Paths to your scenes in load order |

---

## Step 3: Create Your GitHub Actions Workflow

Create `.github/workflows/build.yml`:

```yaml
name: Unity Docker CI

on:
  pull_request:
  push:
    branches: [develop, staging]
  workflow_dispatch:
    inputs:
      platform:
        type: choice
        options:
          - Android
          - WebGL
          - Linux64

jobs:
  build:
    uses: BuzzelStudio/unity-build-workflows/.github/workflows/unity-build.yml@v2
    with:
      project-path: .
      unity-version: '6000.0.26f1'
      target-platform: ${{ inputs.platform || 'Android' }}
      environment: development
      build-config-path: BuildConfig
      test-level: editmode
      cache-mode: safe
      upload-artifact: true
    secrets: inherit
```

No Docker or executor options needed — Docker is mandatory and implicit.

---

## Step 4: Configure GitHub Environments

For staging and production builds:

1. **Settings → Environments → New environment**
2. Create `staging`:
   - Deployment branch: `main`
3. Create `production`:
   - Required reviewers: at least one person
   - Deployment branch: tags matching `v*`
   - Move production secrets to this environment

---

## Step 5: Test a Development Build

Push to a feature branch or trigger manually:

```bash
git push origin feature/ci-setup
```

Or: **Actions → Unity Docker CI → Run workflow → development**

Verify:
- [ ] Schema validation passes
- [ ] Docker image pulled successfully
- [ ] Unity runs inside container (check logs for `docker run`)
- [ ] Build completes without errors
- [ ] Artifact is uploaded and downloadable
- [ ] Editor.log is present in build reports

---

## Step 6: Test Locally with Docker

Run builds locally using the same Docker images as CI:

```bash
python3 scripts/docker/run_unity_container.py \
  --project-path /path/to/your/project \
  --unity-version 6000.0.26f1 \
  --target-platform Android \
  --environment development \
  --build-config-path BuildConfig
```

Prerequisites: Docker Engine running locally.

---

## Step 7: Configure Discord Notifications (Optional)

To receive build-completion messages in a Discord channel:

1. In Discord: **Server Settings → Integrations → Webhooks → New Webhook**. Select the target channel and copy the webhook URL.
2. In GitHub: **Settings → Secrets and variables → Actions → New repository secret**.
   - Name: `DISCORD_WEBHOOK_URL`
   - Value: the Discord webhook URL

That's it. The `unity-build.yml`, `unity-build-ios.yml`, `unity-release.yml`, and `unity-release-ios.yml` workflows will automatically post embeds on success, failure, and cancellation.

If `DISCORD_WEBHOOK_URL` is not set the notification step skips silently — the build is never affected.

See [DISCORD_NOTIFICATIONS.md](DISCORD_NOTIFICATIONS.md) for full details including embed format, security notes, and troubleshooting.

---

## Supported Platforms

| Platform | Workflow Input |
|---|---|
| Android | `target-platform: Android` |
| WebGL | `target-platform: WebGL` |
| Linux Standalone | `target-platform: Linux64` |
| Linux Server | `target-platform: LinuxServer` |

iOS and Windows are **not supported** by this Docker-only platform. See [PLATFORM_LIMITATIONS.md](PLATFORM_LIMITATIONS.md).

---

## Troubleshooting First-Time Setup

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

Common issues:
- **"Unity license activation failed"** — Check `UNITY_LICENSE` contains the complete `.ulf` file content.
- **"Cannot connect to Docker daemon"** — Ensure Docker is available on the runner.
- **"Image not found"** — The Unity image for your version may need to be built first.
- **"Schema validation failed"** — Run validation locally against the schema.
