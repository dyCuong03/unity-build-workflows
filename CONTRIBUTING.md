# Contributing to unity-build-workflows

Thank you for your interest in contributing. This document explains how to propose changes, the review process, and coding standards.

---

## What Belongs Here

This repository is a **platform library** for Unity CI/CD. Contributions should fit one of these categories:

- Bug fixes to existing workflows, scripts, or schema
- New platform support (e.g., tvOS, Nintendo Switch via partner SDK)
- New composite actions that are useful across multiple Unity projects
- Documentation improvements
- New BuildConfig fields that are broadly applicable (not project-specific)

Project-specific hooks and custom build methods belong in the consumer repository, not here.

---

## Getting Started

### Prerequisites

- Git
- Node.js 18+ (for schema validation via `ajv-cli`)
- `jq` (for config merge testing)
- `shellcheck` (for shell script linting)
- A Unity installation is not required to contribute to the workflow YAML or documentation.

### Setup

```bash
git clone https://github.com/BuzzelStudio/unity-build-workflows.git
cd unity-build-workflows
npm install   # installs ajv-cli and other dev tools
```

### Validate the Schema

```bash
npx ajv-cli validate \
  -s schemas/unity-build-config.schema.json \
  -d templates/BuildConfig.base.example.json
```

All four template files must validate without errors.

### Lint Shell Scripts

```bash
shellcheck scripts/**/*.sh
```

---

## Development Workflow

1. Fork the repository and create a branch: `git checkout -b feature/my-improvement`
2. Make your changes.
3. Run validation: `npm test` (runs schema validation + shellcheck)
4. Commit with a conventional commit message (see below).
5. Push and open a pull request against `main`.

---

## Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

Types:

| Type | When to Use |
|---|---|
| `feat` | New feature or workflow capability |
| `fix` | Bug fix |
| `docs` | Documentation only changes |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or correcting tests |
| `chore` | Tooling, CI config, dependency updates |

Scopes: `android`, `ios`, `windows`, `webgl`, `schema`, `scripts`, `docs`, `release`.

Examples:
```
feat(android): add symbol export support for Crashlytics
fix(ios): return license before failing on code sign error
docs(security): add OIDC section for cloud auth
```

---

## Pull Request Requirements

Before a PR can be merged:

- [ ] All schema validation tests pass (`npm test`)
- [ ] `shellcheck` passes with no errors
- [ ] YAML workflow files are valid (checked by `actionlint` in CI)
- [ ] New workflow inputs are documented in [docs/BUILD_CONFIG.md](docs/BUILD_CONFIG.md)
- [ ] New platform or signing changes include a documentation update
- [ ] CHANGELOG.md has an entry under `[Unreleased]`
- [ ] At least one approval from a maintainer

For changes that affect the workflow input interface (adding/removing/renaming inputs), open an issue first to discuss backward compatibility implications before writing code.

---

## Breaking Changes

A breaking change is any modification to the public interface that would require consumer repositories to update their workflow files. Examples:

- Removing a workflow input
- Renaming a workflow input
- Changing the type or valid values of an input
- Removing an output that downstream jobs depend on

Breaking changes require:
1. Prior discussion in a GitHub issue
2. A major version bump (v1 → v2)
3. A migration guide in the PR description and in `docs/`
4. The previous major version tag (`v1`) must remain functional for a transition period

---

## Testing Workflow Changes

Because testing reusable GitHub Actions workflows requires running them in GitHub Actions, test your changes by:

1. Pushing your branch to a fork of this repository
2. Creating a test consumer repository
3. Referencing your fork's branch: `uses: your-fork/unity-build-workflows/.github/workflows/android.yml@your-branch`

The repository's own CI runs structural validation (`actionlint`, `shellcheck`, schema checks) but cannot run a full Unity build.

---

## Code Style

### Shell Scripts

- Use `set -euo pipefail` at the top of every script.
- Prefer `[[ ]]` over `[ ]` for conditionals in bash scripts.
- Quote all variable expansions: `"${MY_VAR}"` not `$MY_VAR`.
- Add `shellcheck` disable comments only when necessary, with a comment explaining why.

### GitHub Actions YAML

- All action references must be pinned to a full commit SHA with a version comment.
- Use `env:` blocks to pass secrets to scripts rather than inline `${{ secrets.X }}` in `run:` blocks.
- Add `description:` to all workflow inputs.
- Group related jobs with `needs:` to make the job graph clear.

### JSON Schema

- All new properties must have a `description` field.
- Use `additionalProperties: false` on all object definitions.
- New enum values go at the end of the `enum` array to avoid renumbering (which can affect validation error messages).

---

## Maintainers

- BuzzelStudio mobile team (`@BuzzelStudio/mobile`)

For questions that don't fit a GitHub issue, reach out via the internal `#ci-platform` Slack channel.
