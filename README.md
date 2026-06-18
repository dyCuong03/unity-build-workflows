# unity-build-workflows

Docker-mandatory reusable GitHub Actions workflows for building, testing, and releasing Unity games. All Unity operations run inside pinned, versioned Docker containers — the CI runner never executes Unity directly.

---

## What This Repository Is

`unity-build-workflows` is a CI/CD platform library. Unity game repositories call its reusable workflows. This repository manages:

- Docker image definitions for Unity build environments
- Container entrypoints that invoke Unity in batch mode
- Reusable GitHub Actions workflows for build orchestration
- Build configuration schemas and validation
- Image security scanning and SBOM generation

**Docker is mandatory.** There is no native Unity execution fallback.

---

## Architecture

```
Your Game Repo
  .github/workflows/build.yml
       │ uses: BuzzelStudio/unity-build-workflows/.github/workflows/unity-build.yml@v2
       │       secrets: inherit
       ▼
unity-build-workflows
  CI Runner (ubuntu-latest)
       │
       ▼
  Docker Engine
       │
       ▼
  Pinned Unity Build Image (ghcr.io/buzzelstudio/unity-builder@sha256:...)
       │
       ▼
  entrypoint.sh → Unity -batchmode -executeMethod BuildCommand.Execute
       │
       ▼
  Artifacts, logs, reports → bind-mounted host directories
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the complete layer diagram.

---

## Supported Platforms

| Platform | Executor | Runner OS | Status |
|---|---|---|---|
| Android | `docker-unity` | ubuntu-latest | **Supported** |
| WebGL | `docker-unity` | ubuntu-latest | **Supported** |
| Linux Standalone | `docker-unity` | ubuntu-latest | **Supported** |
| Linux Dedicated Server | `docker-unity` | ubuntu-latest | **Supported** |
| **iOS** | `macos-unity-xcode` | macos-13+ | **Supported** (v2.1.0+) |

### Unsupported Platforms

| Platform | Reason |
|---|---|
| Windows | Requires Windows containers. Use a dedicated Windows pipeline. See [docs/PLATFORM_LIMITATIONS.md](docs/PLATFORM_LIMITATIONS.md). |

Unsupported targets fail with an actionable error message. The repository never silently falls back to native Unity execution.

---

## Minimal Integration

### 1. Add a BuildConfig

```bash
mkdir BuildConfig
cp templates/BuildConfig.base.example.json BuildConfig/base.json
cp templates/BuildConfig.staging.example.json BuildConfig/staging.json
# Edit projectName, applicationId, scenes, etc.
```

### 2. Add secrets

At minimum: `UNITY_LICENSE`. See [templates/build-secrets.example.md](templates/build-secrets.example.md).

### 3. Create `.github/workflows/build.yml`

**Android/WebGL/Linux (Docker lane):**
```yaml
name: Unity Docker CI

on:
  pull_request:
  push:
    branches: [develop, staging]
  workflow_dispatch:

jobs:
  build-android:
    uses: BuzzelStudio/unity-build-workflows/.github/workflows/unity-build.yml@v2
    with:
      project-path: .
      unity-version: '6000.0.26f1'
      target-platform: Android
      environment: development
      build-config-path: BuildConfig
      test-level: editmode
      cache-mode: safe
      upload-artifact: true
    secrets: inherit
```

**iOS (macOS lane):**
```yaml
name: iOS Build

