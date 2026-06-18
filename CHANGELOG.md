# Changelog

All notable changes to `unity-build-workflows` are documented here.

This project adheres to [Semantic Versioning](https://semver.org/) and [Conventional Commits](https://www.conventionalcommits.org/).

The public API is the set of reusable workflow inputs/outputs documented in [docs/BUILD_CONFIG.md](docs/BUILD_CONFIG.md). Changes to that interface that require consumer updates are marked as **BREAKING**.

---

## [Unreleased]

---

## [2.1.0] — 2026-06-18

This release adds production iOS support via a dedicated macOS executor lane.
iOS was previously unsupported (Docker-only platform). It is now a first-class
build target via the `macos-unity-xcode` executor.

**Semver guidance:** This is a **minor** (feature) release. The workflow input
interface gains a new reusable workflow (`unity-build-ios.yml`) and new
BuildConfig `ios` fields, but the existing Docker-lane interface is unchanged.
Consumer repositories targeting Android/WebGL/Linux do not need to update.

### Added

#### iOS Pipeline
- `unity-build-ios.yml` — Reusable workflow for the full iOS pipeline:
  Unity → Xcode project generation → archive → IPA export → (optional) TestFlight upload.
- `scripts/ios/build_ios.sh` — Unity batch-mode iOS build (Xcode project generation).
- `scripts/ios/setup_signing.sh` — Temp keychain creation, certificate import, provisioning profile install, ASC key write.
- `scripts/ios/archive_ios.sh` — `xcodebuild archive` with workspace/project auto-detection and scheme resolution.
- `scripts/ios/export_ios.sh` — `xcodebuild -exportArchive` with auto-generated `ExportOptions.plist`.
- `scripts/ios/upload_testflight.sh` — TestFlight upload via `xcrun altool` / `notarytool`.
- `scripts/ios/cleanup_ios.sh` — Unconditional cleanup: temp keychain, provisioning profile, ASC key file.
- `scripts/common/resolve_platform_executor.py` — Platform→executor resolver. iOS+macOS → `macos-unity-xcode`; Docker platforms+linux → `docker-unity`. Exits non-zero for cross-lane mismatches.

#### iOS BuildConfig Fields (new in `iOS` section)

> **Canonical key is `iOS`.** The lowercase alias `ios` is deprecated-but-accepted
> (schema `$refs` both to one definition). Use `iOS` in all new configs and templates.
- `marketingVersion` — CFBundleShortVersionString
- `sdkVersion` — `iphoneos` or `iphonesimulator`
- `architecture` — `ARM64` or `x86_64`
- `xcodeVersion` — pinned Xcode version
- `developmentTeamId` — 10-char Apple Team ID
- `signingStyle` — `manual` or `automatic`
- `provisioningProfileSpecifier` — profile name for manual signing
- `codeSignIdentity` — signing identity string
- `enableBitcode` — boolean (default false)
- `generateSymbols` — boolean (default true)
- `uploadSymbols` — boolean (default false)
- `uploadToTestFlight` — boolean (default false)

#### Tests
- `tests/test_ios_build_config.py` — iOS BuildConfig schema validation (valid, invalid bundle IDs, enums, contract fields).
- `tests/test_ios_executor_resolution.py` — Platform→executor resolution, iOS-on-Linux rejection, Docker-on-macOS rejection.
- `tests/test_ios_shell_scripts.py` — Shell script tests: archive/export success/failure, secret redaction, cleanup, artifact contract, missing IPA/archive, TestFlight rejection, fork rejection, Unity failure simulations.
- `tests/fixtures/valid_ios_config.json` — Full iOS config fixture.
- `tests/fixtures/valid_ios_minimal.json` — Minimal iOS config fixture.
- `tests/fixtures/invalid_ios_bundle_id.json` — Invalid bundle ID fixture.
- `tests/fixtures/fake_xcodebuild.sh` — Fake xcodebuild for macOS-free testing.

#### Documentation
- `docs/IOS.md` — Full iOS pipeline guide.
- `docs/IOS_SIGNING.md` — Certificate, provisioning profile, and ASC key setup.
- `docs/IOS_RELEASE.md` — Release workflow, GitHub Environment, versioning, TestFlight.

### Changed
- `docs/PLATFORM_LIMITATIONS.md` — iOS section rewritten from "unsupported" to "supported via macOS". Windows remains unsupported.
- `docs/ARCHITECTURE.md` — Added `macos-unity-xcode` executor lane alongside `docker-unity`. Added iOS to supported platforms table.
- `docs/BUILD_CONFIG.md` — `ios` object section fully documented with all contract fields.
- `docs/SECURITY.md` — Added iOS secret inventory, temp credential lifecycle, macOS-specific guidance, and updated rotation policy table.
- `docs/TROUBLESHOOTING.md` — Added iOS section: cert errors, Xcode migration, TestFlight issues, profile expiry, cert rotation.
- `README.md` — Added iOS integration example, iOS secrets reference, updated platform table and documentation index.

### Migration from v2.0.0

Existing Android/WebGL/Linux workflows are **unaffected**. iOS migration:

1. Add the `ios` BuildConfig block to your `base.json` (see [docs/IOS.md](docs/IOS.md))
2. Add iOS GitHub Secrets (see [docs/IOS_SIGNING.md](docs/IOS_SIGNING.md))
3. Create a caller workflow using `unity-build-ios.yml@v2`
4. For releases: create a `production` GitHub Environment (see [docs/IOS_RELEASE.md](docs/IOS_RELEASE.md))
5. If you previously redirected users away from iOS using `docs/PLATFORM_LIMITATIONS.md`, update any internal documentation pointing to that "unsupported" section.

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

[Unreleased]: https://github.com/BuzzelStudio/unity-build-workflows/compare/v2.1.0...HEAD
[2.1.0]: https://github.com/BuzzelStudio/unity-build-workflows/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/BuzzelStudio/unity-build-workflows/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/BuzzelStudio/unity-build-workflows/releases/tag/v1.0.0
