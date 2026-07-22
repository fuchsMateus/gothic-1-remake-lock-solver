"""Local storage for named Gothic 1 Remake lock presets."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class PresetStore:
    FORMAT_VERSION = 1

    def __init__(self, user_path: Path | None = None, bundled_path: Path | None = None) -> None:
        application_directory = Path(__file__).resolve().parent
        local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        self.user_path = user_path or local_app_data / "Gothic1RemakeLockpick" / "presets.json"
        self.bundled_path = bundled_path or application_directory / "presets.json"

    def load(self) -> dict[str, dict[str, Any]]:
        if not self.user_path.exists():
            presets = self._read_file(self.bundled_path) if self.bundled_path.exists() else {}
            self.save(presets)
            return presets
        return self._read_file(self.user_path)

    def save(self, presets: dict[str, dict[str, Any]]) -> None:
        self.user_path.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "version": self.FORMAT_VERSION,
            "presets": [presets[name] for name in sorted(presets, key=str.lower)],
        }
        temporary_path = self.user_path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        temporary_path.replace(self.user_path)

    @staticmethod
    def _read_file(path: Path) -> dict[str, dict[str, Any]]:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Unable to read presets from {path}: {error}") from error

        if document.get("version") != PresetStore.FORMAT_VERSION:
            raise ValueError("Unsupported preset file version.")
        preset_list = document.get("presets")
        if not isinstance(preset_list, list):
            raise ValueError("Preset file must contain a presets list.")

        presets: dict[str, dict[str, Any]] = {}
        for preset in preset_list:
            if not isinstance(preset, dict) or not isinstance(preset.get("name"), str):
                raise ValueError("Every preset must have a name.")
            name = preset["name"].strip()
            if not name:
                raise ValueError("Preset names cannot be empty.")
            if name in presets:
                raise ValueError(f"Duplicate preset name: {name}")
            presets[name] = preset
        return presets
