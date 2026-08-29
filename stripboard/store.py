from __future__ import annotations

import json
import os
from pathlib import Path

from .models import Placement, Position, Settings


def data_dir() -> Path:
    root = os.getenv("APPDATA")
    return Path(root) / "IVAO Strip Board" if root else Path.home() / ".ivao-strip-board"


class Store:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or data_dir()
        self.settings_file = self.root / "settings.json"
        self.layout_file = self.root / "layout.json"

    def load_settings(self) -> Settings:
        try:
            raw = json.loads(self.settings_file.read_text(encoding="utf-8"))
            positions = [Position(str(p["name"]), list(p.get("airports", []))) for p in raw["positions"]]
            return Settings(str(raw["host"]), int(raw["port"]), str(raw["selected_position"]), positions)
        except (OSError, ValueError, KeyError, TypeError):
            return Settings()

    def save_settings(self, settings: Settings) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.settings_file.write_text(json.dumps(settings.to_dict(), indent=2), encoding="utf-8")

    def load_layout(self) -> dict[str, Placement]:
        try:
            raw = json.loads(self.layout_file.read_text(encoding="utf-8"))
            return {key: Placement(**value) for key, value in raw.items()}
        except (OSError, ValueError, TypeError):
            return {}

    def save_layout(self, layout: dict[str, Placement]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        value = {key: {"row": p.row, "column": p.column, "span": p.span} for key, p in layout.items()}
        self.layout_file.write_text(json.dumps(value, indent=2), encoding="utf-8")
