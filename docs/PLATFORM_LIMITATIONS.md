# Platform Limitations

This repository operates two execution lanes:

- **`docker-unity`** — Docker-mandatory lane for Android, WebGL, and Linux builds. Runs on `ubuntu-latest`.
- **`macos-unity-xcode`** — Native macOS lane for iOS builds. Runs on `macos-13` or `macos-latest`.

The platform executor resolver (`scripts/common/resolve_platform_executor.py`) selects the correct lane automatically based on `target-platform`. Docker and macOS builds are **mutually exclusive** — each platform runs in exactly one lane.

## Supported Platforms

### iOS

**Status:** Supported via the `macos-unity-xcode` executor (macOS runner, native Xcode).

**Executor:** `macos-unity-xcode` — a macOS GitHub Actions runner with Unity and Xcode pre-installed.

**Why macOS is required:** Unity iOS builds produce an Xcode project that requires the macOS-native Xcode toolchain for:
- Code signing with Apple certificates (`security` + keychain)
- Provisioning profile installation
- IPA archive export (`xcodebuild archive`, `xcodebuild -exportArchive`)
- App Store Connect upload (`xcrun altool` / `notarytool`)

**Docker is not used for iOS.** Running Xcode inside a Linux container is not possible.

**How to use:** Add `target-platform: iOS` to your caller workflow. The resolver automatically selects the `macos-unity-xcode` executor.

**Attempting iOS on a Linux runner** produces:
```
ERROR: Platform 'iOS' requires executor 'macos-unity-xcode' (macOS runner).
Current runner-os is 'linux', which is incompatible.
Use a macOS runner: runs-on: macos-latest
```

**Full documentation:** [docs/IOS.md](IOS.md), [docs/IOS_SIGNING.md](IOS_SIGNING.md), [docs/IOS_RELEASE.md](IOS_RELEASE.md)

## Unsupported Platforms

### Windows

**Status:** Unsupported by this repository.

**Reason:** Unity Windows builds (Win64) require:
- Windows containers on Windows Docker hosts (not Linux containers)
- MSVC compiler for IL2CPP builds
- Windows-specific Unity modules

While Windows containers exist, they are not verified in our CI environment. We do not claim support without proof.

**Alternative:** Use a dedicated Windows-based CI pipeline:
- GitHub Actions `windows-latest` runner with native Unity installation
- Self-hosted Windows runner with Unity Hub

**Error message when attempted:**
```
Target `Windows64` is unsupported by the Docker-only build platform.
This repository does not permit native Unity execution.
Use the dedicated Windows pipeline documented in
docs/PLATFORM_LIMITATIONS.md.
```

## Platform-Specific Limitations

### Graphical PlayMode Tests

PlayMode tests that require a GPU or display server may not work in headless Linux containers. EditMode tests run without issues.

**Workaround:** Use `Xvfb` (X Virtual Framebuffer) if PlayMode tests require a display. The entrypoint supports this when the container includes Xvfb.

### GPU-Dependent Features

Unity features requiring GPU access (e.g., GPU skinning, compute shaders in editor) are unavailable in standard Docker containers.

**Impact:** Build-time shader compilation works (cross-compilation). Runtime GPU testing does not.

### Native Plugins

Native plugins (.so, .dll, .dylib) must be compatible with the container's Linux environment during the build phase. Platform-specific native plugins for the target platform (e.g., Android .so files) are included in the build output but not executed during the build.

### Cross-Compilation

| Build Target | Executor | Runner OS | Compilation |
|---|---|---|---|
| Android | `docker-unity` | Linux | Cross-compilation via Android SDK/NDK |
| WebGL | `docker-unity` | Linux | Cross-compilation via Emscripten |
| Linux64 | `docker-unity` | Linux | Native compilation |
| LinuxServer | `docker-unity` | Linux | Native compilation |
| iOS | `macos-unity-xcode` | macOS | Native — Xcode on macOS |
| Windows64 | — | — | **Unsupported** — requires Windows containers |

### Container Resource Limits

Unity builds are memory-intensive. Recommended minimums:

| Build Type | Memory | CPU |
|---|---|---|
| Android (IL2CPP) | 8 GB | 4 cores |
| WebGL | 8 GB | 4 cores |
| Linux (IL2CPP) | 6 GB | 4 cores |
| EditMode Tests | 4 GB | 2 cores |

Set limits via `--container-memory` and `--container-cpus` flags in `run_unity_container.py`.

### Android SDK/NDK Version Constraints

The Android image variant pins specific SDK and NDK versions. If your project requires different versions:

1. Update `docker/variants/android.Dockerfile`
2. Rebuild the image
3. Update the image manifest

Do not attempt to install SDK components at build time — this breaks reproducibility.
