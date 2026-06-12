using System;
using System.Collections.Generic;
using UnityEditor;

namespace Company.BuildPipeline.Editor.Validation.Rules
{
    /// <summary>
    /// Ensures the scripting backend is valid for the target platform.
    /// iOS only supports IL2CPP. WebGL only supports IL2CPP. Android supports Mono2x and IL2CPP.
    /// </summary>
    public class BUILD008_UnsupportedScriptingBackend : IBuildValidationRule
    {
        public string Id => "BUILD008";
        public ValidationSeverity Severity => ValidationSeverity.Error;

        // platform name (lower) -> allowed backends (lower)
        private static readonly Dictionary<string, HashSet<string>> AllowedBackends =
            new Dictionary<string, HashSet<string>>(StringComparer.OrdinalIgnoreCase)
            {
                { "ios",     new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "il2cpp" } },
                { "webgl",   new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "il2cpp" } },
                { "android", new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "mono2x", "il2cpp" } },
                { "windows", new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "mono2x", "il2cpp" } },
            };

        public ValidationResult Validate(BuildContext context)
        {
            var cfg = context.Configuration;
            var platform = cfg.TargetPlatform;
            var backend  = cfg.ScriptingBackend;

            if (string.IsNullOrWhiteSpace(platform) || string.IsNullOrWhiteSpace(backend))
                return ValidationResult.Pass(Id, Severity, "targetPlatform or scriptingBackend not set — skipping.");

            if (!AllowedBackends.TryGetValue(platform, out var allowed))
                return ValidationResult.Pass(Id, Severity, $"No backend restrictions defined for platform '{platform}'.");

            if (!allowed.Contains(backend))
                return ValidationResult.Fail(Id, Severity,
                    $"Scripting backend '{backend}' is not supported on '{platform}'. Allowed: {string.Join(", ", allowed)}.");

            return ValidationResult.Pass(Id, Severity, $"Scripting backend '{backend}' is valid for '{platform}'.");
        }
    }
}
