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
        print(f"[CTX] 컨텍스트 컴파일 시작: {task_id}", flush=True)
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
            base["available_npc_ids"] = list(self.state.data.get("npcs", {}).keys())
        elif task_id == "events":
            base["existing"] = {
                "maps": self.state.data.get("maps", {}),
                "npcs": self.state.data.get("npcs", {}),
                "dialogs": self.state.data.get("dialogs", {}),
                "warps": self.state.data.get("warps", {}),
            }
            base["available_npc_ids"] = list(self.state.data.get("npcs", {}).keys())
        elif task_id == "assets_prompts":
            base["existing"] = {
                "maps": self.state.data.get("maps", {}),
                "npcs": self.state.data.get("npcs", {}),
                "tileset": self.state.data.get("tileset"),
            }
        else:
            base["existing"] = {k: self.state.data.get(k) for k in ["maps", "npcs", "entities", "assets"] if self.state.data.get(k)}
            base["available_npc_ids"] = list(self.state.data.get("npcs", {}).keys())

        base["symbols"] = self.registry.export()["symbols"]
        print(f"[CTX] 컨텍스트 컴파일 완료: symbols={len(base['symbols'])}, existing_keys={list(base['existing'].keys())}, available_npc_ids={base.get('available_npc_ids',[])}", flush=True)
        return base

    def _constraints(self) -> dict[str, Any]:
        return {
            "gb_hardware": {
                "screen": {"w": 160, "h": 144},
                "sprites": {"max_total": 40, "max_per_scanline": 10, "default_size": "8x8", "critical": True},
                "background": {"max_palettes_dmg": 1, "max_palettes_cgb": 8, "colors_per_palette": 4},
                "objects": {"max_palettes_cgb": 8, "colors_per_palette": 4},
                "dmg": {"shades": 4},
                "cgb": {"max_colors_per_palette": 4, "bit_depth": 15},
                "tiles": {"note": "BG and OBJ tiles share VRAM. Keep counts minimal."},
                "window": {"available": True, "note": "Use sparingly for UI/dialogue."},
                "banking": {"note": "Large data may require MBC banking."},
                "vblank": {"note": "Respect VBlank timing for updates."},
            },
            "schema_strict": True,
            "no_engine_edit": True,
            "data_only": True,
            "prefer_tilemap": True,
            "sprite_budget_enforced": True,
        }
