using System.Collections.Generic;
using System.IO;
using NUnit.Framework;
using Company.BuildPipeline.Editor;
using Newtonsoft.Json.Linq;

namespace Company.BuildPipeline.Tests.Editor
{
    [TestFixture]
    public class BuildConfigurationLoaderTests
    {
        private string _tempDir;
        private BuildConfigurationLoader _loader;

        [SetUp]
        public void SetUp()
        {
            _tempDir = Path.Combine(Path.GetTempPath(), "BuildPipelineTests", System.Guid.NewGuid().ToString());
            Directory.CreateDirectory(_tempDir);
            Directory.CreateDirectory(Path.Combine(_tempDir, "environments"));
            _loader = new BuildConfigurationLoader();
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tempDir))
                Directory.Delete(_tempDir, recursive: true);
        }

        // ── Helper ────────────────────────────────────────────────────────────

        private void WriteJson(string relativePath, object obj)
        {
            var path = Path.Combine(_tempDir, relativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, Newtonsoft.Json.JsonConvert.SerializeObject(obj));
        }

        // ── Tests ─────────────────────────────────────────────────────────────

        [Test]
        public void Load_BaseJsonOnly_ReturnsBaseValues()
        {
            WriteJson("base.json", new { productName = "MyGame", bundleVersion = "1.0.0", targetPlatform = "android" });

            var config = _loader.Load(_tempDir, environment: null);

            Assert.AreEqual("MyGame", config.ProductName);
            Assert.AreEqual("1.0.0", config.BundleVersion);
            Assert.AreEqual("android", config.TargetPlatform);
        }

        [Test]
        public void Load_EnvironmentJson_OverridesBaseValues()
        {
            WriteJson("base.json", new { productName = "MyGame", bundleVersion = "1.0.0", isDevelopmentBuild = false });
            WriteJson("environments/staging.json", new { isDevelopmentBuild = true, outputPath = "Builds/staging" });

            var config = _loader.Load(_tempDir, environment: "staging");

            Assert.IsTrue(config.IsDevelopmentBuild);
            Assert.AreEqual("Builds/staging", config.OutputPath);
            Assert.AreEqual("MyGame", config.ProductName); // Base value preserved
        }

        [Test]
        public void Load_CliOverrides_TakePrecedenceOverEnvironment()
        {
            WriteJson("base.json", new { productName = "MyGame", outputPath = "Builds/base" });
            WriteJson("environments/production.json", new { outputPath = "Builds/production" });

            var cli = new Dictionary<string, string> { { "outputPath", "Builds/override" } };
            var config = _loader.Load(_tempDir, environment: "production", cliOverrides: cli);

            Assert.AreEqual("Builds/override", config.OutputPath);
        }

        [Test]
        public void Load_StampsEnvironmentField()
        {
            WriteJson("base.json", new { productName = "MyGame" });

            var config = _loader.Load(_tempDir, environment: "staging");

            Assert.AreEqual("staging", config.Environment);
        }

        [Test]
        public void Load_MissingBaseJson_ReturnsDefaults()
        {
            // No base.json — loader should not throw; returns code defaults.
            var config = _loader.Load(_tempDir, environment: null);

            Assert.IsNotNull(config);
        }

        [Test]
        public void DeepMerge_OverwritesScalars()
        {
            var target = new JObject { ["key"] = "original", ["other"] = "keep" };
            var patch  = new JObject { ["key"] = "updated" };

            BuildConfigurationLoader.DeepMerge(target, patch);

            Assert.AreEqual("updated", target["key"]?.ToString());
            Assert.AreEqual("keep", target["other"]?.ToString());
        }

        [Test]
        public void DeepMerge_RecursivelyMergesObjects()
        {
            var target = new JObject
            {
                ["signingConfig"] = new JObject { ["keystorePath"] = "old.keystore", ["keyAlias"] = "old-alias" }
            };
            var patch = new JObject
            {
                ["signingConfig"] = new JObject { ["keystorePath"] = "new.keystore" }
            };

            BuildConfigurationLoader.DeepMerge(target, patch);

            var signing = (JObject)target["signingConfig"];
            Assert.AreEqual("new.keystore", signing["keystorePath"]?.ToString());
            Assert.AreEqual("old-alias",   signing["keyAlias"]?.ToString()); // Preserved
        }

        [Test]
        public void DeepMerge_ReplacesArraysNotAppends()
        {
            var target = new JObject { ["scenes"] = new JArray("SceneA", "SceneB") };
            var patch  = new JObject { ["scenes"] = new JArray("SceneC") };

            BuildConfigurationLoader.DeepMerge(target, patch);

            var result = (JArray)target["scenes"];
            Assert.AreEqual(1, result.Count);
            Assert.AreEqual("SceneC", result[0]?.ToString());
        }

        [Test]
        public void FlattenCliOverrides_HandlesSimpleKeys()
        {
            var overrides = new Dictionary<string, string>
            {
                { "outputPath", "Builds/ci" },
                { "bundleVersion", "2.0.0" }
            };

            var result = BuildConfigurationLoader.FlattenCliOverrides(overrides);

            Assert.AreEqual("Builds/ci", result["outputPath"]?.ToString());
            Assert.AreEqual("2.0.0",     result["bundleVersion"]?.ToString());
        }

        [Test]
        public void FlattenCliOverrides_HandlesDotNotationKeys()
        {
            var overrides = new Dictionary<string, string>
            {
                { "signingConfig.keystorePath", "my.keystore" }
            };

            var result = BuildConfigurationLoader.FlattenCliOverrides(overrides);

            var signing = (JObject)result["signingConfig"];
            Assert.IsNotNull(signing);
            Assert.AreEqual("my.keystore", signing["keystorePath"]?.ToString());
        }

        [Test]
        public void Load_EnvironmentNestedLayout_IsFound()
        {
            // Support: environments/production/config.json
            Directory.CreateDirectory(Path.Combine(_tempDir, "environments", "production"));
            WriteJson("base.json", new { productName = "MyGame" });
            WriteJson("environments/production/config.json", new { productName = "MyGame-Prod" });

            var config = _loader.Load(_tempDir, environment: "production");

            Assert.AreEqual("MyGame-Prod", config.ProductName);
        }
    }
}
