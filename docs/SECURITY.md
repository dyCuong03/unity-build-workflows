# Security

This document describes the security model, secret handling practices, fork safety measures, and threat model for `unity-build-workflows`.

---

## Threat Model

The primary assets being protected:

| Asset | Risk | Mitigation |
|---|---|---|
| Android signing keystore | Unauthorized APK/AAB signing | Secrets scoped to protected environments; never logged |
| iOS distribution certificate | Unauthorized IPA signing / App Store submission | Same as keystore; cleaned from keychain after build |
| App Store Connect API key | Unauthorized app submissions or app data access | Environment-scoped; short-lived use |
| Unity license serial | License theft / activation exhaustion | Repository secret; not available to forks |
| Production build artifacts | Tampering before distribution | Builds run in isolated jobs; artifact checksums recorded |

---

## Secret Handling

### Where Secrets Live

Secrets are stored in GitHub's encrypted secret store (at repository or environment scope). They are never:
- Written to disk outside of a temporary file used immediately and deleted
- Printed in logs (GitHub masks known secret values; scripts additionally use `set +x` around secret expansion)
- Passed as command-line arguments (use environment variables instead)

### Secret Injection Pattern

All sensitive values are injected via environment variables, not shell arguments:

```bash
# Good — value not visible in process list
export KEYSTORE_PASS="${{ secrets.ANDROID_KEYSTORE_PASSWORD }}"
./sign.sh

# Bad — value visible in process list
./sign.sh --password "${{ secrets.ANDROID_KEYSTORE_PASSWORD }}"
```

### Temporary Keystore File

The Android signing keystore and iOS certificate are decoded from base64 to temporary files:

```bash
KEYSTORE_PATH=$(mktemp)
echo "$ANDROID_KEYSTORE_BASE64" | base64 -d > "$KEYSTORE_PATH"
# ... build and sign ...
rm -f "$KEYSTORE_PATH"
```

The `rm` is placed in a `trap EXIT` handler so it runs even if the script fails.

---

## Fork Pull Request Safety

GitHub Actions does not provide repository secrets to workflows triggered by pull requests from forks. This is a GitHub platform-level protection and is the primary defense against malicious PRs exfiltrating secrets.

**What fork PR workflows can access:**
- Public repository contents
- `GITHUB_TOKEN` with read-only permissions on public repositories
- No repository secrets
- No environment secrets

**What this means for `unity-build-workflows`:**

Pull request workflows from forks can run schema validation, linting, and test compilation, but they cannot sign builds or access production resources. This is by design.

If your repository is private and you want to allow trusted contributors' fork PRs to run full builds, use the `pull_request_target` event with explicit approval gating — but understand the security implications before doing so.

---

## Environment Protection Rules

Production secrets are scoped to the `production` GitHub Environment, which enforces:

1. **Required reviewers** — at least one human must approve the deployment
2. **Branch/tag restriction** — only tags matching `v*` from `main` can deploy to production
3. **No fork access** — forks cannot trigger environment deployments

This means even if a malicious commit is pushed to a branch, it cannot access production secrets without:
- Merging to `main` (requires PR approval)
- Creating a `v*` tag (requires push access to `main`)
- Having the deployment reviewed and approved

---

## `GITHUB_TOKEN` Permissions

Workflows use the minimum required `GITHUB_TOKEN` permissions:

```yaml
permissions:
  contents: read
  actions: read
  checks: write        # For test result annotations
  id-token: write      # For OIDC (if used for cloud auth)
```

The default `GITHUB_TOKEN` is not granted write access to the repository contents, preventing workflows from accidentally modifying source code.

---

## OIDC for Cloud Authentication (Optional)

If your `postBuild` hooks upload artifacts to AWS S3, Google Cloud Storage, or Azure Blob Storage, prefer OIDC over long-lived access keys:

```yaml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::123456789012:role/unity-build-upload
    aws-region: ap-southeast-1
```

OIDC tokens are short-lived and bound to the specific workflow run, making them far more secure than static access keys stored as secrets.

---

## Dependency Pinning

All actions in the workflows are pinned to their full commit SHA (not a floating tag), to prevent supply chain attacks via compromised action tags:

```yaml
# Pinned to SHA — safe
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2

# Not pinned — vulnerable to tag hijacking
- uses: actions/checkout@v4
```

Dependabot is configured to keep action dependencies up to date via SHA pinning.

---

## Artifact Integrity

Each build produces a `build-manifest.json` alongside the artifact containing:
- SHA-256 hash of the build output
- Build configuration hash
- Runner hostname
- Build timestamp
- GitHub run ID and SHA

This allows verifying that a distributed build artifact matches the one produced by CI.

---

## Secret Rotation Policy

| Secret | Rotation Frequency | Trigger for Immediate Rotation |
|---|---|---|
| `ANDROID_KEYSTORE_*` | Annual | Departing team member, suspected compromise |
| `IOS_CERTIFICATE_*` | Before expiry (1 year) | Departing team member, Apple revocation |
| `APPLE_CONNECT_API_KEY_*` | Annual | Departing team member, suspected compromise |
| `UNITY_LICENSE` | Per subscription renewal | License revocation |
| `SLACK_WEBHOOK_URL` | On rotation by Slack admin | Suspected leak |

---

## Reporting Security Vulnerabilities

Do not open a public GitHub issue for security vulnerabilities. Email `security@buzzellstudio.com` with:
- Description of the vulnerability
- Steps to reproduce
- Potential impact

We will respond within 72 hours and coordinate a fix and disclosure timeline with you.
