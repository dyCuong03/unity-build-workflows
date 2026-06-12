# Changelog

All notable changes to `unity-build-workflows` are documented here.

This project adheres to [Semantic Versioning](https://semver.org/) and [Conventional Commits](https://www.conventionalcommits.org/).

The public API is the set of reusable workflow inputs/outputs documented in [docs/BUILD_CONFIG.md](docs/BUILD_CONFIG.md). Changes to that interface that require consumer updates are marked as **BREAKING**.

---

## [Unreleased]

---

## [2.0.0] — 2026-06-12

### BREAKING CHANGES

This release migrates the entire build platform from native Unity Editor execution to Docker-mandatory containers. **All consuming repositories must update their workflow references from `@v1` to `@v2`.**

#### Removed Workflows
- **`unity-build-ios.yml`** — iOS is unsupported by the Docker-only platform. Use a dedicated macOS pipeline. See [docs/PLATFORM_LIMITATIONS.md](docs/PLATFORM_LIMITATIONS.md).
- **`unity-build-windows.yml`** — Windows is unsupported by the Docker-only platform. Use a dedicated Windows pipeline.

#### Removed Workflow Inputs
- `executor-mode` — Docker is now mandatory and implicit.
- `use-docker` — Removed; Docker is the only executor.
- `native-runner` — Removed; no native execution path exists.

#### Removed Actions
- `actions/setup-unity/` — Docker images have Unity pre-installed. No host-side Unity installation needed.

#### Removed Scripts
- `scripts/run_unity_build.py` — Replaced by `scripts/docker/run_unity_container.py`.
- `scripts/ios/` — iOS pipeline removed.
- `scripts/windows/` — Windows pipeline removed.

#### Changed Workflow API
- All build/test workflows now require Docker Engine on the runner.
- `runs-on` changed to `ubuntu-latest` for all supported builds (was platform-specific).
- Image resolution is automatic from the approved image manifest.
- Nightly build matrix reduced to `[Android, WebGL, Linux64]`.

### Added

#### Docker Platform
- `docker/unity/Dockerfile` — Base Unity image extending pinned GameCI base.
- `docker/variants/android.Dockerfile` — Android build image with SDK/NDK/JDK.
- `docker/variants/webgl.Dockerfile` — WebGL build image.
- `docker/variants/linux.Dockerfile` — Linux standalone and dedicated server image.
- `docker/unity/entrypoint.sh` — Strict container entrypoint supporting build, test, validate, and inspect commands.
- `docker/unity/healthcheck.sh` — Image health verification.
- `docker/unity/activate-license.sh` — Ephemeral license activation.
- `docker/unity/return-license.sh` — License cleanup.
- `docker/metadata/image-manifest.schema.json` — Image manifest JSON Schema.

#### Docker Scripts
- `scripts/docker/run_unity_container.py` — Single entry point for running Unity in Docker (CI and local).
- `scripts/docker/build_unity_image.py` — Image build automation.
- `scripts/docker/validate_unity_image.py` — Image validation and compliance.
- `scripts/docker/resolve_image_reference.py` — Target platform to image resolution.
- `scripts/docker/generate_sbom.sh` — SBOM generation.
- `scripts/docker/scan_image.sh` — Vulnerability scanning.

#### New Workflows
- `build-unity-image.yml` — Dedicated image build, scan, and publish workflow.
- `scan-unity-image.yml` — Scheduled image vulnerability scanning.
- `unity-build-linux.yml` — Linux standalone and dedicated server builds.

#### New Actions
- `actions/resolve-unity-image/` — Resolve target platform to approved image.
- `actions/run-unity-container/` — Standardized Docker container execution.
- `actions/restore-docker-cache/` — Docker volume-based Library cache.

#### New Documentation
- `docs/DOCKER_BUILD.md` — Container execution flow documentation.
- `docs/IMAGE_LIFECYCLE.md` — Image strategy, scanning, SBOM, tagging.
- `docs/LINUX.md` — Linux platform documentation.
- `docs/PLATFORM_LIMITATIONS.md` — iOS/Windows exclusion rationale and alternatives.
- `docs/adr/001-docker-mandatory-architecture.md` — Architecture decision record.

#### Schemas
- `schemas/unity-image-manifest.schema.json` — Image manifest validation schema.

#### Tests
- `tests/test_docker_command.py` — Docker command construction tests.
- `tests/test_image_resolution.py` — Image reference resolution tests.
- `tests/test_image_manifest.py` — Image manifest schema tests.
- `tests/test_secret_redaction.py` — Secret leak prevention tests.
- `tests/test_no_native_unity_invocation.py` — Regression test preventing native Unity execution.
- `tests/test_entrypoint.py` — Entrypoint integration tests with fake Unity.

#### Platform Support
- Linux Standalone (Linux64) builds via Docker.
- Linux Dedicated Server (LinuxServer) builds via Docker.

### Changed
- All Unity compilation, tests, and builds now execute inside Docker containers.
- Cache strategy updated to use Docker volumes instead of host filesystem.
- License handling redesigned for ephemeral containers.
- All workflows use `ubuntu-latest` runners.
- Security model updated for container isolation.

### Migration Guide

1. Update workflow references: `@v1` → `@v2`
2. Remove `executor-mode`, `use-docker`, `native-runner` inputs from caller workflows.
3. Remove iOS and Windows build jobs (use dedicated non-Docker pipelines).
4. Ensure runners have Docker Engine available.
5. Update `UNITY_LICENSE` secret to contain the `.ulf` file content.
6. See [docs/ADD_NEW_PROJECT.md](docs/ADD_NEW_PROJECT.md) for the updated integration guide.

---

## [1.0.0] — 2024-06-12

### Added

#### Core Platform
- Reusable workflow `android.yml` — Android APK and AAB builds with debug and custom keystore signing, IL2CPP and Mono backends, configurable SDK versions and architectures.
- Reusable workflow `ios.yml` — Unity → Xcode project generation → IPA export pipeline with manual and automatic signing, App Store Connect upload via API key.
- Reusable workflow `windows.yml` — Windows Standalone x86_64 and x86 builds with IL2CPP (MSVC) and Mono support, optional output compression.
- Reusable workflow `webgl.yml` — WebGL builds with Brotli, Gzip, and Disabled compression formats; configurable memory size and HTML template.
- Reusable workflow `test.yml` — Unity Test Runner (EditMode and PlayMode) as a standalone workflow step.
- Reusable workflow `release.yml` — Tag-triggered production build and promotion pipeline with environment gating.

#### Configuration
- `schemas/unity-build-config.schema.json` — JSON Schema (Draft-07) validating the full BuildConfig object.
- Template BuildConfig files for base, development, staging, and production environments.

#### Unity Package
- `unity-package/com.company.build-pipeline/` — Unity Editor package with BuildCommand, validation rules, platform builders, and build hooks.

#### Documentation
- Complete documentation suite covering architecture, onboarding, platform guides, security, and troubleshooting.

---

[Unreleased]: https://github.com/BuzzelStudio/unity-build-workflows/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/BuzzelStudio/unity-build-workflows/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/BuzzelStudio/unity-build-workflows/releases/tag/v1.0.0
