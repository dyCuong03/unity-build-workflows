using System;
using System.Collections.Generic;
using UnityEditor;

namespace Company.BuildPipeline.Editor
{
    /// <summary>
    /// Carries all state throughout a single build invocation.
    /// Created once by BuildCommand.Execute and passed to every subsystem.
    /// </summary>
    public class BuildContext
    {
        // ── Config ────────────────────────────────────────────────────────────

        public BuildConfiguration Configuration { get; set; }

        // ── Resolved values (may differ from raw config after CLI overrides) ──

        public string Environment => Configuration?.Environment ?? string.Empty;
        public string OutputPath => Configuration?.OutputPath ?? string.Empty;
        public string Workspace => Configuration?.Workspace ?? string.Empty;
        public string ReleaseTag => Configuration?.ReleaseTag ?? string.Empty;

        // ── Unity build target ────────────────────────────────────────────────

        public BuildTarget Target { get; set; }

        // ── Validation ────────────────────────────────────────────────────────

        public List<ValidationResult> ValidationResults { get; } = new List<ValidationResult>();

        // ── Execution result (populated after build) ──────────────────────────

        public BuildExecutionResult ExecutionResult { get; set; }

        // ── Timing ────────────────────────────────────────────────────────────

        public DateTime BuildStartedAt { get; } = DateTime.UtcNow;

        // ── Arbitrary metadata bag (for hooks / reporters) ────────────────────

        public Dictionary<string, object> Metadata { get; } = new Dictionary<string, object>();
    }

    /// <summary>
    /// Outcome of a single platform build attempt.
    /// </summary>
    public class BuildExecutionResult
    {
        public bool Success { get; set; }
        public string ErrorMessage { get; set; } = string.Empty;
        public int WarningCount { get; set; }
        public TimeSpan Duration { get; set; }
        public string OutputPath { get; set; } = string.Empty;
        public long OutputSizeBytes { get; set; }
    }
}
