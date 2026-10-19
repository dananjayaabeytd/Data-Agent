import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pydantic import ValidationError

from utils import llm_pick

PROFILES = """
active: cheap
profiles:
  cheap:
    description: test
    defaults: {reasoning_effort: minimal}
    levels:
      low: {model: model-a}
      medium: {model: model-b, timeout: 30}
      high: {model: model-c}
  strong:
    defaults: {reasoning_effort: none, temperature: 0}
    levels:
      low: {model: model-x}
      medium: {model: model-y}
      high: {model: model-z}
"""


class ModelProfileTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.config = Path(self.directory.name) / "models.yaml"
        self.config.write_text(PROFILES, encoding="utf-8")
        self.patches = [
            patch.object(llm_pick, "CONFIG_PATH", self.config),
            patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-not-used"}),
        ]
        for active in self.patches:
            active.start()
        os.environ.pop("MODEL_PROFILE", None)
        llm_pick.active_profile.cache_clear()

    def tearDown(self):
        for active in self.patches:
            active.stop()
        llm_pick.active_profile.cache_clear()
        self.directory.cleanup()

    def test_active_profile_from_file_with_defaults_merged(self):
        profile = llm_pick.active_profile()
        self.assertEqual(profile.name, "cheap")
        self.assertEqual(profile.levels["medium"].model, "model-b")
        self.assertEqual(profile.levels["medium"].timeout, 30)
        self.assertEqual(profile.levels["low"].reasoning_effort, "minimal")

    def test_environment_variable_selects_profile(self):
        with patch.dict(os.environ, {"MODEL_PROFILE": "strong"}):
            llm = llm_pick.pick_llm("medium")
        self.assertEqual(llm.model_name, "model-y")
        self.assertEqual(llm.temperature, 0)
        self.assertEqual(llm.reasoning_effort, "none")

    def test_unknown_profile_is_rejected(self):
        with patch.dict(os.environ, {"MODEL_PROFILE": "missing"}):
            with self.assertRaisesRegex(ValueError, "available: cheap, strong"):
                llm_pick.active_profile()

    def test_typo_in_settings_is_rejected(self):
        self.config.write_text(PROFILES.replace("timeout: 30", "timout: 30"), encoding="utf-8")
        with self.assertRaises(ValidationError):
            llm_pick.active_profile()

    def test_missing_level_is_rejected(self):
        self.config.write_text(PROFILES.replace("      high: {model: model-c}\n", ""), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing levels: high"):
            llm_pick.active_profile()


class ShippedConfigTests(unittest.TestCase):
    def test_every_shipped_profile_is_valid(self):
        import yaml

        config = yaml.safe_load(llm_pick.CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIn(config["active"], config["profiles"])
        self.assertTrue({"budget", "quality"} <= set(config["profiles"]))
        for name in config["profiles"]:
            with patch.dict(os.environ, {"MODEL_PROFILE": name}):
                llm_pick.active_profile.cache_clear()
                profile = llm_pick.active_profile()
            self.assertEqual(set(profile.levels), set(llm_pick.LEVELS), name)
        llm_pick.active_profile.cache_clear()
