# Build Secrets Reference

This document lists every secret and variable that the unity-build-workflows pipelines read from GitHub repository or environment secrets. No actual secret values are stored here — this file is safe to commit.

Configure secrets under **Settings → Secrets and variables → Actions** in your GitHub repository, or at the organization level for shared secrets.

---

## Universal Secrets (all platforms)

| Secret Name | Required | Description |
|---|---|---|
| `UNITY_LICENSE` | Yes | Contents of your Unity `.ulf` license file, base64-encoded. For Unity Personal/Plus/Pro. |
| `UNITY_EMAIL` | Yes* | Email address of the Unity account. Required when activating a floating license. |
| `UNITY_PASSWORD` | Yes* | Password of the Unity account. Required when activating a floating license. |
| `UNITY_SERIAL` | Yes* | Unity serial number. Required for Pro/Plus serial activation. |

> *Either `UNITY_LICENSE` (file-based) or the email/password/serial combination must be provided.

---

## Android Secrets

| Secret Name | Required | Description |
|---|---|---|
| `ANDROID_KEYSTORE_BASE64` | Yes (production) | Android keystore file, base64-encoded. Run: `base64 -w 0 my.keystore` |
| `ANDROID_KEYSTORE_PASSWORD` | Yes (production) | Password for the keystore file. |
| `ANDROID_KEY_ALIAS` | Yes (production) | Alias of the signing key inside the keystore. |
| `ANDROID_KEY_PASSWORD` | Yes (production) | Password for the key alias. |

> When `keystoreMode` is `debug`, only the Unity debug keystore is used and these secrets are not needed.

---

## iOS Secrets

| Secret Name | Required | Description |
|---|---|---|
| `IOS_CERTIFICATE_BASE64` | Yes | Apple Distribution or Development certificate (.p12), base64-encoded. |
| `IOS_CERTIFICATE_PASSWORD` | Yes | Password for the .p12 certificate. |
| `IOS_PROVISIONING_PROFILE_BASE64` | Yes | Provisioning profile (.mobileprovision), base64-encoded. |
| `APPLE_CONNECT_API_KEY_ID` | Yes (App Store) | App Store Connect API Key ID. |
| `APPLE_CONNECT_API_ISSUER_ID` | Yes (App Store) | App Store Connect API Issuer ID (UUID). |
| `APPLE_CONNECT_API_KEY_P8_BASE64` | Yes (App Store) | Private key (.p8) from App Store Connect, base64-encoded. |

> When `automaticSigning` is `true`, manual certificate/profile secrets are replaced by Xcode's automatic signing using your Development Team. The App Store Connect API keys are still required for `exportMethod: app-store` uploads.

---

## Notification Secrets (optional)

| Secret Name | Required | Description |
|---|---|---|
| `SLACK_WEBHOOK_URL` | No | Incoming Webhook URL for Slack build notifications. |
| `DISCORD_WEBHOOK_URL` | No | Discord webhook for build notifications. |

---

## Cloud Distribution Secrets (optional)

| Secret Name | Required | Description |
|---|---|---|
| `FIREBASE_APP_ID_ANDROID` | No | Firebase App ID for Android distribution via Firebase App Distribution. |
| `FIREBASE_APP_ID_IOS` | No | Firebase App ID for iOS distribution. |
| `FIREBASE_TOKEN` | No | Firebase CI token (`firebase login:ci`). |

---

## How to Base64-Encode Files

**Linux/macOS:**
```bash
base64 -w 0 my.keystore | pbcopy   # macOS
base64 -w 0 my.keystore            # Linux (copy from output)
```

**Windows PowerShell:**
```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("my.keystore")) | Set-Clipboard
```

---

## Secret Rotation Policy

1. Android keystore: Rotate annually or immediately after any team member with access departs.
2. iOS certificates: Rotate before the certificate expiry date (typically 1 year). Check in Apple Developer portal.
3. App Store Connect API keys: Revoke and regenerate when a team member with access departs.
4. Unity license: Renew per Unity subscription terms.

---

## Security Notes

- Never commit actual secret values to any file in the repository.
- Use GitHub's [secret scanning](https://docs.github.com/en/code-security/secret-scanning) to catch accidental commits.
- For fork PR safety, see [docs/SECURITY.md](../docs/SECURITY.md).
- Secrets are masked in workflow logs automatically by GitHub Actions.
