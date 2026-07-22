import json
import tempfile
import unittest
from pathlib import Path

from preset_store import PresetStore


class PresetStoreTests(unittest.TestCase):
    def test_seeds_user_presets_from_the_bundled_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bundled_path = root / "bundled.json"
            user_path = root / "user" / "presets.json"
            bundled_path.write_text(
                json.dumps({"version": 1, "presets": [{"name": "Example lock"}]}),
                encoding="utf-8",
            )

            presets = PresetStore(user_path=user_path, bundled_path=bundled_path).load()

            self.assertIn("Example lock", presets)
            self.assertTrue(user_path.exists())

    def test_saves_presets_by_name(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "presets.json"
            store = PresetStore(user_path=user_path, bundled_path=user_path)
            store.save({"Chest": {"name": "Chest", "layerCount": 1}})

            self.assertEqual("Chest", store.load()["Chest"]["name"])


if __name__ == "__main__":
    unittest.main()