on:
  push:
    branches: [main, release/*]
  workflow_dispatch:

jobs:
  build-ios:
    uses: BuzzelStudio/unity-build-workflows/.github/workflows/unity-build-ios.yml@v2
    with:
      project-path: .
      unity-version: '6000.0.26f1'
      target-platform: iOS
      environment: staging
      build-config-path: BuildConfig
      upload-artifact: true
    secrets: inherit
```

The executor is selected automatically from `target-platform` — no `executor-mode` input exists.

See [docs/ADD_NEW_PROJECT.md](docs/ADD_NEW_PROJECT.md) for the full onboarding walkthrough.
See [docs/IOS.md](docs/IOS.md) for the iOS pipeline guide.

### 4. Add iOS Secrets (iOS builds only)

For iOS, add these secrets at **Settings → Secrets and variables → Actions**:

```
UNITY_LICENSE                           # .ulf license content
UNITY_EMAIL                             # Unity account email
UNITY_PASSWORD                          # Unity account password
IOS_DISTRIBUTION_CERTIFICATE_BASE64    # Base64-encoded .p12 certificate
IOS_DISTRIBUTION_CERTIFICATE_PASSWORD  # .p12 export password
IOS_PROVISIONING_PROFILE_BASE64        # Base64-encoded .mobileprovision
APP_STORE_CONNECT_KEY_ID               # ASC API key ID (for TestFlight)
APP_STORE_CONNECT_ISSUER_ID            # ASC issuer UUID (for TestFlight)
APP_STORE_CONNECT_PRIVATE_KEY          # .p8 key contents (for TestFlight)
```

See [docs/IOS_SIGNING.md](docs/IOS_SIGNING.md) for setup instructions.

### 5. Enable Discord Notifications (optional)

Add a single secret to receive build-completion embeds in a Discord channel:

```
DISCORD_WEBHOOK_URL    # Discord webhook URL — omit to disable notifications
```

Notifications cover success, failure, and cancelled status. If the secret is not set the workflows skip the notification step silently — no YAML changes needed to disable. See [docs/DISCORD_NOTIFICATIONS.md](docs/DISCORD_NOTIFICATIONS.md) for setup and behaviour.

---

## Local Build Commands

Local builds also use Docker:

```bash
# Android build
python3 scripts/docker/run_unity_container.py \
  --project-path . \
  --unity-version 6000.0.26f1 \
  --target-platform Android \
  --environment development \
  --build-config-path BuildConfig

# EditMode tests
python3 scripts/docker/run_unity_container.py \
  --project-path . \
  --unity-version 6000.0.26f1 \
  --target-platform Android \
  --test-level editmode

# Convenience targets (if Makefile present)
make unity-build-android
make unity-test-editmode
make unity-build-webgl
```

**Prerequisites:** Docker Engine installed and running. No local Unity installation required for builds.

---

## Docker Image Strategy

Images extend pinned [GameCI](https://game.ci/) base images with an organizational tooling layer:

```
unityci/editor:6000.0.26f1-android-3  (pinned GameCI base)
  └─ ghcr.io/buzzelstudio/unity-builder:6000.0.26f1-android-v2.0.0  (org layer)
       └─ entrypoint.sh, license scripts, healthcheck, python3, jq
```

Production workflows resolve and pin images by digest:
```
ghcr.io/buzzelstudio/unity-builder@sha256:<digest>
```

See [docs/IMAGE_LIFECYCLE.md](docs/IMAGE_LIFECYCLE.md) for the full image strategy.

---

## Required Docker Version

- Docker Engine 20.10+ (BuildKit support)
- Docker Compose is not required

---

## Versioning Policy

Semantic versioning. Consumer repositories reference a major version tag:

```yaml
uses: BuzzelStudio/unity-build-workflows/.github/workflows/unity-build.yml@v2
```

- `@v2` points to the latest `2.x.x` release.
- Major version increments indicate breaking changes to the workflow input interface.
- Pin to exact version for reproducibility: `@v2.0.0`.

Current version: **2.2.0** — see [CHANGELOG.md](CHANGELOG.md).

---

## Documentation

| Document | Contents |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Layer diagram, executor lanes (docker-unity + macos-unity-xcode), extension points |
| [docs/DOCKER_BUILD.md](docs/DOCKER_BUILD.md) | Container flow, mounts, caches, licensing, debugging |
| [docs/IMAGE_LIFECYCLE.md](docs/IMAGE_LIFECYCLE.md) | Base image, variants, scanning, SBOM, tagging, deprecation |
| [docs/ADD_NEW_PROJECT.md](docs/ADD_NEW_PROJECT.md) | Step-by-step onboarding guide |
| [docs/BUILD_CONFIG.md](docs/BUILD_CONFIG.md) | Every BuildConfig field documented (including full iOS section) |
| [docs/ANDROID.md](docs/ANDROID.md) | Android signing, AAB, symbol export via Docker |
| [docs/IOS.md](docs/IOS.md) | **NEW** — Full iOS pipeline: Unity → Xcode → archive → IPA → TestFlight |
| [docs/IOS_SIGNING.md](docs/IOS_SIGNING.md) | **NEW** — Certificate, provisioning profile, ASC key setup |
| [docs/IOS_RELEASE.md](docs/IOS_RELEASE.md) | **NEW** — Release workflow, protected environment, versioning, TestFlight |
| [docs/IOS_VERIFICATION.md](docs/IOS_VERIFICATION.md) | **NEW** — macOS runner verification runbook (Level 0–3, checklist) |
| [docs/WEBGL.md](docs/WEBGL.md) | WebGL compression, hosting via Docker |
| [docs/LINUX.md](docs/LINUX.md) | Linux standalone and dedicated server builds |
| [docs/PLATFORM_LIMITATIONS.md](docs/PLATFORM_LIMITATIONS.md) | iOS now supported via macOS; Windows unsupported; GPU/native plugin limits |
| [docs/RELEASE_FLOW.md](docs/RELEASE_FLOW.md) | Tag-based release, environments, digest enforcement |
| [docs/SELF_HOSTED_RUNNER.md](docs/SELF_HOSTED_RUNNER.md) | Runner setup with Docker requirements |
| [docs/SECURITY.md](docs/SECURITY.md) | Secret handling, iOS credentials, image trust, fork safety |
| [docs/DISCORD_NOTIFICATIONS.md](docs/DISCORD_NOTIFICATIONS.md) | **NEW** — Discord build-completion notifications: setup, security, embed format |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Docker, Unity, and iOS errors; cert rotation; Xcode migration |
| [docs/adr/001-docker-mandatory-architecture.md](docs/adr/001-docker-mandatory-architecture.md) | Architecture decision record |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) — © 2024 BuzzelStudio
