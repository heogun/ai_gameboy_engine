from __future__ import annotations

from typing import Any


class TaskGraph:
    def __init__(self, game_type: str = "topdown_rpg"):
        self.game_type = game_type
        self.tasks: list[dict[str, Any]] = []
        self._build_default()

    def _build_default(self) -> None:
        if self.game_type == "topdown_rpg":
            self.tasks = [
                {"id": "tileset", "depends_on": [], "agent": "tileset_agent", "schema": "tileset"},
                {"id": "map_layout", "depends_on": ["tileset"], "agent": "map_agent", "schema": "map"},
                {"id": "collision_warps", "depends_on": ["map_layout"], "agent": "collision_agent", "schema": "collision"},
                {"id": "npcs", "depends_on": ["map_layout"], "agent": "entity_agent", "schema": "npcs"},
                {"id": "dialogs", "depends_on": ["npcs"], "agent": "dialog_agent", "schema": "dialogs"},
                {"id": "events", "depends_on": ["collision_warps", "npcs", "dialogs"], "agent": "event_agent", "schema": "events"},
                {"id": "assets_prompts", "depends_on": ["tileset", "npcs"], "agent": "asset_agent", "schema": "assets"},
            ]
        else:
            self.tasks = [
                {"id": "core_setup", "depends_on": [], "agent": "core_agent", "schema": "core"},
                {"id": "entities", "depends_on": ["core_setup"], "agent": "entity_agent", "schema": "entities"},
                {"id": "logic", "depends_on": ["entities"], "agent": "logic_agent", "schema": "logic"},
                {"id": "assets_prompts", "depends_on": ["core_setup"], "agent": "asset_agent", "schema": "assets"},
            ]

    def get_next(self, completed: set[str]) -> dict[str, Any] | None:
        for task in self.tasks:
            task_id = task["id"]
            if task_id in completed:
                continue
            deps = task.get("depends_on", [])
            if all(d in completed for d in deps):
                return task
        return None

    def is_done(self, completed: set[str]) -> bool:
        return all(t["id"] in completed for t in self.tasks)

    def export(self) -> list[dict[str, Any]]:
        return list(self.tasks)
