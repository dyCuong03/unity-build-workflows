# Architecture

`unity-build-workflows` is a Docker-mandatory CI/CD platform for Unity games. All Unity operations run inside pinned, versioned Docker containers. The CI runner is an orchestrator only.

---

## Layer Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  Consumer Repository (.github/workflows/build.yml)               │
│  • calls reusable workflows via uses: BuzzelStudio/unity-build-  │
│    workflows/.github/workflows/<workflow>.yml@v2                 │
│  • provides BuildConfig JSON + GitHub secrets                    │
└───────────────────────────┬──────────────────────────────────────┘
                            │ workflow_call
┌───────────────────────────▼──────────────────────────────────────┐
│  Workflow Layer  (.github/workflows/)                             │
│  • unity-build.yml (main orchestrator)                           │
│  • unity-build-android.yml, unity-build-webgl.yml,               │
│    unity-build-linux.yml                                         │
│  • unity-test.yml, unity-validate.yml                            │
│  • unity-release.yml, unity-nightly.yml                          │
│  • build-unity-image.yml, scan-unity-image.yml                   │
└───────────────────────────┬──────────────────────────────────────┘
                            │ uses: ./.github/actions/<name>
┌───────────────────────────▼──────────────────────────────────────┐
│  Composite Action Layer  (.github/actions/)                      │
│  • resolve-unity-image/  — target → image resolution            │
│  • run-unity-container/  — Docker container execution            │
│  • restore-docker-cache/ — Library cache volumes                 │
│  • collect-container-output/ — logs, reports, artifacts          │
│  • upload-build-report/  — build report upload                  │
└───────────────────────────┬──────────────────────────────────────┘
                            │ executes
┌───────────────────────────▼──────────────────────────────────────┐
│  Docker Layer                                                     │
│  • scripts/docker/run_unity_container.py  — Docker wrapper       │
│  • scripts/docker/resolve_image_reference.py — image resolution  │
│  • docker/unity/entrypoint.sh  — container entrypoint            │
│  • docker/unity/activate-license.sh — license activation         │
└───────────────────────────┬──────────────────────────────────────┘
                            │ invokes
┌───────────────────────────▼──────────────────────────────────────┐
│  Unity Layer (inside container)                                   │
│  • Unity Editor -batchmode -executeMethod                        │
│    Company.BuildPipeline.BuildCommand.Execute                    │
│  • BuildConfigurationLoader → BuildValidator → PlatformBuilder   │
│  • Reports and artifacts written to bind-mounted directories     │
└───────────────────────────┬──────────────────────────────────────┘
                            │ reads
┌───────────────────────────▼──────────────────────────────────────┐
│  Config Layer                                                     │
│  • BuildConfig.*.json   — per-environment build configuration    │
│  • schema validation    — JSON Schema v7 enforced at CI entry    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Execution Flow

```
CI Runner (ubuntu-latest)
  │
  ├── 1. Checkout project
  ├── 2. Resolve Unity image (resolve-unity-image action)
  │       └── Maps target-platform → image variant → digest-pinned reference
  ├── 3. Restore Docker cache volumes (restore-docker-cache action)
  ├── 4. Run Unity in container (run-unity-container action)
  │       └── docker run --rm --init --user $(id -u):$(id -g)
  │             └── entrypoint.sh build --target-platform Android ...
  │                   └── activate-license.sh
  │                   └── Unity -batchmode -executeMethod BuildCommand.Execute
  │                   └── copy Editor.log to Logs/
  │                   └── return-license.sh
  │                   └── cleanup trap
  ├── 5. Collect container output (collect-container-output action)
  │       └── Gather logs, reports, test results from bind mounts
  ├── 6. Upload artifacts and reports
  └── 7. Post-build steps (signing, deployment) on host
```

---

## Docker Image Strategy

Images extend pinned GameCI base images with an organizational tooling layer:

```
unityci/editor:6000.0.26f1-android-3  (GameCI base, pinned)
  └─ ghcr.io/buzzelstudio/unity-builder:6000.0.26f1-android-v2.0.0
       └─ entrypoint.sh, license scripts, healthcheck, python3, jq
```

See [IMAGE_LIFECYCLE.md](IMAGE_LIFECYCLE.md) for full image strategy.

---

## Supported Platforms

| Platform | Image Variant | Docker Support |
|---|---|---|
| Android | `android` | Full — cross-compilation via Android SDK/NDK |
| WebGL | `webgl` | Full — cross-compilation via Emscripten |
| Linux64 | `linux` | Full — native compilation |
| LinuxServer | `linux` | Full — native compilation |
| iOS | — | **Unsupported** — requires macOS + Xcode |
| Windows64 | — | **Unsupported** — requires Windows containers |

See [PLATFORM_LIMITATIONS.md](PLATFORM_LIMITATIONS.md).

---

## Unity Package Layer

The `unity-package/` directory contains a Unity Editor package (`com.company.build-pipeline`) providing:

- **BuildCommand.Execute** — C# entry point invoked via `-executeMethod`
- **BuildConfigurationLoader** — Loads and merges BuildConfig JSON
- **BuildValidator** — Runs validation rules before build
- **PlatformBuilders** — Platform-specific build logic (Android, WebGL, Linux)
- **BuildHookRegistry** — Lifecycle hooks (BeforeValidation, BeforeBuild, AfterBuild)
- **BuildReportExporter** — Exports build reports to JSON/Markdown

Docker changes only the execution environment. All build logic stays in typed C# code.

---

## Config Layer

BuildConfig files follow a layered merge pattern:

```
base.json  ←  environment.json  →  merged config (validated)  →  passed to container
```

The merged config is validated against `schemas/unity-build-config.schema.json` before any build steps run.

---

## Extension Points

### Lifecycle Hooks

Implement `IBuildHook` in the Unity package. Hooks run inside the container at:
- BeforeValidation
- BeforeBuild
- AfterBuild

### Custom Validation Rules

Implement `IBuildValidationRule` and register in the build pipeline.

### Custom Platform Builders

Implement `IPlatformBuilder` for additional build targets.

---

## Error Handling

| Failure Type | Behavior |
|---|---|
| Unsupported platform | Fails before Docker invocation with actionable error |
| Image not found | Fails with registry/version guidance |
| Schema validation failure | Pipeline fails immediately with field path |
| Unity license failure | Container preserves activation log; pipeline fails |
| Unity build failure | Editor.log + reports persisted via bind mounts; pipeline fails |
| Missing expected artifact | Wrapper fails even if Unity exits 0 |
| Container OOM/timeout | Exit code 137 propagated; logs preserved if possible |

All cleanup steps use `if: always()` to ensure license return and temp file deletion.

---

## Security Model

See [SECURITY.md](SECURITY.md) for the full security documentation.

Key principles:
- Containers run non-privileged with `--cap-drop=ALL`
- No Docker socket mount in build containers
- Secrets injected at runtime, never in image layers
- Production builds use digest-pinned images
- Image security scanning before publication
