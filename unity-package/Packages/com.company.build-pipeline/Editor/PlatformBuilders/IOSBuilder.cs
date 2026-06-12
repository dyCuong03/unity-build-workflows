using System;
using System.IO;
using UnityEditor;
using UnityEditor.iOS.Xcode;
using UnityEngine;

namespace Company.BuildPipeline.Editor
{
    public class IOSBuilder : IPlatformBuilder
    {
        public BuildTarget Target => BuildTarget.iOS;

        public bool Supports(BuildContext context)
            => context.Configuration.TargetPlatform.Equals("ios", StringComparison.OrdinalIgnoreCase);

        public void Configure(BuildContext context)
        {
            var cfg = context.Configuration;

            PlayerSettings.productName = cfg.ProductName;
            PlayerSettings.companyName = cfg.CompanyName;
            PlayerSettings.bundleVersion = cfg.BundleVersion;
            PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.iOS, cfg.AppIdentifier);

            // iOS only supports IL2CPP.
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.iOS, ScriptingImplementation.IL2CPP);

            var signing = cfg.SigningConfig;
            if (signing != null)
            {
                if (!string.IsNullOrWhiteSpace(signing.TeamId))
                    PlayerSettings.iOS.appleDeveloperTeamID = signing.TeamId;

                if (!string.IsNullOrWhiteSpace(signing.ProvisioningProfileId))
                {
                    PlayerSettings.iOS.iOSManualProvisioningProfileID = signing.ProvisioningProfileId;
                    PlayerSettings.iOS.appleEnableAutomaticSigning = false;
                }

                if (!string.IsNullOrWhiteSpace(signing.CodeSignIdentity))
                    PlayerSettings.iOS.iOSManualProvisioningProfileType = ProvisioningProfileType.Distribution;
            }

            PlayerSettings.iOS.buildNumber = cfg.BundleVersion;
        }

        public BuildExecutionResult Build(BuildContext context)
        {
            var cfg = context.Configuration;
            var outputPath = cfg.OutputPath;
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath) ?? outputPath);

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

            return new BuildExecutionResult
            {
                Success = success,
                ErrorMessage = success ? string.Empty : report.summary.result.ToString(),
                WarningCount = (int)report.summary.totalWarnings,
                Duration = duration,
                OutputPath = outputPath,
                OutputSizeBytes = 0  // Xcode project output; size reported post-archive
            };
        }
    }
}
