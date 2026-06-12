using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using Company.BuildPipeline.Editor.Validation.Rules;

namespace Company.BuildPipeline.Editor
{
    /// <summary>
    /// Runs all registered <see cref="IBuildValidationRule"/> implementations and
    /// aggregates results into the <see cref="BuildContext"/>.
    /// </summary>
    public class BuildValidator
    {
        private readonly List<IBuildValidationRule> _rules;

        /// <summary>Creates a validator pre-loaded with all built-in rules.</summary>
        public BuildValidator()
        {
            _rules = new List<IBuildValidationRule>
            {
                new BUILD001_BootstrapSceneMissing(),
                new BUILD002_NoEnabledScenes(),
                new BUILD003_ProductionDevBuild(),
                new BUILD004_ProductionDebugging(),
                new BUILD005_InvalidAppIdentifier(),
                new BUILD006_AddressablesProfileMismatch(),
                new BUILD007_OutputPathOutsideWorkspace(),
                new BUILD008_UnsupportedScriptingBackend(),
                new BUILD009_VersionTagMismatch(),
                new BUILD010_MissingSigningConfig(),
                new BUILD011_DuplicateScenes(),
                new BUILD012_UnityVersionMismatch(),
                new BUILD013_ConfigSchemaViolation(),
                new BUILD014_RequiredHookFailed(),
                new BUILD015_ProductionNonProdEndpoint()
            };
        }

        /// <summary>Allows injecting custom or test rules.</summary>
        public BuildValidator(IEnumerable<IBuildValidationRule> rules)
        {
            _rules = rules.ToList();
        }

        /// <summary>
        /// Evaluates every rule, appends results to <see cref="BuildContext.ValidationResults"/>,
        /// and returns <c>false</c> if any Error-severity rule failed.
        /// </summary>
        public bool Validate(BuildContext context)
        {
            bool anyError = false;

            foreach (var rule in _rules)
            {
                ValidationResult result;
                try
                {
                    result = rule.Validate(context);
                }
                catch (Exception ex)
                {
                    result = ValidationResult.Fail(rule.Id, ValidationSeverity.Error,
                        $"Rule {rule.Id} threw an exception: {ex.Message}");
                }

                context.ValidationResults.Add(result);
                LogResult(result);

                if (!result.Passed && result.Severity == ValidationSeverity.Error)
                    anyError = true;
            }

            int errors = context.ValidationResults.Count(r => !r.Passed && r.Severity == ValidationSeverity.Error);
            int warnings = context.ValidationResults.Count(r => !r.Passed && r.Severity == ValidationSeverity.Warning);
            Debug.Log($"[BuildPipeline:Validation] Complete — {errors} error(s), {warnings} warning(s).");

            return !anyError;
        }

        private static void LogResult(ValidationResult r)
        {
            var prefix = $"[BuildPipeline:Validation] [{r.RuleId}]";
            if (r.Passed)
                Debug.Log($"{prefix} PASS — {r.Message}");
            else if (r.Severity == ValidationSeverity.Warning)
                Debug.LogWarning($"{prefix} WARN — {r.Message}");
            else
                Debug.LogError($"{prefix} FAIL — {r.Message}");
        }
    }
}
