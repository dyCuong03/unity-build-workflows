# Architecture

`unity-build-workflows` is a reusable, layered CI/CD platform for Unity games. It is designed to be consumed as a GitHub Actions reusable workflow from any Unity project repository without duplicating pipeline code.

---

## Layer Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  Consumer Repository (.github/workflows/build.yml)               │
│  • calls reusable workflows via uses: BuzzelStudio/unity-build-   │
│    workflows/.github/workflows/<workflow>.yml@v1                  │
│  • provides BuildConfig JSON + GitHub secrets                     │
└───────────────────────────┬──────────────────────────────────────┘
                            │ workflow_call
┌───────────────────────────▼──────────────────────────────────────┐
│  Workflow Layer  (.github/workflows/)                             │
│  • android.yml, ios.yml, windows.yml, webgl.yml                  │
│  • test.yml (Unity Test Runner)                                   │
│  • release.yml (tag-triggered promotion gate)                     │
│  • Each workflow orchestrates jobs and calls composite actions    │
└───────────────────────────┬──────────────────────────────────────┘
                            │ uses: ./actions/<name>
┌───────────────────────────▼──────────────────────────────────────┐
│  Composite Action Layer  (actions/)                               │
│  • setup-unity/         — license activation, cache              │
│  • build-unity/         — invoke Unity CLI with correct flags     │
│  • sign-android/        — keystore inject + signing               │
│  • sign-ios/            — certificate/provisioning profile inject │
│  • run-gates/           — size checks, validation rules          │
│  • upload-artifact/     — normalized artifact naming + upload    │
└───────────────────────────┬──────────────────────────────────────┘
                            │ executes
┌───────────────────────────▼──────────────────────────────────────┐
│  Scripts Layer  (scripts/)                                        │
│  • build.sh             — entry-point shell wrapper              │
│  • validate-config.sh   — JSON Schema validation via ajv-cli     │
│  • run-tests.sh         — Unity EditMode + PlayMode test runner  │
│  • hooks/               — lifecycle hook scripts                 │
└───────────────────────────┬──────────────────────────────────────┘
                            │ reads
┌───────────────────────────▼──────────────────────────────────────┐
│  Config Layer                                                     │
│  • BuildConfig.*.json   — per-environment build configuration    │
│  • schema validation    — JSON Schema v7 enforced at CI entry    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Workflow Layer

Each platform has a dedicated reusable workflow file. All accept a common set of inputs:

| Input | Type | Description |
|---|---|---|
| `build-config` | string | JSON string of the merged BuildConfig object |
| `unity-version` | string | Unity version to use (e.g. `2022.3.45f1`) |
| `runner` | string | GitHub-hosted or self-hosted runner label |
| `artifact-retention-days` | number | Days to retain uploaded artifacts |

Workflows emit a `build-artifact-name` output so downstream jobs can download the artifact by name.

---

## Unity Package Layer

The optional `unity-package/` directory contains a Unity Editor package (`com.buzzellstudio.ci-tools`) that can be imported into the Unity project. It provides:

- **Editor build scripts** — C# methods invoked via `-executeMethod` in headless mode
- **Validation rules** — implementations of the `IValidationRule` interface, callable from CI
- **Build preprocessors** — `IPreprocessBuildWithReport` hooks for config injection at build time

The package is not required — the workflows function without it — but it enables advanced configuration injection (e.g., writing server URLs into `StreamingAssets` before build).

---

## Config Layer

BuildConfig files follow a layered merge pattern. The merge happens outside Unity, in the calling workflow, before the config is passed as a workflow input:

```
base.json  ←  environment.json  →  merged config (validated)  →  workflow input
```

Merge is a shallow JSON merge (environment values override base values). Arrays are replaced entirely, not concatenated.

The merged config is validated against `schemas/unity-build-config.schema.json` using `ajv-cli` before any build steps run. Validation failure aborts the pipeline immediately with a descriptive error.

---

## Extension Points

### Lifecycle Hooks

Hooks are shell scripts placed in `scripts/hooks/` in the **consumer repository**. They are identified by name in `BuildConfig.hooks.preBuild` and `hooks.postBuild`. The hook runner passes the following environment variables:

| Variable | Value |
|---|---|
| `BUILD_CONFIG_JSON` | The full merged BuildConfig as a JSON string |
| `BUILD_TARGET` | Platform being built (`Android`, `iOS`, `Windows`, `WebGL`) |
| `BUILD_OUTPUT_DIR` | Absolute path to the output directory |
| `GITHUB_SHA` | Current commit SHA |

### Custom Validation Rules

Implement `IValidationRule` from the CI tools package and add the rule identifier to `gates.requiredValidationRules`. The validation runner discovers rules by reflection.

### Custom Build Methods

Override the default `-executeMethod` by providing `com.yourcompany.ci.Build.Execute` in your Unity project. The method receives the BuildConfig via `Environment.GetEnvironmentVariable("BUILD_CONFIG_JSON")`.

---

## Error Handling

| Failure Type | Behaviour |
|---|---|
| Schema validation failure | Pipeline fails immediately, error logged with field path |
| Unity license activation failure | Pipeline fails with instructions to check secret format |
| Unity build failure (exit code != 0) | Build logs uploaded as artifact, pipeline fails |
| Gate violation (size exceeded) | Gate check job fails; build artifact still uploaded for inspection |
| Hook script exits non-zero | Pipeline fails; subsequent hooks in the same array are not run |
| Missing required secret | GitHub Actions masks and omits the value; script emits explicit error |

All jobs use `if: always()` on cleanup steps (license return, temp file deletion) to ensure licenses are released even on failure.

---

## Release Trust Boundary

Production builds are protected by GitHub Environments. The `production` environment requires:

1. At least one reviewer approval before deployment jobs run
2. Deployment branch limited to `main` (or tags matching `v*`)
3. Secrets scoped to the environment (not available to PR workflows)

Fork pull requests never have access to environment secrets. See [SECURITY.md](SECURITY.md) for the full threat model.
