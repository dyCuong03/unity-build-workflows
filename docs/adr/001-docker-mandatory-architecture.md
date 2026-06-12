# ADR-001: Docker-Mandatory Unity Build Architecture

**Status:** Accepted
**Date:** 2026-06-12
**Decision Makers:** BuzzelStudio Build Platform Team

## Context

The unity-build-workflows repository (v1.0.0) executes Unity Editor directly on CI runners across four platform-specific workflows. Each workflow installs Unity via the `setup-unity` composite action and invokes Unity in batch mode natively.

### Problems with Native Execution

1. **Environment drift** — Runner OS updates, pre-installed tool changes, and Unity Hub version mismatches cause non-reproducible builds.
2. **Platform sprawl** — Four separate runner types (ubuntu-latest, macos-latest, windows-latest) with distinct Unity installation paths and license activation methods.
3. **Cache fragility** — Library caches tied to runner OS versions break unpredictably.
4. **Security surface** — Unity licensing credentials handled differently per platform with inconsistent cleanup.
5. **Scaling cost** — macOS and Windows runners are significantly more expensive than Linux runners.
6. **No image versioning** — Build environment is implicit and unversioned.

## Decision

**All Unity compilation, testing, Addressables builds, player builds, and validation must run inside Docker containers.** The CI runner serves only as an orchestrator that invokes Docker.

### Architecture

```
CI Runner (ubuntu-latest)
  └─ Docker Engine
       └─ Pinned Unity Build Image (ghcr.io/buzzelstudio/unity-builder@sha256:...)
            └─ entrypoint.sh
                 └─ Unity Editor -batchmode
                      └─ Company.BuildPipeline.BuildCommand.Execute
                           └─ Artifacts, logs, reports → bind-mounted host directories
```

### Image Strategy

**Selected approach:** Thin organization-owned image extending pinned GameCI base images.

- **Base:** `unityci/editor:<version>-<module>-<gameci-version>` (pinned by digest in production)
- **Organization layer:** Adds entrypoint, license scripts, healthcheck, system tools (python3, jq)
- **Variants:** android, webgl, linux (separate images per module set)

**Rejected alternatives:**

- *Fully custom image:* Excessive maintenance burden for Unity Editor installation, module management, and SDK toolchain setup. GameCI maintains this well.
- *GameCI images directly:* No organizational entrypoint, no standardized license handling, no image contract versioning.

### Supported Platforms

| Platform | Docker Support | Status |
|---|---|---|
| Android | Full (Linux container) | Supported |
| WebGL | Full (Linux container) | Supported |
| Linux64 | Full (Linux container) | Supported |
| LinuxServer | Full (Linux container) | Supported |
| iOS | Requires macOS host + Xcode | **Unsupported** — use dedicated macOS pipeline |
| Windows64 | Requires Windows containers | **Unsupported** — use dedicated Windows pipeline |

### Platform Exclusion Rationale

- **iOS:** Unity iOS builds produce an Xcode project requiring macOS-native Xcode toolchain for final IPA signing and archive export. No verified Docker solution exists for the full pipeline.
- **Windows:** Unity Windows builds require Windows containers on Windows Docker hosts. Unverified in our CI environment. Not claiming support without proof.

## Consequences

### Breaking Changes

- `executor-mode`, `use-docker`, `native-runner` workflow inputs removed
- `unity-build-ios.yml` and `unity-build-windows.yml` workflows removed
- `setup-unity` composite action removed (Docker image has Unity pre-installed)
- Nightly builds matrix reduced to [Android, WebGL, Linux64]
- All consuming repositories must update workflow references

### Benefits

- Reproducible builds via pinned, versioned, scanned images
- Single runner type (ubuntu-latest) for all supported builds
- Consistent license handling across all platforms
- Image-level security scanning and SBOM generation
- Build environment is a versioned, auditable artifact

### Risks

- iOS and Windows builds require separate, non-Docker pipelines
- Initial migration effort for consuming repositories
- Docker image build and publication adds infrastructure overhead
- GameCI base image dependency (mitigated by digest pinning)

## Migration

See CHANGELOG.md for the v2.0.0 migration guide.
