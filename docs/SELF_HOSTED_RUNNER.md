# Self-Hosted Runners

This document covers setting up self-hosted GitHub Actions runners for the Docker-mandatory `unity-build-workflows` platform.

Self-hosted runners are recommended when:
- Build times on GitHub-hosted runners are too slow
- Unity license costs require minimizing concurrent activations
- Network access to private registries is required
- Specific hardware (large memory, fast storage) is needed

---

## Requirements

All self-hosted runners must have **Docker Engine** installed. Unity is never installed directly on the runner.

| Component | Requirement |
|---|---|
| OS | Ubuntu 22.04+ (recommended) |
| Docker Engine | 20.10+ with BuildKit support |
| RAM | 16 GB minimum (32 GB recommended for IL2CPP) |
| Storage | 100 GB SSD (Docker images + cache volumes) |
| GPU | Not required for builds |

### Docker Installation

```bash
# Install Docker Engine
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add runner user to docker group
sudo usermod -aG docker $USER

# Verify
docker run --rm hello-world
```

---

## Registering the Runner

### Organization-Level (recommended)

1. **Organization Settings → Actions → Runners → New self-hosted runner**
2. Select Linux
3. Follow the setup script
4. Add labels: `self-hosted`, `unity-docker`

### Repository-Level

1. **Repository Settings → Actions → Runners → New self-hosted runner**
2. Follow the setup script
3. Add labels: `self-hosted`, `unity-docker`

---

## Runner as a Service

```bash
# After ./config.sh
sudo ./svc.sh install
sudo ./svc.sh start
sudo systemctl enable actions.runner.<org>-<repo>.<runner-name>
```

---

## Docker Image Caching

Pre-pull Unity images on the runner to avoid download time during builds:

```bash
docker pull ghcr.io/<IMAGE_NAMESPACE>/unity-builder:6000.0.26f1-android-v2.0.0
docker pull ghcr.io/<IMAGE_NAMESPACE>/unity-builder:6000.0.26f1-webgl-v2.0.0
docker pull ghcr.io/<IMAGE_NAMESPACE>/unity-builder:6000.0.26f1-linux-v2.0.0
```

Set up a cron job to pull latest images weekly.

---

## Library Cache Volumes

Docker named volumes persist Unity Library caches between builds:

```bash
# List cache volumes
docker volume ls | grep unity-lib

# Remove a corrupted cache
docker volume rm unity-lib-<hash>

# Remove all Unity cache volumes
docker volume ls -q | grep unity-lib | xargs docker volume rm
```

---

## Security Hardening

1. **Run as a dedicated low-privilege user** — not root
2. **Docker group access only** — runner user in `docker` group
3. **No Docker socket mount** — Unity containers never access the Docker socket
4. **Outbound firewall** — allow only required endpoints (GitHub, Unity licensing, your registry)
5. **Separate runners by environment** — staging and production use different runner groups
6. **Regular updates** — keep Docker Engine and runner agent updated

---

## Storage Management

Docker images and volumes consume significant storage:

```bash
# Check Docker disk usage
docker system df

# Clean unused images (keeps pulled images)
docker image prune -f

# Clean all unused resources (aggressive)
docker system prune -f
```

Set up a weekly cleanup job:
```bash
# Crontab entry
0 3 * * 0 docker system prune -f --volumes --filter "until=168h"
```

---

## Troubleshooting

**"No runner matching labels found"** — Check runner labels match workflow requirements.

**"Cannot connect to Docker daemon"** — Ensure Docker is running and the runner user is in the `docker` group.

**"Permission denied"** — Verify Docker group membership: `groups $USER | grep docker`

**"Disk full"** — Run `docker system prune -f` and check volume usage.
