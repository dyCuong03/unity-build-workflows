using System;
using System.Collections.Generic;

namespace Company.BuildPipeline.Editor.Validation.Rules
{
    /// <summary>
    /// Detects non-production endpoint URLs (localhost, staging/dev hostnames) in a
    /// production build.  Checks all values in the <c>endpoints</c> dictionary.
    /// </summary>
    public class BUILD015_ProductionNonProdEndpoint : IBuildValidationRule
    {
        public string Id => "BUILD015";
        public ValidationSeverity Severity => ValidationSeverity.Error;

        private static readonly string[] NonProdIndicators =
        {
            "localhost", "127.0.0.1", "0.0.0.0",
            "staging", "stage", "stg",
            "dev.", "development",
            "test.", "testing",
            "qa.", "qa-",
            "sandbox",
            "internal",
            "local."
        };

        public ValidationResult Validate(BuildContext context)
        {
            var cfg = context.Configuration;

            bool isProduction = cfg.Environment?.Equals("production", StringComparison.OrdinalIgnoreCase) == true;
            if (!isProduction)
                return ValidationResult.Pass(Id, Severity, "Not a production environment — endpoint check skipped.");

            if (cfg.Endpoints == null || cfg.Endpoints.Count == 0)
                return ValidationResult.Pass(Id, Severity, "No endpoints configured.");

            var violations = new List<string>();

            foreach (var kv in cfg.Endpoints)
            {
                var url = kv.Value ?? string.Empty;
                foreach (var indicator in NonProdIndicators)
                {
                    if (url.IndexOf(indicator, StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        violations.Add($"'{kv.Key}': {url}");
                        break;
                    }
                }
            }

            if (violations.Count > 0)
                return ValidationResult.Fail(Id, Severity,
                    $"Production config contains non-production endpoint(s): {string.Join("; ", violations)}.");

            return ValidationResult.Pass(Id, Severity, "All endpoints appear production-safe.");
        }
    }
}
