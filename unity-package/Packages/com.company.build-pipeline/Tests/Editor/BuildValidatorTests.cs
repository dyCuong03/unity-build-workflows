using System.Collections.Generic;
using NUnit.Framework;
using Company.BuildPipeline.Editor;
using Company.BuildPipeline.Editor.Validation.Rules;
using UnityEditor;

namespace Company.BuildPipeline.Tests.Editor
{
    [TestFixture]
    public class BuildValidatorTests
    {
        // ── Factory helpers ───────────────────────────────────────────────────

        private static BuildContext MakeContext(BuildConfiguration cfg)
            => new BuildContext { Configuration = cfg, Target = BuildTarget.Android };

        private static BuildConfiguration BaseConfig() => new BuildConfiguration
        {
            ProductName    = "TestGame",
            CompanyName    = "TestCo",
            BundleVersion  = "1.0.0",
            AppIdentifier  = "com.test.game",
            TargetPlatform = "android",
            Environment    = "development",
            Scenes         = new List<string> { "Assets/Scenes/Bootstrap.unity", "Assets/Scenes/Main.unity" },
            BootstrapScene = "Assets/Scenes/Bootstrap.unity",
            ScriptingBackend = "Mono2x"
        };

        // ── BUILD001 ──────────────────────────────────────────────────────────

        [Test]
        public void BUILD001_Passes_WhenBootstrapSceneIsFirstScene()
        {
            var rule = new BUILD001_BootstrapSceneMissing();
            var cfg = BaseConfig();
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsTrue(result.Passed);
        }

        [Test]
        public void BUILD001_Fails_WhenBootstrapSceneIsEmpty()
        {
            var rule = new BUILD001_BootstrapSceneMissing();
            var cfg = BaseConfig();
            cfg.BootstrapScene = string.Empty;
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsFalse(result.Passed);
        }

        [Test]
        public void BUILD001_Fails_WhenBootstrapSceneIsNotFirstEntry()
        {
            var rule = new BUILD001_BootstrapSceneMissing();
            var cfg = BaseConfig();
            cfg.BootstrapScene = "Assets/Scenes/Main.unity"; // not index 0
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsFalse(result.Passed);
        }

        // ── BUILD002 ──────────────────────────────────────────────────────────

        [Test]
        public void BUILD002_Fails_WhenScenesListIsEmpty()
        {
            var rule = new BUILD002_NoEnabledScenes();
            var cfg = BaseConfig();
            cfg.Scenes = new List<string>();
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsFalse(result.Passed);
        }

        [Test]
        public void BUILD002_Passes_WithAtLeastOneScene()
        {
            var rule = new BUILD002_NoEnabledScenes();
            var result = rule.Validate(MakeContext(BaseConfig()));
            Assert.IsTrue(result.Passed);
        }

        // ── BUILD003 ──────────────────────────────────────────────────────────

        [Test]
        public void BUILD003_Fails_WhenProductionAndDevBuild()
        {
            var rule = new BUILD003_ProductionDevBuild();
            var cfg = BaseConfig();
            cfg.Environment = "production";
            cfg.IsDevelopmentBuild = true;
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsFalse(result.Passed);
        }

        [Test]
        public void BUILD003_Passes_WhenDevelopmentAndDevBuild()
        {
            var rule = new BUILD003_ProductionDevBuild();
            var cfg = BaseConfig();
            cfg.Environment = "development";
            cfg.IsDevelopmentBuild = true;
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsTrue(result.Passed);
        }

        // ── BUILD004 ──────────────────────────────────────────────────────────

        [Test]
        public void BUILD004_Fails_WhenProductionAndDebuggingEnabled()
        {
            var rule = new BUILD004_ProductionDebugging();
            var cfg = BaseConfig();
            cfg.Environment = "production";
            cfg.IsDebuggingEnabled = true;
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsFalse(result.Passed);
        }

        // ── BUILD005 ──────────────────────────────────────────────────────────

        [Test]
        public void BUILD005_Passes_WithValidIdentifier()
        {
            var rule = new BUILD005_InvalidAppIdentifier();
            var cfg = BaseConfig();
            cfg.AppIdentifier = "com.company.mygame";
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsTrue(result.Passed);
        }

        [Test]
        public void BUILD005_Fails_WithNoDotsInIdentifier()
        {
            var rule = new BUILD005_InvalidAppIdentifier();
            var cfg = BaseConfig();
            cfg.AppIdentifier = "invalid";
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsFalse(result.Passed);
        }

        [Test]
        public void BUILD005_Fails_WithEmptyIdentifier()
        {
            var rule = new BUILD005_InvalidAppIdentifier();
            var cfg = BaseConfig();
            cfg.AppIdentifier = string.Empty;
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsFalse(result.Passed);
        }

