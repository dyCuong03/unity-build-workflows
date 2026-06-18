# Build Secrets Reference

This document lists every secret and variable that the unity-build-workflows pipelines read from GitHub repository or environment secrets. No actual secret values are stored here — this file is safe to commit.

Configure secrets under **Settings → Secrets and variables → Actions** in your GitHub repository, or at the organization level for shared secrets.

Production secrets (marked with ⚙️) must be scoped to a **GitHub Environment** named `production` with required-reviewer protection. See [docs/SECURITY.md](../docs/SECURITY.md) for environment setup.

---

## Secret Matrix

| Secret Name | Development | Staging | Production | Artifact-only | Store-deploy | Description |
|---|:---:|:---:|:---:|:---:|:---:|---|
| **Unity License** | | | | | | |
| `UNITY_LICENSE` | ✓ | ✓ | ✓ | ✓ | — | Complete `.ulf` file content (not base64-encoded). Either this or the email/password/serial trio must be provided. |
| `UNITY_EMAIL` | ○ | ○ | ○ | ○ | — | Unity account email. Required when activating a floating/serial license instead of file-based. |
| `UNITY_PASSWORD` | ○ | ○ | ○ | ○ | — | Unity account password. Required with email for floating license activation. |
| `UNITY_SERIAL` | ○ | ○ | ○ | ○ | — | Unity serial number. Required for Pro/Plus serial activation. |
| **Android** | | | | | | |
| `ANDROID_KEYSTORE_BASE64` | — | ✓ | ✓ | — | — | Android keystore file, base64-encoded. Required when `keystoreMode: custom`. |
| `ANDROID_KEYSTORE_PASSWORD` | — | ✓ | ✓ | — | — | Password for the keystore file. |
| `ANDROID_KEY_ALIAS` | — | ✓ | ✓ | — | — | Alias of the signing key inside the keystore. |
| `ANDROID_KEY_PASSWORD` | — | ✓ | ✓ | — | — | Password for the key alias. |
| **Google Play** | | | | | | |
| `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` | — | — | — | — | ✓ | Service account JSON for uploading to Google Play. Scope to `production` environment. |
| **iOS** | | | | | | |
| `IOS_DISTRIBUTION_CERTIFICATE_BASE64` | — | ✓ | ✓ | — | — | Apple Distribution or Development certificate (.p12), base64-encoded. |
| `IOS_DISTRIBUTION_CERTIFICATE_PASSWORD` | — | ✓ | ✓ | — | — | Password for the .p12 certificate file. |
| `IOS_PROVISIONING_PROFILE_BASE64` | — | ✓ | ✓ | — | — | Provisioning profile (.mobileprovision), base64-encoded. |
| **App Store Connect** | | | | | | |
| `APP_STORE_CONNECT_KEY_ID` | — | — | ✓ ⚙️ | — | ✓ | App Store Connect API Key ID. |
| `APP_STORE_CONNECT_ISSUER_ID` | — | — | ✓ ⚙️ | — | ✓ | App Store Connect API Issuer ID (UUID). |
| `APP_STORE_CONNECT_PRIVATE_KEY` | — | — | ✓ ⚙️ | — | ✓ | Private key (.p8 file contents) from App Store Connect. **High sensitivity.** |
| **Notifications** | | | | | | |
| `DISCORD_WEBHOOK_URL` | ○ | ○ | ○ | — | — | Discord webhook URL for build-completion notifications. Omit to disable silently. |

**Legend:**
- ✓ — Required for this context
- ○ — Optional or conditionally required
- — — Not applicable / not needed
- ⚙️ — Must be scoped to the `production` GitHub Environment (not repository-level)

---

## Column Definitions

| Column | When it applies |
|---|---|
| **Development** | Development builds (`keystoreMode: debug` for Android, `signingStyle: automatic` for iOS) |
| **Staging** | Staging/QA builds with real signing (ad-hoc iOS, signed AAB for Android) |
| **Production** | Release builds targeting stores (App Store, Google Play) — via `production` GitHub Environment |
| **Artifact-only** | CI builds that produce an artifact but do not sign or deploy (e.g., pull-request builds, nightly) |
| **Store-deploy** | The deploy step only: uploading a pre-built, pre-signed artifact to a store |

---

## Unity License Secrets

