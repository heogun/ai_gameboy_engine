from __future__ import annotations

from typing import Any

from .registry import SymbolRegistry
from .state import ProjectState


class ContextCompiler:
    def __init__(self, state: ProjectState, registry: SymbolRegistry):
        self.state = state
        self.registry = registry

    def compile(self, task: dict[str, Any]) -> dict[str, Any]:
        task_id = task["id"]
        base = {
            "task": task_id,
            "request": self.state.get("request"),
            "platform": self.state.get("platform"),
            "engine": self.state.get("engine"),
            "existing": {},
            "symbols": [],
            "constraints": self._constraints(),
        }

        if task_id == "tileset":
            base["existing"] = {}
        elif task_id == "map_layout":
            base["existing"] = {"tileset": self.state.data.get("maps", {}).get("_tileset") or self.state.data.get("tileset")}
        elif task_id == "collision_warps":
            base["existing"] = {"maps": self.state.data.get("maps", {})}
        elif task_id == "npcs":
            base["existing"] = {"maps": self.state.data.get("maps", {})}
        elif task_id == "dialogs":
            base["existing"] = {"npcs": self.state.data.get("npcs", {})}
        elif task_id == "events":
            base["existing"] = {
                "maps": self.state.data.get("maps", {}),
                "npcs": self.state.data.get("npcs", {}),
                "dialogs": self.state.data.get("dialogs", {}),
                "warps": self.state.data.get("warps", {}),
            }
        elif task_id == "assets_prompts":
            base["existing"] = {
                "maps": self.state.data.get("maps", {}),
                "npcs": self.state.data.get("npcs", {}),
                "tileset": self.state.data.get("tileset"),
            }
        else:
            base["existing"] = {k: self.state.data.get(k) for k in ["maps", "npcs", "entities", "assets"] if self.state.data.get(k)}

        base["symbols"] = self.registry.export()["symbols"]
        return base

    def _constraints(self) -> dict[str, Any]:
        return {
            "gb_hardware": {
                "sprites_max": 40,
                "sprites_per_line": 10,
                "bg_palettes_max": 8,
                "obj_palettes_max": 8,
                "colors_per_palette": 4,
            },
            "schema_strict": True,
            "no_engine_edit": True,
            "data_only": True,
        }
