using System;
using System.Collections.Generic;

namespace Company.BuildPipeline.Editor.Validation.Rules
{
    /// <summary>
    /// Verifies that every hook type name listed in <c>requiredHooks</c> has been registered
    /// in the <see cref="BuildHookRegistry"/>.  The registry must be stored in
    /// <c>context.Metadata["hookRegistry"]</c> before validation runs.
    /// </summary>
    public class BUILD014_RequiredHookFailed : IBuildValidationRule
    {
        public string Id => "BUILD014";
        public ValidationSeverity Severity => ValidationSeverity.Error;

        public ValidationResult Validate(BuildContext context)
        {
            var required = context.Configuration.RequiredHooks;

            if (required == null || required.Count == 0)
                return ValidationResult.Pass(Id, Severity, "No required hooks configured.");

            if (!context.Metadata.TryGetValue("hookRegistry", out var registryObj) ||
                registryObj is not BuildHookRegistry registry)
                return ValidationResult.Fail(Id, Severity,
                    "hookRegistry not found in BuildContext.Metadata. Cannot verify required hooks.");

            var registered = new HashSet<string>(registry.RegisteredTypeNames(), StringComparer.OrdinalIgnoreCase);
            var missing = new List<string>();

            foreach (var hookName in required)
                if (!registered.Contains(hookName))
                    missing.Add(hookName);

            if (missing.Count > 0)
                return ValidationResult.Fail(Id, Severity,
                    $"Required hook(s) not registered: {string.Join(", ", missing)}.");

            return ValidationResult.Pass(Id, Severity, "All required hooks are registered.");
        }
    }
}
