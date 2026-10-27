from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ProjectState:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.state_path = output_dir / "orchestrator_state.json"
        self.data: dict[str, Any] = {
            "version": 1,
            "game_type": None,
            "request": None,
            "platform": "gb",
            "engine": None,
            "maps": {},
            "npcs": {},
            "dialogs": {},
            "warps": {},
            "entities": {},
            "items": {},
            "flags": {},
            "events": {},
            "assets": {},
            "tasks": [],
            "completed_tasks": [],
            "current_task": None,
            "history": [],
        }
        self.load()

    def load(self) -> None:
        if self.state_path.is_file():
            try:
                loaded = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data = loaded
            except (json.JSONDecodeError, OSError):
                pass

    def save(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return self.state_path

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def update(self, updates: dict[str, Any]) -> None:
        self.data.update(updates)

    def add_history(self, entry: dict[str, Any]) -> None:
        history = self.data.setdefault("history", [])
        if isinstance(history, list):
            history.append(entry)
            self.data["history"] = history