        // ── BUILD006 ──────────────────────────────────────────────────────────

        [Test]
        public void BUILD006_Passes_WhenProfileContainsEnvironment()
        {
            var rule = new BUILD006_AddressablesProfileMismatch();
            var cfg = BaseConfig();
            cfg.AddressablesProfile = "production-cdn";
            cfg.Environment = "production";
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsTrue(result.Passed);
        }

        [Test]
        public void BUILD006_Warns_WhenProfileDoesNotContainEnvironment()
        {
            var rule = new BUILD006_AddressablesProfileMismatch();
            var cfg = BaseConfig();
            cfg.AddressablesProfile = "production-cdn";
            cfg.Environment = "staging";
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsFalse(result.Passed);
            Assert.AreEqual(ValidationSeverity.Warning, result.Severity);
        }

        // ── BUILD007 ──────────────────────────────────────────────────────────

        [Test]
        public void BUILD007_Passes_WhenOutputIsInsideWorkspace()
        {
            var rule = new BUILD007_OutputPathOutsideWorkspace();
            var cfg = BaseConfig();
            cfg.Workspace = System.IO.Path.GetTempPath();
            cfg.OutputPath = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "Builds");
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsTrue(result.Passed);
        }

        [Test]
        public void BUILD007_Fails_WhenOutputIsOutsideWorkspace()
        {
            var rule = new BUILD007_OutputPathOutsideWorkspace();
            var cfg = BaseConfig();
            cfg.Workspace  = "/workspace";
            cfg.OutputPath = "/tmp/builds"; // outside workspace
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsFalse(result.Passed);
        }

        // ── BUILD008 ──────────────────────────────────────────────────────────

        [Test]
        public void BUILD008_Fails_WhenIosUsesMonoBackend()
        {
            var rule = new BUILD008_UnsupportedScriptingBackend();
            var cfg = BaseConfig();
            cfg.TargetPlatform = "ios";
            cfg.ScriptingBackend = "Mono2x";
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsFalse(result.Passed);
        }

        [Test]
        public void BUILD008_Passes_WhenIosUsesIL2CPP()
        {
            var rule = new BUILD008_UnsupportedScriptingBackend();
            var cfg = BaseConfig();
            cfg.TargetPlatform = "ios";
            cfg.ScriptingBackend = "il2cpp";
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsTrue(result.Passed);
        }

        // ── BUILD009 ──────────────────────────────────────────────────────────

        [Test]
        public void BUILD009_Passes_WhenTagMatchesVersion()
        {
            var rule = new BUILD009_VersionTagMismatch();
            var cfg = BaseConfig();
            cfg.ReleaseTag    = "v1.0.0";
            cfg.BundleVersion = "1.0.0";
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsTrue(result.Passed);
        }

        [Test]
        public void BUILD009_Warns_WhenTagDoesNotMatchVersion()
        {
            var rule = new BUILD009_VersionTagMismatch();
            var cfg = BaseConfig();
            cfg.ReleaseTag    = "v2.0.0";
            cfg.BundleVersion = "1.0.0";
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsFalse(result.Passed);
            Assert.AreEqual(ValidationSeverity.Warning, result.Severity);
        }

        // ── BUILD010 ──────────────────────────────────────────────────────────

        [Test]
        public void BUILD010_Fails_WhenAndroidMissingSigningConfig()
        {
            var rule = new BUILD010_MissingSigningConfig();
            var cfg = BaseConfig();
            cfg.TargetPlatform = "android";
            cfg.SigningConfig   = null;
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsFalse(result.Passed);
        }

        [Test]
        public void BUILD010_Passes_WhenAndroidHasFullSigningConfig()
        {
            var rule = new BUILD010_MissingSigningConfig();
            var cfg = BaseConfig();
            cfg.TargetPlatform = "android";
            cfg.SigningConfig   = new SigningConfiguration
            {
                KeystorePath = "my.keystore",
                KeystorePasswordEnvVar = "KEYSTORE_PASS",
                KeyAlias = "myalias"
            };
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsTrue(result.Passed);
        }

        // ── BUILD011 ──────────────────────────────────────────────────────────

        [Test]
        public void BUILD011_Fails_WhenScenesHasDuplicates()
        {
            var rule = new BUILD011_DuplicateScenes();
            var cfg = BaseConfig();
            cfg.Scenes = new List<string> { "A", "B", "A" };
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsFalse(result.Passed);
        }

        [Test]
        public void BUILD011_Passes_WhenAllScenesAreUnique()
        {
            var rule = new BUILD011_DuplicateScenes();
            var result = rule.Validate(MakeContext(BaseConfig()));
            Assert.IsTrue(result.Passed);
        }

