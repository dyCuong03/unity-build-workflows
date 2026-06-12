# Release Flow

This document describes the tag-based release process, protected environments, and build promotion gates in `unity-build-workflows`.

---

## Overview

Releases follow a trunk-based promotion model:

```
feature branch  →  develop (dev builds)  →  main (staging builds)  →  v* tag (production builds)
```

No environment skips are permitted — a commit must flow through staging before a production tag can be created from it.

---

## Branch and Tag Conventions

| Branch/Pattern | Triggers | Environment |
|---|---|---|
| Any branch | `push` to feature branch | development |
| `develop` | `push` to develop | development |
| `main` | `push` to main | staging |
| `v*` tag on `main` | Tag push | production |

Tags must follow `vMAJOR.MINOR.PATCH` (e.g., `v1.2.3`). The `bundleVersion` in `BuildConfig.production.json` must match the tag version.

---

## Creating a Release

### 1. Merge to main

All features for the release must be merged into `main` via pull request. Staging builds run automatically on merge.

### 2. Verify Staging Build

Wait for the staging workflow to complete successfully. Download and test the staging artifact. Confirm all quality gates pass.

### 3. Update BuildConfig Version

In `BuildConfig.base.json` (or `BuildConfig.production.json`), update:

```json
"bundleVersion": "1.2.3"
```

Commit and push to `main`. The staging build with the new version number should be the final candidate.

### 4. Create and Push the Release Tag

```bash
git checkout main
git pull
git tag v1.2.3 -m "Release 1.2.3: [brief description]"
git push origin v1.2.3
```

This triggers the production workflow.

### 5. Approve the Production Deployment

The production workflow pauses at the `production` environment gate, waiting for a required reviewer to approve. Navigate to **Actions → [workflow run] → Review deployments → Approve**.

### 6. Monitor Production Build

Once approved, the build runs with production secrets and strict quality gates. If any gate fails, the tag remains but the workflow fails — no artifact is distributed. Fix the issue, delete the tag, and re-tag from the corrected commit.

---

## GitHub Environments

### `staging`

| Setting | Value |
|---|---|
| Deployment branches | `main` only |
| Required reviewers | None (automatic) |
| Wait timer | None |
| Secrets | Staging keystores, staging provisioning profiles, Firebase tokens |

### `production`

| Setting | Value |
|---|---|
| Deployment branches | Tags matching `v*` |
| Required reviewers | At least 1 (team lead or release manager) |
| Wait timer | Optional (e.g., 10 minutes for last-minute abort) |
| Secrets | Production keystores, production provisioning profiles, App Store Connect keys |

Secrets scoped to an environment are only available when the environment's conditions are met. Fork pull requests and feature branches never access production secrets.

---

## Quality Gates at Release

Production builds enforce stricter gates than development/staging:

```json
"gates": {
  "maxBuildSizeMB": 500,
  "warnBuildSizeIncreasePct": 5,
  "failBuildSizeIncreasePct": 15,
  "failOnWarnings": true,
  "requiredValidationRules": [
    "no_missing_references",
    "no_missing_scripts",
    "no_missing_prefabs",
    "addressables_content_hash_stable",
    "bundle_identifier_matches_config"
  ]
}
```

Any gate violation aborts the build before signing. The build artifact is not uploaded in a failed state.

---

## Build Number at Release

For release builds with `buildNumberStrategy: github_run_number`, the build number is the GitHub Actions run number. This is monotonically increasing and audit-traceable. For App Store submissions, the `ios.buildNumber` or Android version code is derived from this value.

If you need a specific build number for compliance or App Store Connect versioning, use `buildNumberStrategy: manual` and set `BUILD_NUMBER` as a workflow input.

---

## Rollback

If a released build has a critical defect:

1. Do not delete the version tag — it preserves the build history.
2. Create a hotfix branch from the release tag: `git checkout -b hotfix/1.2.4 v1.2.3`
3. Apply the fix, bump `bundleVersion` to `1.2.4`, and merge to `main`.
4. Tag `v1.2.4` and follow the normal release flow.

---

## Semantic Versioning

| Change Type | Version Bump | Example |
|---|---|---|
| Bug fix, balance change | PATCH | 1.2.3 → 1.2.4 |
| New feature, new content | MINOR | 1.2.3 → 1.3.0 |
| Breaking change (save format, API) | MAJOR | 1.2.3 → 2.0.0 |

The `@v1` floating tag on this repository (`unity-build-workflows`) points to the latest 1.x.x release and is what consumer repositories reference. A `@v2` would indicate breaking changes to the workflow interface.

---

## `@v1` Floating Tag Policy

The `unity-build-workflows` repository maintains floating major version tags:

- `v1` always points to the latest `v1.x.x` release
- Using `@v1` in consumer workflows means automatic minor/patch updates
- Breaking changes increment the major version to `v2`

To pin to an exact version (for reproducibility): `uses: BuzzelStudio/unity-build-workflows/.github/workflows/android.yml@v1.2.3`

To get latest non-breaking updates: `uses: BuzzelStudio/unity-build-workflows/.github/workflows/android.yml@v1`
