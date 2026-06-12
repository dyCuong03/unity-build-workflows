# Self-Hosted Runners

This document covers setting up and configuring self-hosted GitHub Actions runners for `unity-build-workflows`. Self-hosted runners are recommended when:

- iOS builds are needed (requires macOS)
- Build times on GitHub-hosted runners are too slow for your team's iteration speed
- Unity license costs require minimizing concurrent activations
- Specific hardware (Apple Silicon, dedicated GPU) is needed for builds

---

## Runner Requirements by Platform

| Platform | OS | Min RAM | Min Storage | Notes |
|---|---|---|---|---|
| Android | Ubuntu 22.04 | 16 GB | 100 GB SSD | GPU not required |
| iOS | macOS 13+ | 16 GB | 200 GB SSD | Apple Silicon preferred |
| Windows | Windows Server 2022 / Windows 11 | 16 GB | 100 GB SSD | Visual Studio required for IL2CPP |
| WebGL | Ubuntu 22.04 | 16 GB | 100 GB SSD | Same as Android runner |

Unity's `Library/` cache can consume 20–40 GB per project. Provision storage generously.

---

## Installing Unity on Self-Hosted Runners

### Linux / macOS (Unity Hub CLI)

```bash
# Install Unity Hub
# Linux:
wget -qO - https://hub.unity3d.com/linux/keys/public | gpg --dearmor | sudo tee /usr/share/keyrings/Unity_Technologies_ApS.gpg
sudo sh -c 'echo "deb [signed-by=/usr/share/keyrings/Unity_Technologies_ApS.gpg] https://hub.unity3d.com/linux/repos/deb stable main" > /etc/apt/sources.list.d/unityhub.list'
sudo apt-get update && sudo apt-get install unityhub

# Install specific Unity version with required modules
unityhub --headless install \
  --version 2022.3.45f1 \
  --module android \
  --module ios \
  --module webgl
```

### Windows (Unity Hub silent install)

```powershell
# Download and install Unity Hub silently
Invoke-WebRequest -Uri "https://public-cdn.cloud.unity3d.com/hub/prod/UnityHubSetup.exe" -OutFile "UnityHubSetup.exe"
.\UnityHubSetup.exe /S

# Install Unity version with modules
& "C:\Program Files\Unity Hub\Unity Hub.exe" -- --headless install `
  --version 2022.3.45f1 `
  --module windows `
  --module android
```

---

## Registering the Runner with GitHub

### Organization-Level Runner (recommended)

For multiple Unity projects in the same organization:

1. Go to **Organization Settings → Actions → Runners → New self-hosted runner**
2. Select the runner OS
3. Follow the setup script provided by GitHub
4. Add runner labels: `self-hosted`, `unity`, `macos-unity` (or `ubuntu-unity`, `windows-unity`)

### Repository-Level Runner

For a single project:

1. Go to **Repository Settings → Actions → Runners → New self-hosted runner**
2. Follow the setup script
3. Add labels: `self-hosted`, `unity`

---

## Runner Configuration

### As a systemd Service (Linux)

```bash
# After completing ./config.sh
sudo ./svc.sh install
sudo ./svc.sh start
sudo systemctl enable actions.runner.<org>-<repo>.<runner-name>
```

### As a launchd Service (macOS)

```bash
sudo ./svc.sh install
sudo ./svc.sh start
```

### As a Windows Service

```powershell
.\svc.ps1 install
.\svc.ps1 start
```

---

## Runner Labels in BuildConfig Workflows

Reference self-hosted runners by their labels in your consumer workflow:

```yaml
jobs:
  build-ios:
    uses: BuzzelStudio/unity-build-workflows/.github/workflows/ios.yml@v1
    with:
      build-config: ${{ needs.config.outputs.merged }}
      unity-version: '2022.3.45f1'
      runner: 'self-hosted,unity,macos-unity'
    secrets: inherit
```

---

## Library Cache Strategy

The Unity `Library/` folder is the largest cache artifact. Two caching strategies:

### Persistent Volume (recommended for speed)

Keep the workspace across runs by setting a fixed working directory for the runner. The `Library/` folder persists between builds, making incremental builds fast (2–5 minutes vs. 20–40 minutes for cold builds).

Downside: concurrent builds on the same runner can corrupt the cache. Use one runner per Unity project if builds can run simultaneously.

### GitHub Actions Cache

Use `actions/cache` to save and restore `Library/` from GitHub's cache service. Slower than a persistent volume (upload/download overhead), but safe for concurrent builds.

```yaml
- name: Cache Unity Library
  uses: actions/cache@v4
  with:
    path: Library
    key: unity-library-${{ runner.os }}-${{ hashFiles('ProjectSettings/ProjectVersion.txt') }}
    restore-keys: unity-library-${{ runner.os }}-
```

---

## Security Hardening for Self-Hosted Runners

Self-hosted runners that process production builds have access to signing secrets. Harden them:

1. **Isolate runners by environment.** Use separate runners for staging and production. Label them `staging-runner` and `production-runner` respectively.

2. **Restrict environment runner assignment.** In GitHub Environment settings, set "Deployment runners" to require a specific runner group.

3. **No network access from build workspace.** Configure outbound firewall rules to allow only required endpoints (GitHub, Unity licensing, your CDN).

4. **Run as a dedicated low-privilege user.** Do not run the runner agent as root or an admin account.

5. **Rotate secrets regularly.** See [SECURITY.md](SECURITY.md) for the rotation policy.

6. **Audit the runner machine.** Enable OS-level audit logging for file access and process execution on the runner.

---

## Maintenance

### Updating the Runner Agent

```bash
# Stop the service first
sudo ./svc.sh stop

# Download and install the latest runner agent
./config.sh --url <repo-url> --token <new-token>

sudo ./svc.sh start
```

GitHub will warn in the Actions UI when a runner agent is out of date.

### Updating Unity

Install the new Unity version alongside the existing one using Unity Hub. Update the `unity-version` input in your consumer workflow, then uninstall the old version after confirming builds are stable.

---

## Troubleshooting

**"No runner matching labels found"**
The runner labels in the workflow do not match any registered runner. Check the runner's labels in **Settings → Runners** and ensure they match exactly.

**"Runner lost connection during build"**
Network interruption or runner machine went to sleep. For macOS runners, disable sleep (`sudo systemctl mask sleep.target` equivalent on macOS: System Settings → Battery → Prevent sleeping). For Linux, set `TZ=UTC` and check for NTP issues.

**"Unity license could not be activated: Machine limit reached"**
Your Unity license allows a limited number of concurrent activations. Return the license from previous runner machines via Unity Hub, or upgrade to a Unity Build Server license for CI use.
