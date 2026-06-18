# ADR-003: Generic Consumer Integration

**Status:** Accepted
**Date:** 2026-06-18
**Decision Makers:** Platform Architecture
**Branch:** `feature/generic-consumer-integration`

---

## Context

`unity-build-workflows` was originally developed against a single internal project
("Backpack Adventures" / BuzzelStudio).  As it matures into a shared toolkit,
every game-specific assumption becomes a barrier for outside consumers.

This ADR governs the full genericisation effort.  It establishes:

1. A formal migration map for every hard-coded identifier class found in the
   seeded audit.
2. Five architectural decisions that implementation engineers must follow exactly.
3. A generic placeholder convention that all documentation and fixture files must
   adopt.

Implementation engineers MUST NOT deviate from the rulings below without a
superseding ADR approved by the platform architect.

---

## Section 1 — Formal Migration Map

Each row covers one **identifier class**.  Engineers fix the **current value** to
the **generic replacement** drawing the value from the **configuration source**.

| # | Identifier class | Current value | Generic replacement | Configuration source | Affected files (representative) | Compatibility impact | Test coverage required |
|---|---|---|---|---|---|---|---|
| 1 | Default Docker registry + namespace | `ghcr.io/buzzell-studio` (combined string) | `ghcr.io/OWNER` split into two inputs: `image-registry=ghcr.io`, `image-namespace=<required>` | Workflow input `image-namespace` (required, no default) + `image-registry` (default `ghcr.io`) | `scripts/docker/run_unity_container.py:41`, `resolve_image_reference.py:286`, `build_unity_image.py:295` | **Breaking** — callers that did not pass `--registry` previously relied on the hard-coded default; they must now supply `--image-namespace` | `test_image_resolution.py` must assert `ValueError` when `image-namespace` absent |
| 2 | OCI vendor label | `BuzzelStudio` in `build_unity_image.py:106` | `<WORKFLOW_OWNER>` resolved at image-build time from `--image-namespace` (strip trailing path segment) or explicit `--oci-vendor` flag | `--oci-vendor` CLI flag or derived from `image-namespace` | `build_unity_image.py:106` | Non-breaking for consumers; image label only | Snapshot test comparing generated `LABEL` args |
| 3 | Vendor comments in entrypoint | `BuzzelStudio` in `docker/unity/*.sh` comments | Neutral comment referencing the toolkit, e.g. `# unity-build-workflows entrypoint` | N/A (static text) | `docker/unity/entrypoint.sh`, `docker/unity/healthcheck.sh` | None (comments only) | No new test required; existing shell-script tests pass |
| 4 | Non-existent release tag refs | `@v2` / `@v1.2.0` in `templates/project-workflow.yml`, `examples/.../unity-ci.yml` | `@<WORKFLOW_REF>` placeholder, with the canonical working ref being a SHA or the branch `main` until a real semver tag is published | Documented in `README.md` + templates as a mandatory fill-in | `templates/project-workflow.yml` (3 `uses:` lines), `examples/.../unity-ci.yml:29`, `examples/.../README.md:53` | **Breaking illusion** — `@v2` never existed; replacing with `@<WORKFLOW_REF>` makes the obligation explicit without claiming a non-existent tag | `test_workflow_contract.py` must assert no literal `@v1`/`@v2`/`@v1.x.x` strings remain in templates or examples |
| 5 | Game name in test fixtures | `Backpack Adventures` / `backpack-adventures` in `valid_base_config.json`, `valid_production_config.json`, `invalid_*.json`, `build_metadata_sample.json`, `test_build_metadata.py:39` | `ExampleProject` / `example-project` | Static fixture values | `tests/fixtures/valid_base_config.json`, `valid_production_config.json`, `invalid_empty_scenes.json`, `invalid_bundle_id.json`, `invalid_production_dev_build.json`, `build_metadata_sample.json`; `test_build_metadata.py` | None — tests exercise schema logic, not game name | Existing tests must still pass after rename |
| 6 | Company name in test fixtures | `BuzzelStudio` in fixture `companyName` fields | `ExampleCompany` | Static fixture values | Same files as row 5 | None | Same as row 5 |
| 7 | Android application ID in test fixtures | `com.buzzellstudio.backpackadventures` | `com.example.project` | Static fixture values | `valid_base_config.json`, `valid_production_config.json`, `invalid_bundle_id.json` | None — schema regex tests must still pass | `test_build_config.py` bundle-ID pattern tests |
| 8 | iOS bundle identifier in test fixtures / unit test | `com.buzzellstudio.myiosgame`, `com.buzzellstudio.mygame` | `com.example.game` | Static fixture values + `test_ios_build_config.py:92` | `tests/fixtures/valid_ios_config.json`, `test_ios_build_config.py` | None | `test_ios_build_config.py` pattern tests |
| 9 | Schema `$id` URL | `https://github.com/BuzzelStudio/unity-build-workflows/schemas/...` in `unity-build-config.schema.json:3`, `unity-image-manifest.schema.json` (`docker/metadata/image-manifest.schema.json`) | `https://github.com/<WORKFLOW_OWNER>/unity-build-workflows/schemas/...` — document that consumers must substitute `<WORKFLOW_OWNER>` when forking; the shipped default uses the placeholder literal | Static file | `schemas/unity-build-config.schema.json`, `schemas/unity-image-manifest.schema.json`, `docker/metadata/image-manifest.schema.json` | Non-breaking for schema validators (URI is informational only in Draft-07) | `test_image_manifest.py` must assert `$id` does not contain `BuzzelStudio` |
| 10 | UPM package identity | `com.company.build-pipeline` / `Company.BuildPipeline.Editor.BuildCommand.Execute` across 45 files | **KEEP** — see Decision 2 | N/A | All `unity-package/` C# files, `scripts/ios/run_unity_ios.sh:44`, `docker/unity/entrypoint.sh:37` | None | No change |

