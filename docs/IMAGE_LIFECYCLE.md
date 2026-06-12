# Image Lifecycle

## Base Image Selection

**Decision:** Thin organization-owned image extending pinned GameCI base images.

See [ADR-001](adr/001-docker-mandatory-architecture.md) for the rationale.

### GameCI Base Images

We use [GameCI](https://game.ci/) `unityci/editor` images as the base:

```
unityci/editor:6000.0.26f1-android-3
unityci/editor:6000.0.26f1-webgl-3
unityci/editor:6000.0.26f1-linux-il2cpp-3
```

GameCI handles Unity Editor installation, module setup, and SDK toolchain configuration. Our organization layer adds:

- Standardized entrypoint (`entrypoint.sh`)
- License activation/return scripts
- Health check script
- System tools (python3, jq, curl)
- Non-root user configuration
- OCI labels and metadata

## Image Variants

| Variant | Base Image | Supported Targets | Modules |
|---|---|---|---|
| `android` | `unityci/editor:*-android-*` | Android | android, android-sdk-ndk-tools, android-open-jdk |
| `webgl` | `unityci/editor:*-webgl-*` | WebGL | webgl |
| `linux` | `unityci/editor:*-linux-il2cpp-*` | Linux64, LinuxServer | linux-il2cpp, linux-server |

Do not create a single image with all modules. Each variant contains only the modules required for its targets.

## Image Tags

### Human-Readable Tags

```
ghcr.io/buzzelstudio/unity-builder:6000.0.26f1-android-v2.0.0
ghcr.io/buzzelstudio/unity-builder:6000.0.26f1-webgl-v2.0.0
ghcr.io/buzzelstudio/unity-builder:6000.0.26f1-linux-v2.0.0
```

Format: `<unity-version>-<variant>-v<tooling-version>`

### Digest References (Production)

```
ghcr.io/buzzelstudio/unity-builder@sha256:abc123...
```

Production and release workflows resolve and use digest-pinned references.

### Forbidden Tags

Never use:
- `latest`
- `ubuntu`
- `unity6`
- `android-latest`
- Any mutable tag in release mode

## Image Build Workflow

Triggered by:
- Changes to `docker/**`
- Changes to image manifest or entrypoint
- Manual dispatch
- Unity version updates

**Not** triggered by game project changes.

### Build Steps

1. Validate image configuration
2. Build the requested variant (BuildKit)
3. Run entrypoint tests (fake Unity)
4. Verify Unity executable availability
5. Verify required modules
6. Verify SDK/NDK/JDK versions (Android)
7. Run minimal Unity smoke command (when license available)
8. Generate image metadata
9. Generate SBOM (`scripts/docker/generate_sbom.sh`)
10. Scan for vulnerabilities (`scripts/docker/scan_image.sh`)
11. Check for embedded secrets (history inspection)
12. Push to registry
13. Publish immutable tags
14. Record image digest
15. Publish image manifest artifact

Image publication is blocked if critical validation or security scanning fails.

## Scanning

### Vulnerability Scanning

Uses Trivy or Grype to scan for known CVEs:

```bash
./scripts/docker/scan_image.sh \
  ghcr.io/buzzelstudio/unity-builder:6000.0.26f1-android-v2.0.0 \
  --severity HIGH,CRITICAL \
  --exit-code 1
```

Weekly scheduled scans via `scan-unity-image.yml` catch newly disclosed vulnerabilities.

### SBOM Generation

```bash
./scripts/docker/generate_sbom.sh \
  ghcr.io/buzzelstudio/unity-builder:6000.0.26f1-android-v2.0.0
```

Generates SPDX-format Software Bill of Materials.

## Image Manifest

Each published image includes a JSON manifest (`image-manifest.json`) validated against `schemas/unity-image-manifest.schema.json`.

The manifest records:
- Unity Editor version and changeset
- Base image digest
- OS version
- Installed modules
- Supported build targets
- Supported scripting backends
- Android SDK/NDK/JDK versions (android variant)
- Tooling version
- Build timestamp
- Source commit
- Image digest
- Contract version

Workflows validate the manifest before running a build. Builds fail if:
- Target is unsupported by the image
- Unity version does not match
- Required modules are missing
- Image contract version is incompatible
- Image reference is mutable in release mode

## Deprecation

When deprecating an image:

1. Remove it from the active image manifest
2. Keep the image in the registry for the retention period
3. Add a deprecation notice to the manifest
4. Update consuming workflows to use the replacement
5. Delete after the retention period

## Secret Inspection

Before publication, images are inspected for accidentally embedded secrets:

```bash
docker history --no-trunc <image> | grep -iE 'license|password|secret|key|token'
```

Images containing secret material in any layer must not be published.
