# Release Flow

This document describes the tag-based release process for the Docker-mandatory Unity CI/CD platform.

---

## Overview

```
feature branch  →  develop (dev builds)  →  main (staging builds)  →  v* tag (production builds)
```

All builds run inside Docker containers. Production builds use digest-pinned images.

---

## Branch and Tag Conventions

| Branch/Pattern | Triggers | Environment | Image Requirement |
|---|---|---|---|
| Feature branch | `push` | development | Tagged image OK |
| `develop` | `push` | development | Tagged image OK |
| `main` | `push` | staging | Tagged image OK |
| `v*` tag on `main` | Tag push | production | **Digest-pinned image required** |

---

## Creating a Release

### 1. Merge to main

All features for the release merged via pull request. Staging builds run automatically.

### 2. Verify Staging Build

Wait for staging workflow to complete. Download and test the artifact.

### 3. Update BuildConfig Version

```json
"bundleVersion": "1.2.3"
```

### 4. Create Release Tag

```bash
git checkout main
git pull
git tag v1.2.3 -m "Release 1.2.3: [brief description]"
git push origin v1.2.3
```

### 5. Approve Production Deployment

Navigate to **Actions → [workflow run] → Review deployments → Approve**.

### 6. Monitor Production Build

Production build uses:
- Digest-pinned Docker image
- Clean build mode (no cache)
- Strict quality gates
- Protected GitHub Environment

---

## Production Build Requirements

| Requirement | Enforcement |
|---|---|
| Digest-pinned image | `resolve-unity-image` rejects mutable tags in release mode |
| Clean build | `clean-build: true` forces fresh Library import |
| Image scan passed | Image manifest records scan status |
| Strict gates | `failOnWarnings: true`, all validation rules |
| Environment approval | GitHub Environment requires reviewer |

---

## Build → Sign → Deploy Separation

```
Docker Container (Unity build)
  └─ Unsigned artifact
       └─ Host signing step (Android keystore / not in container)
            └─ Host deployment step (Google Play / Cloudflare)
```

Signing and deployment credentials are never inside the Unity container.

---

## Rollback

1. Do not delete the version tag
2. Create hotfix branch: `git checkout -b hotfix/1.2.4 v1.2.3`
3. Fix, bump version to `1.2.4`, merge to `main`
4. Tag `v1.2.4` and follow normal release flow

---

## Versioning

Consumer repositories reference the major version:

```yaml
uses: BuzzelStudio/unity-build-workflows/.github/workflows/unity-build.yml@v2
```

- `@v2` points to latest `2.x.x` release
- Breaking changes increment to `v3`
- Pin to exact version for reproducibility: `@v2.0.0`
