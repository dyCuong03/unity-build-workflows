using System;
using UnityEngine;

namespace Company.BuildPipeline.Editor.Validation.Rules
{
    /// <summary>
    /// Verifies that the running Unity version matches the version specified in the build config.
    /// A mismatch can produce non-reproducible builds.
    /// </summary>
    public class BUILD012_UnityVersionMismatch : IBuildValidationRule
    {
        public string Id => "BUILD012";
        public ValidationSeverity Severity => ValidationSeverity.Warning;

        public ValidationResult Validate(BuildContext context)
        {
            var required = context.Configuration.UnityVersion;

            if (string.IsNullOrWhiteSpace(required))
                return ValidationResult.Pass(Id, Severity, "unityVersion not configured — skipping version check.");

            var running = Application.unityVersion;

            if (!string.Equals(running, required, StringComparison.OrdinalIgnoreCase))
                return ValidationResult.Fail(Id, Severity,
                    $"Unity version mismatch: running '{running}', required '{required}'.");

            return ValidationResult.Pass(Id, Severity, $"Unity version '{running}' matches requirement.");
        }
    }
}
