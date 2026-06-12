using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using Newtonsoft.Json;
using UnityEngine;

namespace Company.BuildPipeline.Editor
{
    /// <summary>
    /// Exports build results as JSON and Markdown reports to the output directory.
    /// </summary>
    public class BuildReportExporter
    {
        public void Export(BuildContext context)
        {
            var outputDir = context.Configuration.OutputPath;
            Directory.CreateDirectory(outputDir);

            ExportJson(context, outputDir);
            ExportMarkdown(context, outputDir);
        }

        // ── JSON ──────────────────────────────────────────────────────────────

        private static void ExportJson(BuildContext context, string outputDir)
        {
            var cfg = context.Configuration;
            var result = context.ExecutionResult;

            var payload = new
            {
                buildTime = context.BuildStartedAt.ToString("o"),
                environment = cfg.Environment,
                targetPlatform = cfg.TargetPlatform,
                bundleVersion = cfg.BundleVersion,
                releaseTag = cfg.ReleaseTag,
                success = result?.Success ?? false,
                errorMessage = result?.ErrorMessage ?? string.Empty,
                warningCount = result?.WarningCount ?? 0,
                durationSeconds = result?.Duration.TotalSeconds ?? 0,
                outputPath = result?.OutputPath ?? string.Empty,
                outputSizeBytes = result?.OutputSizeBytes ?? 0,
                validation = context.ValidationResults.Select(r => new
                {
                    ruleId = r.RuleId,
                    severity = r.Severity.ToString(),
                    passed = r.Passed,
                    message = r.Message
                }),
                metadata = context.Metadata
                    .Where(kv => !(kv.Value is BuildHookRegistry)) // don't serialise registry object
                    .ToDictionary(kv => kv.Key, kv => kv.Value)
            };

            var json = JsonConvert.SerializeObject(payload, Formatting.Indented);
            var path = Path.Combine(outputDir, "build-report.json");
            File.WriteAllText(path, json);
            Debug.Log($"[BuildPipeline:Report] JSON report written to {path}");
        }

        // ── Markdown ──────────────────────────────────────────────────────────

        private static void ExportMarkdown(BuildContext context, string outputDir)
        {
            var cfg = context.Configuration;
            var result = context.ExecutionResult;
            var sb = new StringBuilder();

            sb.AppendLine("# Build Report");
            sb.AppendLine();
            sb.AppendLine($"| Field | Value |");
            sb.AppendLine($"|---|---|");
            sb.AppendLine($"| Build Time | {context.BuildStartedAt:u} |");
            sb.AppendLine($"| Environment | `{cfg.Environment}` |");
            sb.AppendLine($"| Target Platform | `{cfg.TargetPlatform}` |");
            sb.AppendLine($"| Bundle Version | `{cfg.BundleVersion}` |");
            sb.AppendLine($"| Release Tag | `{cfg.ReleaseTag}` |");
            sb.AppendLine($"| Result | **{(result?.Success == true ? "SUCCESS" : "FAILURE")}** |");
            if (result != null)
            {
                sb.AppendLine($"| Duration | {result.Duration.TotalSeconds:F1}s |");
                sb.AppendLine($"| Warnings | {result.WarningCount} |");
                sb.AppendLine($"| Output Size | {FormatBytes(result.OutputSizeBytes)} |");
                sb.AppendLine($"| Output Path | `{result.OutputPath}` |");
                if (!string.IsNullOrWhiteSpace(result.ErrorMessage))
                    sb.AppendLine($"| Error | {result.ErrorMessage} |");
            }

            sb.AppendLine();
            sb.AppendLine("## Validation Results");
            sb.AppendLine();
            sb.AppendLine("| Rule | Severity | Status | Message |");
            sb.AppendLine("|---|---|---|---|");
            foreach (var r in context.ValidationResults)
            {
                var status = r.Passed ? "PASS" : (r.Severity == ValidationSeverity.Error ? "FAIL" : "WARN");
                sb.AppendLine($"| {r.RuleId} | {r.Severity} | {status} | {r.Message} |");
            }

            var path = Path.Combine(outputDir, "build-report.md");
            File.WriteAllText(path, sb.ToString());
            Debug.Log($"[BuildPipeline:Report] Markdown report written to {path}");
        }

        private static string FormatBytes(long bytes)
        {
            if (bytes < 1024) return $"{bytes} B";
            if (bytes < 1024 * 1024) return $"{bytes / 1024.0:F1} KB";
            if (bytes < 1024L * 1024 * 1024) return $"{bytes / (1024.0 * 1024):F1} MB";
            return $"{bytes / (1024.0 * 1024 * 1024):F2} GB";
        }
    }
}
