using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;
using UnityEngine;

namespace Company.BuildPipeline.Editor
{
    /// <summary>
    /// Generates a <c>build-metadata.json</c> file containing the stable, machine-readable
    /// summary of a build.  This file is intended for downstream CI steps (e.g. upload,
    /// notification, deployment) to consume without parsing build logs.
    /// </summary>
    public class BuildMetadataWriter
    {
        public void Write(BuildContext context)
        {
            var cfg = context.Configuration;
            var result = context.ExecutionResult;
            var outputDir = cfg.OutputPath;
            Directory.CreateDirectory(outputDir);

            var metadata = new Dictionary<string, object>
            {
                ["schemaVersion"] = "1.0",
                ["buildTime"]     = context.BuildStartedAt.ToString("o"),
                ["environment"]   = cfg.Environment,
                ["targetPlatform"] = cfg.TargetPlatform,
                ["productName"]   = cfg.ProductName,
                ["appIdentifier"] = cfg.AppIdentifier,
                ["bundleVersion"] = cfg.BundleVersion,
                ["releaseTag"]    = cfg.ReleaseTag ?? string.Empty,
                ["unityVersion"]  = Application.unityVersion,
                ["success"]       = result?.Success ?? false,
                ["durationSeconds"] = result?.Duration.TotalSeconds ?? 0,
                ["outputPath"]    = result?.OutputPath ?? string.Empty,
                ["outputSizeBytes"] = result?.OutputSizeBytes ?? 0,
                ["warningCount"]  = result?.WarningCount ?? 0,
                ["validationErrors"] = CountValidationResults(context, ValidationSeverity.Error, passed: false),
                ["validationWarnings"] = CountValidationResults(context, ValidationSeverity.Warning, passed: false),
                ["gitCommit"]     = GetEnv("GIT_COMMIT", GetEnv("GITHUB_SHA", "unknown")),
                ["gitBranch"]     = GetEnv("GIT_BRANCH", GetEnv("GITHUB_REF_NAME", "unknown")),
                ["buildNumber"]   = GetEnv("BUILD_NUMBER", GetEnv("GITHUB_RUN_NUMBER", "0")),
                ["ciPipeline"]    = GetEnv("CI_PIPELINE_ID", GetEnv("GITHUB_RUN_ID", "local")),
            };

            // Merge any extra metadata collected by hooks.
            foreach (var kv in context.Metadata)
            {
                if (kv.Value is BuildHookRegistry) continue;
                if (!metadata.ContainsKey(kv.Key))
                    metadata[kv.Key] = kv.Value;
            }

            var json = JsonConvert.SerializeObject(metadata, Formatting.Indented);
            var path = Path.Combine(outputDir, "build-metadata.json");
            File.WriteAllText(path, json);
            Debug.Log($"[BuildPipeline:Metadata] build-metadata.json written to {path}");
        }

        private static int CountValidationResults(BuildContext ctx, ValidationSeverity severity, bool passed)
        {
            int count = 0;
            foreach (var r in ctx.ValidationResults)
                if (r.Severity == severity && r.Passed == passed) count++;
            return count;
        }

        private static string GetEnv(string name, string fallback = "")
            => Environment.GetEnvironmentVariable(name) ?? fallback;
    }
}
