# Platform Matrix

> **Canonical source.** Every doc that references platform support, runner labels,
> or Docker requirements MUST link here rather than duplicating this table.
> Update this file first; update downstream references second.

---

## Supported Build Targets

| Platform | Docker image variant | CI runner label | Docker required | Status |
|---|---|---|---|---|
| Android | `android` | `ubuntu-latest` | **Yes** | ✅ Supported |
| WebGL | `webgl` | `ubuntu-latest` | **Yes** | ✅ Supported |
| Linux64 | `linux` | `ubuntu-latest` | **Yes** | ✅ Supported |
| LinuxServer | `linux` | `ubuntu-latest` | **Yes** | ✅ Supported |
| iOS (build) | — native — | `macos-unity-xcode` ¹ | No — native macOS | ✅ Supported (self-hosted) |
| iOS (release) | — native — | `macos-unity-xcode` ¹ | No — native macOS | ✅ Supported (self-hosted) |
| Windows64 | — | — | — | ❌ Unsupported ² |

### Footnotes

**¹ iOS runner label** — the default label `macos-unity-xcode` is a self-hosted
runner registered to the consumer's GitHub organisation.  The consumer may
override it by setting the `ios-runner-label` workflow input to any label that
maps to a macOS machine with Xcode and Unity iOS Build Support installed.

GitHub-hosted macOS runners (`macos-latest`, `macos-14`) are **NOT claimed as
supported** unless the consumer independently validates the full build + sign +
export pipeline.  This toolkit does not pre-install Unity or Xcode on
GitHub-hosted runners.

**² Windows64** — Windows builds require either Windows Docker containers on a
Windows Docker host or a Windows-native runner with Unity Windows Build Support.
Neither path has been validated in this toolkit.  Invocations with
`--target-platform Windows64` are rejected at runtime with a clear error message.

---

## Invariants

| Rule | Rationale |
|---|---|
| Android MUST use Docker on Linux — never native | Reproducibility, cost, ADR-001 |
| iOS MUST use native macOS — never Linux Docker | Xcode/Apple-signing toolchain; ADR-002 |
| iOS MUST NOT run on Linux runners | `docker/unity/run_unity_container.py` explicitly rejects `iOS` |
| Release builds MUST use digest-pinned image references | Immutability guarantee; ADR-003 Decision 3 |
| Windows64 MUST NOT be advertised as supported | Not validated; would produce silent failures |

---

## iOS Runner Strategies

| Strategy | Label example | Maintainer burden | Cost model | Status |
|---|---|---|---|---|
| Self-hosted persistent macOS machine | `macos-unity-xcode` | High (OS / Xcode updates) | Fixed infrastructure | **Supported** |
| Self-hosted ephemeral macOS VM (Tart / Cirrus) | consumer-defined | Medium | Per-build VM spin-up | **Supported** — consumer's responsibility |
| GitHub-hosted macOS runner | `macos-latest` | Low | Per-minute billing | **NOT claimed** — requires consumer validation |

---

## Image Reference Format

For Docker-supported platforms, the full image reference takes the form:

```
<image-registry>/<image-namespace>/unity-builder:<unity-version>-<variant>[@<image-digest>]
```

| Component | Workflow input | Default | Required |
|---|---|---|---|
| `image-registry` | `image-registry` | `ghcr.io` | No |
| `image-namespace` | `image-namespace` | — | **Yes** |
| `unity-builder` | (fixed) | `unity-builder` | — |
| `unity-version` | `unity-version` | — | **Yes** |
| `variant` | derived from `target-platform` | — | — |
| `image-digest` | `image-digest` | — | **Yes in release-mode** |

---

## Related Documents

- [ADR-001: Docker-Mandatory Unity Build Architecture](adr/001-docker-mandatory-architecture.md)
- [ADR-002: iOS Native Executor Exception](adr/002-ios-native-exception.md)
- [ADR-003: Generic Consumer Integration](adr/003-generic-consumer-integration.md)
- [SELF_HOSTED_RUNNER.md](SELF_HOSTED_RUNNER.md)
- [IOS.md](IOS.md)
- [ANDROID.md](ANDROID.md)
