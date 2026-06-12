using System;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace Company.BuildPipeline.Editor
{
    public class AndroidBuilder : IPlatformBuilder
    {
        public BuildTarget Target => BuildTarget.Android;

        public bool Supports(BuildContext context)
            => context.Configuration.TargetPlatform.Equals("android", StringComparison.OrdinalIgnoreCase);

        public void Configure(BuildContext context)
        {
            var cfg = context.Configuration;

            PlayerSettings.productName = cfg.ProductName;
            PlayerSettings.companyName = cfg.CompanyName;
            PlayerSettings.bundleVersion = cfg.BundleVersion;
            PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, cfg.AppIdentifier);

            var backend = cfg.ScriptingBackend?.Equals("il2cpp", StringComparison.OrdinalIgnoreCase) == true
                ? ScriptingImplementation.IL2CPP
                : ScriptingImplementation.Mono2x;
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, backend);

            if (backend == ScriptingImplementation.IL2CPP)
            {
                PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64 | AndroidArchitecture.ARMv7;
            }

            // Signing
            var signing = cfg.SigningConfig;
            if (signing != null && !string.IsNullOrWhiteSpace(signing.KeystorePath))
            {
                PlayerSettings.Android.useCustomKeystore = true;
                PlayerSettings.Android.keystoreName = signing.KeystorePath;

                if (!string.IsNullOrWhiteSpace(signing.KeystorePasswordEnvVar))
                    PlayerSettings.Android.keystorePass = Environment.GetEnvironmentVariable(signing.KeystorePasswordEnvVar) ?? string.Empty;

                PlayerSettings.Android.keyaliasName = signing.KeyAlias;

                if (!string.IsNullOrWhiteSpace(signing.KeyAliasPasswordEnvVar))
                    PlayerSettings.Android.keyaliasPass = Environment.GetEnvironmentVariable(signing.KeyAliasPasswordEnvVar) ?? string.Empty;
            }

            // Build number from bundle version (strip non-numeric segments).
            if (int.TryParse(cfg.BundleVersion.Split('.')[0], out int major))
                PlayerSettings.Android.bundleVersionCode = major;

            EditorUserBuildSettings.buildAppBundle = false; // AAB can be toggled via hook if needed
        }

        public BuildExecutionResult Build(BuildContext context)
        {
            var cfg = context.Configuration;
            var outputDir = cfg.OutputPath;
            Directory.CreateDirectory(outputDir);
            var outputPath = Path.Combine(outputDir, $"{cfg.ProductName}.apk");

            var options = new BuildPlayerOptions
            {
                scenes = cfg.Scenes.ToArray(),
                locationPathName = outputPath,
                target = Target,
                options = cfg.IsDevelopmentBuild
                    ? BuildOptions.Development | (cfg.IsDebuggingEnabled ? BuildOptions.AllowDebugging : BuildOptions.None)
                    : BuildOptions.None
            };

            var started = DateTime.UtcNow;
            var report = BuildPipeline.BuildPlayer(options);
            var duration = DateTime.UtcNow - started;

            bool success = report.summary.result == UnityEditor.Build.Reporting.BuildResult.Succeeded;
            long sizeBytes = success && File.Exists(outputPath) ? new FileInfo(outputPath).Length : 0;

            return new BuildExecutionResult
            {
                Success = success,
                ErrorMessage = success ? string.Empty : report.summary.result.ToString(),
                WarningCount = (int)report.summary.totalWarnings,
                Duration = duration,
                OutputPath = outputPath,
                OutputSizeBytes = sizeBytes
            };
        }
    }
}
