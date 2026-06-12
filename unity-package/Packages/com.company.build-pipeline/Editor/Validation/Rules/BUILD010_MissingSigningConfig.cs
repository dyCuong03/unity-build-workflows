using System;

namespace Company.BuildPipeline.Editor.Validation.Rules
{
    /// <summary>
    /// Ensures platform-specific signing configuration is present for platforms that require it.
    /// Android requires keystorePath + keystorePasswordEnvVar + keyAlias.
    /// iOS requires teamId + provisioningProfileId.
    /// </summary>
    public class BUILD010_MissingSigningConfig : IBuildValidationRule
    {
        public string Id => "BUILD010";
        public ValidationSeverity Severity => ValidationSeverity.Error;

        public ValidationResult Validate(BuildContext context)
        {
            var cfg = context.Configuration;
            var platform = cfg.TargetPlatform;

            if (string.IsNullOrWhiteSpace(platform))
                return ValidationResult.Pass(Id, Severity, "No targetPlatform — skipping signing check.");

            bool isAndroid = platform.Equals("android", StringComparison.OrdinalIgnoreCase);
            bool isIos     = platform.Equals("ios", StringComparison.OrdinalIgnoreCase);

            if (!isAndroid && !isIos)
                return ValidationResult.Pass(Id, Severity, $"Platform '{platform}' does not require signing config.");

            var signing = cfg.SigningConfig;

            if (signing == null)
                return ValidationResult.Fail(Id, Severity,
                    $"Platform '{platform}' requires a signingConfig block, but none was provided.");

            if (isAndroid)
            {
                if (string.IsNullOrWhiteSpace(signing.KeystorePath))
                    return ValidationResult.Fail(Id, Severity, "signingConfig.keystorePath is missing for Android.");
                if (string.IsNullOrWhiteSpace(signing.KeystorePasswordEnvVar))
                    return ValidationResult.Fail(Id, Severity, "signingConfig.keystorePasswordEnvVar is missing for Android.");
                if (string.IsNullOrWhiteSpace(signing.KeyAlias))
                    return ValidationResult.Fail(Id, Severity, "signingConfig.keyAlias is missing for Android.");
            }

            if (isIos)
            {
                if (string.IsNullOrWhiteSpace(signing.TeamId))
                    return ValidationResult.Fail(Id, Severity, "signingConfig.teamId is missing for iOS.");
                if (string.IsNullOrWhiteSpace(signing.ProvisioningProfileId))
                    return ValidationResult.Fail(Id, Severity, "signingConfig.provisioningProfileId is missing for iOS.");
            }

            return ValidationResult.Pass(Id, Severity, $"Signing config present and complete for '{platform}'.");
        }
    }
}