        // ── BUILD013 ──────────────────────────────────────────────────────────

        [Test]
        public void BUILD013_Fails_WhenProductNameMissing()
        {
            var rule = new BUILD013_ConfigSchemaViolation();
            var cfg = BaseConfig();
            cfg.ProductName = string.Empty;
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsFalse(result.Passed);
        }

        [Test]
        public void BUILD013_Passes_WithAllRequiredFields()
        {
            var rule = new BUILD013_ConfigSchemaViolation();
            var result = rule.Validate(MakeContext(BaseConfig()));
            Assert.IsTrue(result.Passed);
        }

        // ── BUILD014 ──────────────────────────────────────────────────────────

        [Test]
        public void BUILD014_Fails_WhenRequiredHookNotRegistered()
        {
            var rule = new BUILD014_RequiredHookFailed();
            var cfg = BaseConfig();
            cfg.RequiredHooks = new List<string> { "NonExistentHook" };

            var ctx = MakeContext(cfg);
            ctx.Metadata["hookRegistry"] = new BuildHookRegistry(new List<IBuildHook>());

            var result = rule.Validate(ctx);
            Assert.IsFalse(result.Passed);
        }

        [Test]
        public void BUILD014_Passes_WhenNoRequiredHooks()
        {
            var rule = new BUILD014_RequiredHookFailed();
            var cfg = BaseConfig();
            cfg.RequiredHooks = new List<string>();

            var ctx = MakeContext(cfg);
            ctx.Metadata["hookRegistry"] = new BuildHookRegistry(new List<IBuildHook>());

            var result = rule.Validate(ctx);
            Assert.IsTrue(result.Passed);
        }

        // ── BUILD015 ──────────────────────────────────────────────────────────

        [Test]
        public void BUILD015_Fails_WhenProductionConfigHasStagingEndpoint()
        {
            var rule = new BUILD015_ProductionNonProdEndpoint();
            var cfg = BaseConfig();
            cfg.Environment = "production";
            cfg.Endpoints = new Dictionary<string, string> { { "api", "https://staging.example.com/api" } };
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsFalse(result.Passed);
        }

        [Test]
        public void BUILD015_Fails_WhenProductionConfigHasLocalhostEndpoint()
        {
            var rule = new BUILD015_ProductionNonProdEndpoint();
            var cfg = BaseConfig();
            cfg.Environment = "production";
            cfg.Endpoints = new Dictionary<string, string> { { "api", "http://localhost:8080" } };
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsFalse(result.Passed);
        }

        [Test]
        public void BUILD015_Passes_WhenProductionConfigHasProductionEndpoints()
        {
            var rule = new BUILD015_ProductionNonProdEndpoint();
            var cfg = BaseConfig();
            cfg.Environment = "production";
            cfg.Endpoints = new Dictionary<string, string> { { "api", "https://api.example.com" } };
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsTrue(result.Passed);
        }

        [Test]
        public void BUILD015_Passes_ForNonProductionEnvironment()
        {
            var rule = new BUILD015_ProductionNonProdEndpoint();
            var cfg = BaseConfig();
            cfg.Environment = "staging";
            cfg.Endpoints = new Dictionary<string, string> { { "api", "http://localhost:8080" } };
            var result = rule.Validate(MakeContext(cfg));
            Assert.IsTrue(result.Passed, "Non-prod endpoints are allowed in non-production environments.");
        }

        // ── BuildValidator integration ────────────────────────────────────────

        [Test]
        public void BuildValidator_ReturnsFalse_WhenAnyErrorRuleFails()
        {
            var cfg = BaseConfig();
            cfg.Scenes = new List<string>(); // will trigger BUILD002

            var ctx = MakeContext(cfg);
            ctx.Metadata["hookRegistry"] = new BuildHookRegistry(new List<IBuildHook>());

            var validator = new BuildValidator();
            var passed = validator.Validate(ctx);

            Assert.IsFalse(passed);
        }

        [Test]
        public void BuildValidator_ReturnsTrue_WhenAllRulesPass()
        {
            var cfg = BaseConfig();
            cfg.Workspace = System.IO.Path.GetTempPath();
            cfg.OutputPath = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "Builds");
            cfg.SigningConfig = new SigningConfiguration
            {
                KeystorePath = "my.keystore",
                KeystorePasswordEnvVar = "KEYSTORE_PASS",
                KeyAlias = "myalias"
            };

            var ctx = MakeContext(cfg);
            ctx.Metadata["hookRegistry"] = new BuildHookRegistry(new List<IBuildHook>());

            var validator = new BuildValidator();
            var passed = validator.Validate(ctx);

            Assert.IsTrue(passed);
        }
    }
}
