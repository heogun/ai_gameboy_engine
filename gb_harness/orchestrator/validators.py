from __future__ import annotations

import json
import re
from typing import Any

from .registry import SymbolRegistry


class ValidationPipeline:
    def __init__(self, registry: SymbolRegistry):
        self.registry = registry

    def validate_element(self, data: Any, schema: str) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if not isinstance(data, dict):
            return False, ["Element validation: expected object"]
        if schema == "tileset":
            required = ["tileset_id", "tiles"]
            for r in required:
                if r not in data:
                    errors.append(f"Missing required field: {r}")
            if "tileset_id" in data and not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", str(data["tileset_id"])):
                errors.append("Invalid tileset_id")
        elif schema == "map":
            required = ["map_id", "width", "height", "tiles"]
            for r in required:
                if r not in data:
                    errors.append(f"Missing required field: {r}")
            if "map_id" in data and not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", str(data["map_id"])):
                errors.append("Invalid map_id")
        elif schema == "npcs":
            if "npcs" not in data or not isinstance(data["npcs"], list):
                errors.append("npcs must be a list")
        elif schema == "dialogs":
            if "dialogs" not in data or not isinstance(data["dialogs"], list):
                errors.append("dialogs must be a list")
        elif schema == "events":
            if "events" not in data or not isinstance(data["events"], list):
                errors.append("events must be a list")
        elif schema == "assets":
            if "assets" not in data or not isinstance(data["assets"], list):
                errors.append("assets must be a list")
        else:
            pass
        return len(errors) == 0, errors

    def validate_local(self, data: Any) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if isinstance(data, dict):
            if "npcs" in data and isinstance(data["npcs"], list):
                seen = set()
                for npc in data["npcs"]:
                    if isinstance(npc, dict) and npc.get("npc_id"):
                        if npc["npc_id"] in seen:
                            errors.append(f"Duplicate npc_id: {npc['npc_id']}")
                        seen.add(npc["npc_id"])
            if "dialogs" in data and isinstance(data["dialogs"], list):
                seen = set()
                for dlg in data["dialogs"]:
                    if isinstance(dlg, dict) and dlg.get("dialog_id"):
                        if dlg["dialog_id"] in seen:
                            errors.append(f"Duplicate dialog_id: {dlg['dialog_id']}")
                        seen.add(dlg["dialog_id"])
        return len(errors) == 0, errors

    def validate_reference(self, data: Any, state: Any) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if isinstance(data, dict):
            if "npcs" in data and isinstance(data["npcs"], list):
                maps = state.data.get("maps", {}) if hasattr(state, "data") else {}
                for npc in data["npcs"]:
                    if isinstance(npc, dict):
                        map_id = npc.get("map_id")
                        if map_id and map_id not in maps and map_id != "_tileset":
                            errors.append(f"NPC references unknown map: {map_id}")
            if "dialogs" in data and isinstance(data["dialogs"], list):
                npcs = state.data.get("npcs", {}) if hasattr(state, "data") else {}
                for dlg in data["dialogs"]:
                    if isinstance(dlg, dict):
                        npc_id = dlg.get("npc_id")
                        if npc_id and npc_id not in npcs:
                            errors.append(f"Dialog references unknown npc: {npc_id}")
            if "warps" in data and isinstance(data["warps"], list):
                maps = state.data.get("maps", {}) if hasattr(state, "data") else {}
                for warp in data["warps"]:
                    if isinstance(warp, dict):
                        to_map = warp.get("to_map")
                        if to_map and to_map not in maps:
                            errors.append(f"Warp references unknown map: {to_map}")
        return len(errors) == 0, errors

    def validate_graph(self, state: Any) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if not hasattr(state, "data"):
            return True, []
        maps = state.data.get("maps", {})
        npcs = state.data.get("npcs", {})
        dialogs = state.data.get("dialogs", {})
        for npc_id, npc in npcs.items():
            if isinstance(npc, dict):
                map_id = npc.get("map_id")
                if map_id and map_id not in maps:
                    errors.append(f"Graph: npc {npc_id} on unknown map {map_id}")
        for dlg_id, dlg in dialogs.items():
            if isinstance(dlg, dict):
                npc_id = dlg.get("npc_id")
                if npc_id and npc_id not in npcs:
                    errors.append(f"Graph: dialog {dlg_id} references unknown npc {npc_id}")
        return len(errors) == 0, errors

    def validate_hardware(self, data: Any) -> tuple[bool, list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        if isinstance(data, dict):
            if "npcs" in data and isinstance(data["npcs"], list):
                npc_count = len(data["npcs"])
                if npc_count > 12:
                    errors.append(f"Hardware violation: {npc_count} NPCs as sprites likely exceed OAM budget (max 40 total, max 10 per scanline). Reduce or use tilemap.")
                elif npc_count > 8:
                    warnings.append(f"Hardware warning: {npc_count} NPCs may approach OAM per-scanline limit (10). Keep spread across Y positions.")
            if "entities" in data and isinstance(data["entities"], list):
                ent_count = len(data["entities"])
                if ent_count > 12:
                    errors.append(f"Hardware violation: {ent_count} entities as sprites likely exceed OAM budget. Prefer tilemap-based enemies.")
                elif ent_count > 8:
                    warnings.append(f"Hardware warning: {ent_count} entities may hit 10-per-scanline limit.")
            if "assets" in data and isinstance(data["assets"], list):
                sprite_assets = [a for a in data["assets"] if isinstance(a, dict) and a.get("type") == "sprite"]
                if len(sprite_assets) > 16:
                    errors.append(f"Hardware violation: {len(sprite_assets)} sprite assets risk OAM exhaustion (40 total).")
            # Log warnings but don't fail
            for w in warnings:
                print(f"[VAL][HW-WARN] {w}", flush=True)
        return len(errors) == 0, errors

    def validate_all(self, data: Any, schema: str, state: Any) -> tuple[bool, list[str]]:
        print(f"[VAL] 다단계 검증 시작 (schema={schema})", flush=True)
        all_errors: list[str] = []
        ok, errs = self.validate_element(data, schema)
        print(f"[VAL] 1) 요소검증: {'OK' if ok else 'FAIL'} ({len(errs)} errors)", flush=True)
        all_errors.extend(errs)
        ok2, errs2 = self.validate_local(data)
        print(f"[VAL] 2) 지역검증: {'OK' if ok2 else 'FAIL'} ({len(errs2)} errors)", flush=True)
        all_errors.extend(errs2)
        ok3, errs3 = self.validate_reference(data, state)
        print(f"[VAL] 3) 참조검증: {'OK' if ok3 else 'FAIL'} ({len(errs3)} errors)", flush=True)
        all_errors.extend(errs3)
        ok4, errs4 = self.validate_graph(state)
        print(f"[VAL] 4) 그래프검증: {'OK' if ok4 else 'FAIL'} ({len(errs4)} errors)", flush=True)
        all_errors.extend(errs4)
        ok5, errs5 = self.validate_hardware(data)
        print(f"[VAL] 5) 하드웨어제약검증: {'OK' if ok5 else 'FAIL'} ({len(errs5)} errors)", flush=True)
        all_errors.extend(errs5)
        print(f"[VAL] 검증 완료: {'ALL OK' if len(all_errors) == 0 else f'{len(all_errors)} errors'}", flush=True)
        return len(all_errors) == 0, all_errors