> Either `UNITY_LICENSE` (file-based activation) or the `UNITY_EMAIL` + `UNITY_PASSWORD` + `UNITY_SERIAL` combination is required.

```
UNITY_LICENSE        # Full content of your .ulf license file
UNITY_EMAIL          # Unity account email (floating/serial activation)
UNITY_PASSWORD       # Unity account password (floating/serial activation)
UNITY_SERIAL         # Unity serial number (Pro/Plus)
```

---

## Android Secrets

> Required when `android.keystoreMode` is `custom`. When `keystoreMode: debug`, only the Unity debug keystore is used and these secrets are not needed.

```
ANDROID_KEYSTORE_BASE64      # base64-encoded .jks or .keystore file
ANDROID_KEYSTORE_PASSWORD    # Keystore file password
ANDROID_KEY_ALIAS            # Alias of the signing key
ANDROID_KEY_PASSWORD         # Password for the key alias
```

Encode your keystore:
```bash
# macOS / Linux
base64 -w 0 my-release-key.keystore

# Windows PowerShell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("my-release-key.keystore"))
```

---

## Google Play Secrets

> Required for the store-deploy step only (uploading `.aab` to Google Play). Not needed to build or sign.

```
GOOGLE_PLAY_SERVICE_ACCOUNT_JSON    # Full JSON content of a Google Play service account key
```

Scope this secret to the `production` GitHub Environment.

---

## iOS Secrets

> Required when `iOS.signingStyle` is `manual` and for any distribution build.

```
IOS_DISTRIBUTION_CERTIFICATE_BASE64       # base64-encoded .p12 certificate
IOS_DISTRIBUTION_CERTIFICATE_PASSWORD     # .p12 export password
IOS_PROVISIONING_PROFILE_BASE64           # base64-encoded .mobileprovision file
```

Encode credentials:
```bash
base64 -w 0 Certificates.p12
base64 -w 0 MyApp_Distribution.mobileprovision
```

---

## App Store Connect Secrets

> Required for TestFlight uploads and App Store distribution. Scope all three to the `production` GitHub Environment.

```
APP_STORE_CONNECT_KEY_ID         # API key ID (e.g. ABCD1234EF)
APP_STORE_CONNECT_ISSUER_ID      # Issuer UUID (e.g. 12345678-1234-1234-1234-123456789012)
APP_STORE_CONNECT_PRIVATE_KEY    # Contents of the .p8 private key file
```

Generate in App Store Connect: **Users and Access → Integrations → App Store Connect API → Generate API Key**. The key can only be downloaded once.

---

## Notification Secrets

```
DISCORD_WEBHOOK_URL    # Discord Incoming Webhook URL — omit entirely to disable notifications
```

If `DISCORD_WEBHOOK_URL` is not set the notification step skips silently — no YAML changes needed to disable. See [docs/DISCORD_NOTIFICATIONS.md](../docs/DISCORD_NOTIFICATIONS.md).

---

## Secret Rotation Policy

| Secret | Rotation Frequency | Trigger for Immediate Rotation |
|---|---|---|
| `UNITY_LICENSE` | Per subscription renewal | License revocation |
| `ANDROID_KEYSTORE_*` | Annual | Departing team member, suspected compromise |
| `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` | Annual | Departing team member, role change |
| `IOS_DISTRIBUTION_CERTIFICATE_BASE64` | Annual (cert expiry) | Compromised private key, departing team member |
| `IOS_DISTRIBUTION_CERTIFICATE_PASSWORD` | On certificate rotation | — |
| `IOS_PROVISIONING_PROFILE_BASE64` | Annual (profile expiry) | Bundle ID change, team change |
| `APP_STORE_CONNECT_PRIVATE_KEY` | Annual | Compromised key, role change |
| `DISCORD_WEBHOOK_URL` | On channel deletion or suspected leak | Regenerate in Discord Server Settings |

---

## Security Notes

- Never commit actual secret values to any file in the repository.
- Use GitHub's [secret scanning](https://docs.github.com/en/code-security/secret-scanning) to catch accidental commits.
- Secrets are masked in workflow logs automatically by GitHub Actions.
- For fork PR safety, see [docs/SECURITY.md](../docs/SECURITY.md).
- `APP_STORE_CONNECT_*` secrets **must** be scoped to the `production` GitHub Environment, not repository-level — this prevents staging builds from accidentally uploading to TestFlight, and prevents forks from accessing production credentials.
