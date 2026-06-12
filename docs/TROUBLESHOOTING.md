# Troubleshooting

Common errors and their fixes for the Docker-mandatory Unity CI/CD platform.

---

## Docker Issues

### Docker daemon unavailable

**Error:** `Cannot connect to the Docker daemon`

**Cause:** Docker Engine is not running on the CI runner or developer machine.

**Fix:**
- CI: Ensure the runner has Docker pre-installed. GitHub-hosted `ubuntu-latest` runners include Docker.
- Local: Start Docker Desktop or the Docker daemon (`sudo systemctl start docker`).
- Self-hosted: Install Docker Engine and ensure the runner user is in the `docker` group.

### Registry authentication failure

**Error:** `denied: permission denied` or `unauthorized: authentication required`

**Cause:** The runner cannot pull the Unity build image from the container registry.

**Fix:**
- Ensure `GITHUB_TOKEN` has `packages: read` permission
- For private registries, add registry credentials to the workflow
- Check that the image reference exists in the registry

### Image not found

**Error:** `manifest unknown` or `not found`

**Cause:** The requested image tag or digest does not exist in the registry.

**Fix:**
- Verify the Unity version and variant are correct
- Check image manifest for available images
- Build the image first via `build-unity-image.yml` workflow

### Image digest mismatch

**Error:** `image digest does not match expected`

**Cause:** The image in the registry has been updated but the manifest still references the old digest.

**Fix:**
- Rebuild and republish the image
- Update the image manifest with the new digest
- In development mode, use tags instead of digests

---

## Unity License Issues

### Unity license activation failed

**Error:** `Unity license activation failed` or `No valid Unity license found`

**Cause:** The `UNITY_LICENSE` secret is missing, invalid, or expired.

**Fix:**
1. Verify `UNITY_LICENSE` repository secret contains the complete `.ulf` file content
2. Check that the license covers the Unity version being used
3. Check `Logs/unity-activate.log` for detailed activation errors
4. For Professional/Plus licenses, ensure `UNITY_EMAIL` and `UNITY_PASSWORD` are also set
5. License files expire — regenerate if older than 2 years

### Machine count exceeded

**Error:** `License activation failed: Machine count exceeded`

**Cause:** Unity's concurrent activation limit reached.

**Fix:** Return licenses from unused machines via Unity Hub (Preferences → Licenses → Return), or upgrade to Unity Build Server for CI.

### License version mismatch

**Error:** `License file is not valid for this version`

**Cause:** The `.ulf` was generated for a different Unity version.

**Fix:** Activate Unity with the exact version used in the workflow and export a new `.ulf`.

---

## Permission Issues

### Permission denied on workspace files

**Error:** `Permission denied` on workspace files or Unity cache

**Cause:** File ownership mismatch between host and container.

**Fix:**
- The `run_unity_container.py` wrapper sets `--user "$(id -u):$(id -g)"` automatically
- Check that the project directory is readable by the current user
- If using a named volume, it may have been created by a different user — delete it: `docker volume rm <volume-name>`

### Root-owned output

**Error:** Build artifacts are owned by root and cannot be cleaned up.

**Cause:** Container ran as root instead of the host user.

**Fix:**
- Always use `scripts/docker/run_unity_container.py` which sets `--user` automatically
- Never run `docker run` manually without `--user`
- Fix existing root-owned files: `sudo chown -R $(id -u):$(id -g) Builds/`

---

## Cache Issues

### Library cache corruption

**Error:** `Failed to import asset` or `Asset database is corrupted`

**Cause:** Library cache is incompatible with the current Unity version or was corrupted by a failed build.

**Fix:**
- Delete the cache volume: `docker volume rm unity-lib-<hash>`
- Use `--clean-build` flag to skip cache restoration
- Set `cache-mode: off` in the workflow

---

## Container Resource Issues

### Container out of memory

**Error:** `Killed` or `OOMKilled` in container status (exit code 137)

**Cause:** Unity build exceeded the container's memory limit.

**Fix:**
- Increase memory limit: `--container-memory 12g`
- IL2CPP Android builds typically need 8+ GB
- WebGL builds may need 8+ GB

### Unity process killed

**Error:** Exit code 137 (SIGKILL)

**Cause:** OOM killer, timeout, or manual cancellation.

**Fix:**
- Check container memory limits
- Increase workflow timeout: `timeout-minutes: 90`
- Check for infinite loops in build hooks
- Check `Logs/Editor.log` for last operation before kill

---

## Build Output Issues

### Missing artifact

**Error:** `Expected artifact not found` or build reports success but no output file

**Cause:** Unity exited with code 0 but did not produce the expected build artifact.

**Fix:**
- Check `BuildReports/build-report.json` for build details
- Check `Logs/Editor.log` for Unity-side errors
- Verify `outputDirectory` in BuildConfig matches expected path
- Verify scene list is not empty
- The wrapper treats missing expected artifacts as failure even when Unity exits 0

### Missing Editor.log

**Error:** No log file in the Logs directory after build failure.

**Cause:** Container crashed before Unity wrote any log, or the log mount was misconfigured.

**Fix:**
- Check Docker container exit code for OOM or signal kills
- Verify the Logs directory mount in the docker command
- Use `--dry-run` to inspect the mount configuration

---

## Platform Issues

### Unsupported platform

**Error:** `Target 'iOS' is unsupported by the Docker-only build platform`

**Cause:** Attempting to build an unsupported target (iOS, Windows).

**Fix:**
- Use a dedicated macOS pipeline for iOS builds
- Use a dedicated Windows pipeline for Windows builds
- See [PLATFORM_LIMITATIONS.md](PLATFORM_LIMITATIONS.md)

### Android SDK/NDK mismatch

**Error:** `Android SDK/NDK version mismatch` or Gradle build failures

**Cause:** The project requires a different SDK/NDK version than installed in the image.

**Fix:**
- Check the image manifest for installed SDK/NDK versions
- Update `docker/variants/android.Dockerfile` and rebuild the image
- Do not install SDK components at build time

---

## Schema Validation Errors

### Empty scenes array

**Error:** `scenes: must NOT have fewer than 1 items`

**Fix:** Add at least one scene path to the `scenes` array.

### Invalid bundleVersion

**Error:** `bundleVersion: must match pattern`

**Fix:** Use `MAJOR.MINOR.PATCH` format, e.g. `"1.0.0"` not `"1.0"`.

### Invalid applicationId

**Error:** `android.applicationId: must match pattern`

**Fix:** Use reverse-DNS format: `com.company.game`. Must start with a letter.

### Production dev build

**Error:** `developmentBuild must be false for production`

**Fix:** Set `developmentBuild: false` in `BuildConfig.production.json`.

---

## General Issues

### Slow first build

**Cause:** No Library cache exists. Unity must import all assets.

**Fix:**
- Expected for first build; subsequent builds reuse cached Library volume
- Set `cache-mode: safe` (default) to enable caching

### Build passes locally but fails in CI

**Fix:**
- Use the same image reference locally and in CI
- Use `--dry-run` to compare Docker commands
- Check Unity version matches exactly
- Verify all required secrets are set in CI

---

## Still Stuck?

1. Download the full build log artifact from the failed workflow run
2. Search for `Error` in `Editor.log` (case-sensitive; Unity uses capital-E)
3. Open an issue with: relevant log lines, BuildConfig (redact secrets), workflow run URL
