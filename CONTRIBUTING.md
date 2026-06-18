# Contributing to unity-build-workflows

Thank you for your interest in contributing. This document explains how to propose changes, the review process, and coding standards.

---

## What Belongs Here

This repository is a **Docker-mandatory CI/CD platform library** for Unity games. Contributions should fit one of these categories:

- Bug fixes to existing workflows, scripts, Docker images, or schema
- New Docker image variants or platform support (e.g., Linux dedicated server)
- New composite actions for Docker-based Unity workflows
- Documentation improvements
- New BuildConfig fields that are broadly applicable
- Security improvements to the Docker execution model

Project-specific hooks and custom build methods belong in the consumer repository, not here.

**Important:** All Unity operations must run inside Docker containers. Do not add native Unity execution paths.

---

## Getting Started

### Prerequisites

- Git
- Python 3.8+ (for scripts and tests)
- Docker Engine 20.10+ (for local testing)
- `jq` (for config inspection)
- `shellcheck` (for shell script linting)
- A Unity installation is **not required** to contribute. Docker handles the Unity environment.

### Setup

```bash
git clone https://github.com/<WORKFLOW_OWNER>/unity-build-workflows.git
cd unity-build-workflows
pip install -r tests/requirements.txt
```

### Run Tests

```bash
pytest tests/
```

### Lint Shell Scripts

```bash
shellcheck docker/unity/*.sh scripts/docker/*.sh
```

---

## Development Workflow

1. Fork the repository and create a branch: `git checkout -b feature/my-improvement`
2. Make your changes.
3. Run tests: `pytest tests/`
4. Run linting: `shellcheck docker/unity/*.sh`
5. Commit with a conventional commit message.
6. Push and open a pull request against `main`.

---

## Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

Scopes: `docker`, `android`, `webgl`, `linux`, `schema`, `scripts`, `docs`, `release`, `actions`, `workflows`

Examples:
```
feat(docker): add GPU support to linux variant
fix(android): correct Gradle cache volume name
docs(security): add SBOM generation details
test(docker): add entrypoint timeout test
```

---

## Pull Request Requirements

- [ ] All tests pass (`pytest tests/`)
- [ ] `shellcheck` passes for shell scripts
- [ ] No native Unity invocation introduced (checked by `test_no_native_unity_invocation.py`)
- [ ] YAML workflow files are valid
- [ ] CHANGELOG.md has an entry under `[Unreleased]`
- [ ] At least one approval from a maintainer

---

## Breaking Changes

A breaking change requires:
1. Prior discussion in a GitHub issue
2. A major version bump (v2 → v3)
3. A migration guide in the PR description
4. Updated CHANGELOG.md

---

## Docker-Specific Guidelines

### Dockerfiles

- Keep images minimal — only add packages needed for the build
- Pin base images by tag (digest in production)
- Do not bake secrets into image layers
- Add OCI labels for traceability
- Test entrypoint changes with fake Unity executable

### Entrypoint

- Use `set -Eeuo pipefail`
- Validate all inputs before invoking Unity
- Use traps for cleanup
- Preserve exit codes

### Container Security

- No `--privileged`
- No Docker socket mount
- `--cap-drop=ALL`
- `--security-opt=no-new-privileges`

---

## Code Style

### Shell Scripts

- `set -Eeuo pipefail` at the top
- Prefer `[[ ]]` over `[ ]`
- Quote all variable expansions
- Use `shellcheck` disable comments sparingly

### Python Scripts

- Python 3.8+ compatible
- Use `argparse` for CLI
- Type hints encouraged
- Follow existing patterns in `scripts/docker/`

### GitHub Actions YAML

- All action references pinned to commit SHA with version comment
- Use `env:` blocks for secrets, not inline `${{ secrets.X }}`
- Add `description:` to all inputs
- Use `if: always()` on cleanup/upload steps

---

## Maintainers

- `@<WORKFLOW_OWNER>/mobile` team

For questions, open a GitHub issue or contact the platform team via your organization's preferred channel.
