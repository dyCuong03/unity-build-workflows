# Changelog

All notable changes to `unity-build-workflows` are documented here.

This project adheres to [Semantic Versioning](https://semver.org/) and [Conventional Commits](https://www.conventionalcommits.org/).

The public API is the set of reusable workflow inputs/outputs documented in [docs/BUILD_CONFIG.md](docs/BUILD_CONFIG.md). Changes to that interface that require consumer updates are marked as **BREAKING**.

---

## [Unreleased]

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
- `schemas/unity-build-config.schema.json` — JSON Schema (Draft-07) validating the full BuildConfig object including platform-specific sub-objects, quality gates, hooks, and metadata.
- `templates/BuildConfig.base.example.json` — Base configuration template showing all available fields.
- `templates/BuildConfig.development.example.json` — Development environment overrides (development build, debug signing, relaxed gates).
- `templates/BuildConfig.staging.example.json` — Staging environment overrides (release-like settings, internal distribution).
- `templates/BuildConfig.production.example.json` — Production environment overrides (strict gates, store distribution settings).
- `templates/build-secrets.example.md` — Complete secret reference with encoding instructions and rotation policy.

#### Scripts
- `scripts/build.sh` — Shell entry-point for local and CI builds.
- `scripts/build.ps1` — PowerShell entry-point for Windows local builds.
- `scripts/validate-config.sh` — JSON Schema validation script using `ajv-cli`.
- `scripts/run-tests.sh` — Unity Test Runner invocation with JUnit XML output.
- `scripts/hooks/` — Hook runner infrastructure for `preBuild` and `postBuild` lifecycle hooks.

#### Composite Actions
- `actions/setup-unity/` — Unity license activation with `.ulf` and serial activation modes; library cache integration.
- `actions/build-unity/` — Headless Unity build invocation with structured log capture.
- `actions/sign-android/` — Keystore decode, inject, sign; cleanup on exit.
- `actions/sign-ios/` — Certificate and provisioning profile keychain management; cleanup on exit.
- `actions/run-gates/` — Build size checks, percentage increase gate, validation rule runner.
- `actions/upload-artifact/` — Normalized artifact naming and upload with SHA-256 manifest.

#### Unity Package
- `unity-package/com.buzzellstudio.ci-tools/` — Optional Unity Editor package providing `IValidationRule` interface, `IBuildPreprocessor`, and C# build entry-point methods.

#### Documentation
- `README.md` — Overview, architecture diagram, minimal integration example, versioning policy.
- `docs/ARCHITECTURE.md` — Complete layer diagram, extension points, error handling.
- `docs/ADD_NEW_PROJECT.md` — Step-by-step onboarding guide.
- `docs/BUILD_CONFIG.md` — Full field reference.
- `docs/ANDROID.md` — Android signing, AAB/APK, SDK configuration.
- `docs/IOS.md` — iOS code signing, Xcode, App Store Connect.
- `docs/WINDOWS.md` — Windows standalone, IL2CPP, MSVC requirements.
- `docs/WEBGL.md` — WebGL compression, memory, hosting recommendations.
- `docs/RELEASE_FLOW.md` — Tag-based release process, environment gates.
- `docs/SELF_HOSTED_RUNNER.md` — Runner setup, Unity installation, security hardening.
- `docs/SECURITY.md` — Threat model, secret handling, fork safety.
- `docs/TROUBLESHOOTING.md` — Common errors and fixes.
- `CONTRIBUTING.md` — Contribution guidelines, code style, PR requirements.
- `LICENSE` — MIT license.

---

[Unreleased]: https://github.com/BuzzelStudio/unity-build-workflows/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/BuzzelStudio/unity-build-workflows/releases/tag/v1.0.0