---

## Decision 1 — Repository / release-ref identity

### Ruling

Template and example files MUST NOT reference a specific GitHub organisation name
or a version tag that does not exist in the repository.

**Required change to `templates/project-workflow.yml` and `examples/`:**

```yaml
# Replace:
uses: BuzzelStudio/unity-build-workflows/.github/workflows/unity-build.yml@v2

# With:
uses: <WORKFLOW_OWNER>/unity-build-workflows/.github/workflows/unity-build.yml@<WORKFLOW_REF>
```

`<WORKFLOW_OWNER>` is the GitHub user or organisation that hosts the fork/clone
of this toolkit.  `<WORKFLOW_REF>` is a commit SHA, a branch name, or a semver tag
**that actually exists** in that repository.

**Tagging policy:** No `@v2` tag exists.  Until a release process is established
and a real tag is published, templates MUST use a SHA or `main` as the example
ref and clearly comment that the consumer must substitute their own.

This is a documentation-only fix — no workflow YAML semantics change.

---

## Decision 2 — Package identity (UPM + C# namespace)

### Ruling: **KEEP `com.company.build-pipeline` and `Company.BuildPipeline.Editor.BuildCommand.Execute`**

**Rationale:**

1. `Company` and `company` are universally recognised as placeholder identifiers
   in software toolkits.  Unlike `BuzzelStudio`, they carry no organisational claim.
2. Renaming 45 files across C# namespaces, `package.json`, shell scripts, and
   workflow YAML would be a breaking change for any consumer that has already
   pinned the `-executeMethod` flag in their Unity project or CI config.
3. The Unity `-executeMethod` argument is a string that consumers copy verbatim;
   changing it silently breaks builds with no compiler warning.
