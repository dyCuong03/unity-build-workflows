# Platform Limitations

This repository uses a Docker-mandatory architecture. All Unity operations run inside Linux containers. This creates inherent limitations for certain platforms.

## Unsupported Platforms

### iOS

**Status:** Unsupported by this repository.

**Reason:** Unity iOS builds produce an Xcode project that requires macOS-native Xcode toolchain for:
- Code signing with Apple certificates
- Provisioning profile application
- IPA archive export (`xcodebuild -exportArchive`)
- App Store Connect upload

No verified Docker solution exists for the complete iOS build pipeline. Running Xcode inside a Linux container is not possible.

**Alternative:** Use a dedicated macOS-based CI pipeline:
- GitHub Actions `macos-latest` runner with native Unity installation
- Self-hosted macOS runner with Unity Hub
- Dedicated iOS build service (e.g., Codemagic, Bitrise)

**Error message when attempted:**
```
Target `iOS` is unsupported by the Docker-only build platform.
This repository does not permit native Unity execution.
Use the dedicated macOS release pipeline documented in
docs/PLATFORM_LIMITATIONS.md.
```

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

| Build Target | Container OS | Cross-Compilation |
|---|---|---|
| Android | Linux | Yes — Android SDK/NDK handles cross-compilation |
| WebGL | Linux | Yes — Emscripten handles cross-compilation |
| Linux64 | Linux | Native compilation |
| LinuxServer | Linux | Native compilation |
| iOS | Linux | **No** — requires Xcode on macOS |
| Windows64 | Linux | **No** — requires MSVC on Windows |

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
