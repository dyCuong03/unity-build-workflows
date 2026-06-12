# Windows Builds

This document covers Windows Standalone build configuration for `unity-build-workflows`.

---

## Runner Requirements

Windows builds run on **Windows** runners. GitHub-hosted `windows-latest` works out of the box.

Required:
- Unity Editor with Windows Build Support module (included when installing on Windows; required as add-on on other OS)
- For cross-compilation from Linux/macOS: Unity's Windows Build Support (Mono) module

**Note:** IL2CPP Windows builds require the Visual Studio Build Tools (C++ workload) to be installed on the runner. GitHub-hosted `windows-latest` includes Visual Studio 2022 Community. Self-hosted Windows runners must install it manually.

---

## BuildConfig Fields

Full reference in [BUILD_CONFIG.md](BUILD_CONFIG.md#windows-object).

| Field | Default | Notes |
|---|---|---|
| `architecture` | `x86_64` | Use `x86_64` for all modern targets |
| `outputName` | `projectName` | Name of the `.exe` without extension |
| `compressOutput` | `false` | Zip the output folder for smaller artifact upload |

---

## Scripting Backend

Windows supports both `Mono` and `IL2CPP`:

| Backend | Build Time | Runtime Performance | Notes |
|---|---|---|---|
| `Mono` | Fast | Good | Supports script debugging |
| `IL2CPP` | Slow (requires MSVC) | Best | Required for some Unity features |

For release builds targeting Steam or Epic, `IL2CPP` is recommended. For internal tools or developer builds, `Mono` is faster.

---

## Output Structure

A Windows Standalone build produces:

```
Builds/
  Windows/
    MyGame.exe
    MyGame_Data/
    UnityCrashHandler64.exe
    UnityPlayer.dll
    MonoBleedingEdge/        # Mono backend only
```

When `compressOutput: true`, the entire folder is zipped to `MyGame-windows-{buildNumber}.zip` before upload.

---

## Code Signing (Optional)

Windows executable signing is not built into the workflow by default, but can be added via a post-build hook. To sign with an Authenticode certificate:

```bash
# scripts/hooks/sign-windows.sh
signtool sign \
  /fd SHA256 \
  /tr http://timestamp.digicert.com \
  /td SHA256 \
  /f "$WINDOWS_CERT_PFX" \
  /p "$WINDOWS_CERT_PASSWORD" \
  "$BUILD_OUTPUT_DIR/$OUTPUT_NAME.exe"
```

Add the hook to `hooks.postBuild` and store `WINDOWS_CERT_PFX_BASE64` and `WINDOWS_CERT_PASSWORD` as repository secrets.

---

## Installer Creation (Optional)

The workflow does not create an installer by default. Add a post-build hook using [Inno Setup](https://jrsoftware.org/isinfo.php) or [NSIS](https://nsis.sourceforge.io/) to produce a standalone installer if needed for distribution outside Steam.

---

## Steam Integration (Optional)

To deploy directly to Steam, add a `postBuild` hook using the Steamworks CLI (`steamcmd`):

```json
"hooks": {
  "postBuild": ["deploy-to-steam"]
}
```

Store `STEAM_USERNAME`, `STEAM_PASSWORD`, and `STEAM_TOTP_SECRET` as GitHub secrets and implement the deployment logic in `scripts/hooks/deploy-to-steam.sh`.

---

## Local Windows Build

From a Windows machine:

```powershell
.\scripts\build.ps1 `
  -Platform Windows `
  -Config .\ci\BuildConfig.development.json `
  -UnityPath "C:\Program Files\Unity\Hub\Editor\2022.3.45f1\Editor\Unity.exe"
```

---

## Troubleshooting

**"IL2CPP: Could not find msbuild.exe"**
Visual Studio Build Tools with the C++ workload are not installed. Install from [visualstudio.microsoft.com/downloads](https://visualstudio.microsoft.com/downloads/) → "Build Tools for Visual Studio".

**"Error building Player because scripts have compile errors"**
Check the Unity build log artifact for the specific compiler error. This is not a CI configuration issue.

**"The output file name must end with .exe"**
The `outputName` field should not include the `.exe` extension. The build script appends it automatically.

**Build artifact exceeds GitHub Actions size limit (2GB)**
Enable `compressOutput: true` to zip the output, or reduce the build content. IL2CPP builds can be large due to the runtime; Mono builds are typically smaller.
