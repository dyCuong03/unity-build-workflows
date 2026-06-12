# Docker Image Infrastructure

This directory contains the base Unity CI image definition and all supporting
scripts used by BuzzelStudio build workflows.

## Image Hierarchy

```
unityci/editor:<version>-base-3          (upstream GameCI)
  └── docker/unity/Dockerfile            buzzelstudio/unity-base

unityci/editor:<version>-android-3       (upstream GameCI)
  └── docker/variants/android.Dockerfile buzzelstudio/unity-android

unityci/editor:<version>-webgl-3         (upstream GameCI)
  └── docker/variants/webgl.Dockerfile   buzzelstudio/unity-webgl

unityci/editor:<version>-linux-il2cpp-3  (upstream GameCI)
  └── docker/variants/linux.Dockerfile   buzzelstudio/unity-linux
```

All variants carry the same `entrypoint.sh`, `healthcheck.sh`,
`activate-license.sh`, and `return-license.sh` tooling layer.

## Variants

| Dockerfile                          | Build Target              | Modules Included                   |
|-------------------------------------|---------------------------|------------------------------------|
| `docker/unity/Dockerfile`           | (no platform module)      | base tooling only                  |
| `docker/variants/android.Dockerfile`| `Android`                 | Android SDK, NDK, OpenJDK 17       |
| `docker/variants/webgl.Dockerfile`  | `WebGL`                   | Emscripten                         |
| `docker/variants/linux.Dockerfile`  | `StandaloneLinux64`, `LinuxServer` | IL2CPP, GCC, clang       |

## Building Locally

```bash
# From the repo root
docker build \
  -f docker/unity/Dockerfile \
  --build-arg SOURCE_COMMIT=$(git rev-parse HEAD) \
  --build-arg BUILD_TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ') \
  -t buzzelstudio/unity-base:6000.0.26f1 \
  .

# Android variant
docker build \
  -f docker/variants/android.Dockerfile \
  -t buzzelstudio/unity-android:6000.0.26f1 \
  .
```

## Running a Build

```bash
docker run --rm \
  -v $(pwd):/workspace \
  -v $(pwd)/Builds:/workspace/Builds \
  -v $(pwd)/Logs:/workspace/Logs \
  -e UNITY_LICENSE="$(cat path/to/Unity_v6.x.ulf)" \
  buzzelstudio/unity-android:6000.0.26f1 \
  build \
    --project-path /workspace \
    --target-platform Android \
    --environment production \
    --build-config /workspace/build-config.json \
    --output-path /workspace/Builds \
    --log-dir /workspace/Logs
```

## Supported Commands

| Command             | Description                                              |
|---------------------|----------------------------------------------------------|
| `build`             | Full platform build via `BuildCommand.Execute`           |
| `build-addressables`| Addressable Asset build only                             |
| `validate`          | Project validation, no build output                      |
| `test-editmode`     | Run Unity EditMode tests                                 |
| `test-playmode`     | Run Unity PlayMode tests                                 |
| `inspect`           | Print container environment (no Unity invocation)        |
| `version`           | Print Unity version and exit                             |

## License Activation

The entrypoint calls `activate-license.sh` automatically when one of these
environment variables is set:

| Variable         | Purpose                                       |
|------------------|-----------------------------------------------|
| `UNITY_LICENSE`  | ULF file content (raw XML or base64-encoded)  |
| `UNITY_EMAIL`    | Email for email+password activation           |
| `UNITY_PASSWORD` | Password for email+password activation        |
| `UNITY_SERIAL`   | (optional) Serial key for plus/pro licenses   |

License files are written to a temp location (`/tmp/unity-license-*.ulf`) with
`600` permissions and are never echoed to any log stream. They are deleted in
the cleanup trap at container exit.

## Non-Root / Arbitrary UID Support

The images create a `unity` user (UID/GID 1000 by default) and set
`HOME=/tmp/unity-home` (world-sticky) to ensure the home directory is always
writable even when the container is run with `--user`.

```bash
# Run as arbitrary UID
docker run --rm --user 2000:2000 \
  -v $(pwd):/workspace \
  buzzelstudio/unity-android:6000.0.26f1 inspect
```

## Environment Variables Reference

| Variable                   | Default                      | Description                          |
|----------------------------|------------------------------|--------------------------------------|
| `UNITY_EDITOR`             | `/usr/bin/unity-editor`      | Path to Unity editor binary          |
| `UNITY_VERSION`            | set by Dockerfile ARG        | Unity version string                 |
| `BUILD_TARGET`             | variant-specific             | Default build target platform        |
| `BUILD_ENVIRONMENT`        | `development`                | Environment tag passed to BuildCommand |
| `BUILD_OUTPUT_PATH`        | `/workspace/Builds`          | Default build output directory       |
| `TEST_RESULTS_PATH`        | `/workspace/TestResults`     | Test result XML output directory     |
| `LOG_DIR`                  | `/workspace/Logs`            | Editor.log copy destination          |
| `UNITY_LOG_FILE`           | `/tmp/unity-home/Editor.log` | Unity internal log path              |
| `HEALTHCHECK_MIN_DISK_MB`  | `512`                        | Minimum free MB on /workspace        |
| `GRADLE_USER_HOME`         | `/tmp/gradle-cache`          | (android) Gradle cache location      |
| `EM_CACHE`                 | `/tmp/emscripten-cache`      | (webgl) Emscripten cache location    |

## Security Notes

- No secrets, licenses, or credentials are baked into any image layer.
- `chmod 777` is never used; directories use sticky-bit `1777` where multi-user write is needed.
- Path traversal (`..`) is rejected by `entrypoint.sh` for all path arguments.
- License files are written at `600` and removed at exit.