4. A compatibility shim (a C# `[Obsolete]` forwarding class under an old namespace)
   would add permanent dead-weight to the package.

**Published contract:**

| Identifier | Stable value | Status |
|---|---|---|
| UPM package name | `com.company.build-pipeline` | **Stable — do not rename** |
| C# namespace root | `Company.BuildPipeline.Editor` | **Stable — do not rename** |
| Unity `-executeMethod` | `Company.BuildPipeline.Editor.BuildCommand.Execute` | **Stable — do not rename** |

Consumers are expected to copy the exact `-executeMethod` string.  The `Company`
prefix is a deliberate, neutral placeholder — not the name of any real organisation.

**Implementation action:** `unity-package-engineer` must add a comment block to
`package.json` and `BuildCommand.cs` explaining that `Company` is a stable
placeholder, not an organisational name, so future maintainers do not attempt to
rename it.

---

## Decision 3 — Registry / image-identity contract

### Definitions

| Concept | Definition | Example |
|---|---|---|
| `workflow-repository` | The GitHub repository hosting this toolkit | `github.com/<WORKFLOW_OWNER>/unity-build-workflows` |
| `workflow-ref` | The exact git ref (SHA, branch, or tag) of the toolkit being used | `a1b2c3d` or `main` |
| `image-registry` | OCI registry host | `ghcr.io` |
| `image-namespace` | Organisation or user path within the registry | `my-org` |
| `image-name` | Repository name within the namespace | `unity-builder` |
| `image-digest` | Immutable content-addressed digest | `sha256:abc123…` |
| `image-variant` | Build-module variant of the image | `android`, `webgl`, `linux` |

Full image reference pattern:
```
<image-registry>/<image-namespace>/<image-name>:<tag>@<image-digest>
```

### Rules

1. **`image-registry`** — workflow input, default `ghcr.io`.  Consumers may
   override to use a private registry mirror.
2. **`image-namespace`** — workflow input, **required, no default**.  Scripts
   MUST raise a clear error (`ValueError`) if this is absent.  The previous
   `ghcr.io/buzzell-studio` hard-code is removed entirely.
3. **`image-name`** — derived from variant, default pattern `unity-builder`.
   Not a user input.
4. **Release builds** — when `release-mode: true`, `image-digest` is
   **required** and must match the pattern `^sha256:[0-9a-f]{64}$`.
   A mutable tag alone (`:latest`, `:2022.3.21f1-android`) is rejected.
   This ensures production builds are bit-for-bit reproducible and cannot be
   silently overwritten by a registry push.
5. **Development builds** — mutable tag references are permitted.  A warning
   must be emitted when no digest is supplied.
6. **Image approval gate** — release-mode validation checks the image manifest's
   `contractVersion` field against the toolkit's expected version.  An image
   built by a different toolkit version must not pass the release gate without
   an explicit override flag (`--allow-contract-mismatch`), which is itself
   rejected in release mode.

### Migration

`scripts/docker/run_unity_container.py`, `resolve_image_reference.py`, and
`build_unity_image.py` must replace:

```python
DEFAULT_REGISTRY = "ghcr.io/buzzell-studio"
```

with separate constants and require `image-namespace` as an explicit parameter:

```python
DEFAULT_REGISTRY_HOST = "ghcr.io"
# No default namespace — callers must supply --image-namespace
```

The `--registry` CLI flag (currently accepting the combined host+namespace
`ghcr.io/buzzell-studio`) is split into:

- `--image-registry` (optional, default `ghcr.io`)
- `--image-namespace` (required)

This is a **breaking CLI change**.  The affected scripts must bump their usage
doc version comment.  The GitHub Actions workflow YAML must be updated to pass
both arguments explicitly.

---

## Decision 4 — Cross-repo toolkit-checkout contract

### Problem

A consumer calls:

```yaml
uses: <WORKFLOW_OWNER>/unity-build-workflows/.github/workflows/unity-build.yml@<WORKFLOW_REF>
```

GitHub Actions runs the reusable workflow's steps on a runner where
`actions/checkout@v4` (inside the reusable workflow) checks out the **caller's**
repository into `$GITHUB_WORKSPACE`.  After that checkout, paths like
`scripts/docker/run_unity_container.py`, `schemas/`, and
`.github/actions/upload-build-report` do **not exist** — they live in the
toolkit repo, not the consumer repo.

The pattern `uses: ./.github/actions/...` inside a reusable workflow resolves
relative to the **called** (toolkit) repo, so composite actions are safe.
However, `run:` shell commands that invoke `python3 scripts/...` operate on the
runner filesystem and will fail if the scripts are not physically present.

### Authoritative design

```
Runner workspace after setup step
├── project/                    ← consumer repo (Unity project root)
│   ├── Assets/
│   ├── Packages/
│   ├── BuildConfig/
│   └── .github/workflows/      ← consumer workflows (callers only)
└── .ci/
    └── unity-build-workflows/  ← EXACT toolkit revision (read-only)
        ├── scripts/
        ├── schemas/
        ├── docker/
        └── .github/
            ├── workflows/      ← reusable workflows (called, not copied)
            └── actions/        ← composite actions
```

**Checkout sequence (inside the reusable workflow):**

```yaml
- name: Checkout consumer project
  uses: actions/checkout@v4
  with:
    path: project

- name: Checkout toolkit at exact workflow-ref
  uses: actions/checkout@v4
  with:
    repository: ${{ github.action_repository }}   # toolkit repo
    ref: ${{ github.action_ref }}                 # exact SHA/ref used in `uses:`
    path: .ci/unity-build-workflows
    token: ${{ secrets.GITHUB_TOKEN }}
```

All subsequent `run:` steps invoke scripts as:

```bash
python3 .ci/unity-build-workflows/scripts/docker/run_unity_container.py \
  --project-path project \
  ...
```

Outputs (artifacts, build reports, logs) are written to paths under the runner
workspace root (e.g., `artifacts/`, `logs/`) — **never** inside
`.ci/unity-build-workflows/` (toolkit must remain pristine) and **never** inside
`project/Assets/` or `project/Packages/` (Unity project must remain pristine).

**Composite actions** continue to use `uses: ./.github/actions/<name>` which
GitHub resolves correctly to the called repo.

### GitHub Actions constraints (reusable-workflow-engineer must prove with tests)

| Constraint | Notes |
|---|---|
| `uses: ./.github/workflows/...` inside a reusable workflow is allowed | GitHub resolves relative paths to the called repo, not the caller |
| `github.action_repository` and `github.action_ref` are available inside reusable workflows | Confirmed in GitHub docs; engineer must add a test job that asserts these are non-empty |
| A reusable workflow may call another reusable workflow (one level deep) | GitHub allows nesting; second-level `uses:` must be absolute, not local `./.github/...` if the sub-workflow is in a different repo |
| `path:` in `actions/checkout@v4` is relative to `$GITHUB_WORKSPACE` | Must never be an absolute path |

**Risk flag:** If `github.action_ref` resolves to a branch name rather than a
SHA when the consumer pins a branch, successive runs may pick up different toolkit
code without the consumer changing their workflow.  Consumers SHOULD pin to a SHA
in production.  Documentation must warn of this.

---

## Decision 5 — Runner contract

See also: `docs/PLATFORM_MATRIX.md` (the single canonical source).

| Platform | Runner label | Docker required | Notes |
|---|---|---|---|
| Android | `ubuntu-latest` | Yes — Linux Docker | Default runner; never native |
| WebGL | `ubuntu-latest` | Yes — Linux Docker | Default runner; never native |
| Linux64 / LinuxServer | `ubuntu-latest` | Yes — Linux Docker | Default runner; never native |
| iOS (build) | `ios-runner-label` input, default `macos-unity-xcode` | No — native macOS | Must be macOS; must have Xcode + Unity iOS Build Support |
| iOS (release / TestFlight) | Same as iOS build | No — native macOS | Additional Apple credentials required |
| Windows64 | — | — | **Unsupported** — not claimed until native Windows CI is validated |

### Android invariant

Android MUST NEVER run natively on a CI runner.  Any attempt to invoke
`scripts/docker/run_unity_container.py` with `--target-platform Android` on a
runner without Docker must fail at container-launch time with a clear error.

### iOS runner label

The workflow input `ios-runner-label` (default: `macos-unity-xcode`) allows
consumers with self-hosted macOS runners to substitute their own label.
Two strategies are documented:

1. **Self-hosted macOS runner** (supported) — a persistent or ephemeral macOS
   machine registered to the consumer's GitHub organisation.  Full control over
   Xcode version, Unity modules, and Apple certificates.

2. **GitHub-hosted macOS runner** (NOT claimed unless tested) — `macos-latest`
   or `macos-14`.  Unity iOS Build Support and Xcode CLI toolchain are not
   pre-installed.  Consumers who want this path must install dependencies in a
   setup step and validate the full build + sign pipeline end-to-end.  This
   toolkit makes no promise that `macos-latest` produces a valid IPA without
   additional configuration.

### Windows64

Windows builds require a Windows Docker host or a Windows-native runner with
Unity Windows Build Support installed.  Neither path has been validated in this
toolkit.  `Windows64` is explicitly **not supported** and must be documented as
such in all platform matrices.  Any CI that calls `--target-platform Windows64`
will receive the error message from `DOCKER_UNSUPPORTED_PLATFORMS`.

---

## Section 6 — Generic placeholder convention

### Markdown / documentation

| Placeholder | Meaning | Example usage |
|---|---|---|
| `<PROJECT_NAME>` | Human-readable project name | `My Game` |
| `<COMPANY_NAME>` | Studio or organisation display name | `My Studio` |
| `<ANDROID_APPLICATION_ID>` | Android package name | `com.mystudio.mygame` |
| `<IOS_BUNDLE_IDENTIFIER>` | iOS bundle ID | `com.mystudio.mygame` |
| `<APPLE_TEAM_ID>` | Apple Developer Team ID | `ABCDE12345` |
| `<WORKFLOW_OWNER>` | GitHub user/org hosting the toolkit | `my-org` |
| `<IMAGE_NAMESPACE>` | OCI registry namespace | `my-org` |
| `<WORKFLOW_REF>` | Git ref for toolkit checkout | `a1b2c3d` or `main` |

Angle-bracket placeholders signal "fill this in" to the reader.  They MUST NOT
appear as literal values in any JSON file checked into the repository (JSON
parsers and validators will attempt to use them as real data).

### JSON fixtures and schema examples

| Field | Generic value | Prohibited values |
|---|---|---|
| `projectName` | `"example-project"` | any real game slug |
| `companyName` | `"ExampleCompany"` | `"BuzzelStudio"` or any real studio |
| `productName` | `"ExampleProject"` | `"Backpack Adventures"` or any real title |
| `android.applicationId` | `"com.example.project"` | `"com.buzzellstudio.*"` or any real ID |
| `ios.bundleIdentifier` | `"com.example.game"` | `"com.buzzellstudio.*"` or any real ID |
| `bundleVersion` | `"1.0.0"` | version strings tied to a real release |

The domain `example` (RFC 2606) is intentionally reserved and carries no trademark
risk.

---

## Assumptions

1. The repository will not be reorganised into a GitHub App or Action Marketplace
   listing before this ADR is implemented; the `uses: OWNER/REPO@REF` model holds.
2. `github.action_repository` and `github.action_ref` context values are available
   inside reusable workflows (to be verified by reusable-workflow-engineer).
3. Consumers are willing to supply `image-namespace` explicitly; there is no
   universally appropriate default namespace.
4. The seeded audit is complete — no additional hard-coded org identifiers exist
   beyond those listed in Section 1.

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| `--image-namespace` is now required; existing internal pipelines that relied on the `ghcr.io/buzzell-studio` default will break | High | Document migration in CHANGELOG; bump major version |
| `@v2` removal exposes that no semver tags exist | Medium | Add a note in README directing consumers to pin a SHA; establish a release tagging process |
| Cross-repo checkout adds ~30 s per job for the second `actions/checkout` | Low | Acceptable trade-off for correctness; can be cached via `actions/cache` in future |
| `github.action_ref` resolving to a mutable branch name in production | Medium | Warn in docs; recommend SHA pinning; block in release-mode if ref is not a SHA (future gate) |
| Renaming test fixtures could break tests that match on exact strings | Low | `qa-integration-engineer` runs full suite after `tests-engineer` updates fixtures |

---

## Consequences

- **Breaking:** `--registry` CLI flag is split into `--image-registry` + `--image-namespace` (required).
- **Breaking:** Templates/examples no longer reference a non-existent `@v2` tag.
- **Non-breaking:** Package identity (`com.company.build-pipeline`, `Company.BuildPipeline.Editor`) is preserved.
- **Non-breaking:** Test fixtures renamed to generic values; schema logic unchanged.
- **Additive:** Cross-repo toolkit-checkout pattern is now the documented, tested default.
- **Additive:** `PLATFORM_MATRIX.md` becomes the single canonical runner/platform reference.
