from __future__ import annotations

from typing import Any


class HardwareValidator:
    def __init__(self, platform: str = "gb"):
        self.platform = platform
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate(self, state: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
        self.errors = []
        self.warnings = []
        self._validate_oam(state)
        self._validate_vram(state)
        self._validate_wram(state)
        self._validate_rom_banking(state)
        self._validate_cgb_palettes(state)
        self._validate_sprites_per_scanline_hint(state)
        self._validate_tiles(state)
        self._validate_maps(state)
        self._validate_dialogs(state)
        ok = len(self.errors) == 0
        return ok, self.errors, self.warnings

    def _validate_oam(self, state: dict[str, Any]):
        sprites = []
        for npc in state.get("npcs", {}).values():
            if isinstance(npc, dict):
                sprites.append(npc)
        for ent in state.get("entities", {}).values():
            if isinstance(ent, dict):
                sprites.append(ent)
        for asset in state.get("assets", {}).values():
            if isinstance(asset, dict) and asset.get("type") == "sprite":
                sprites.append(asset)
        total = len(sprites)
        if total > 40:
            self.errors.append(f"[OAM] Total sprite entities/assets exceed 40: {total} (MAX 40)")
        elif total > 32:
            self.warnings.append(f"[OAM] High sprite count: {total}/40. Watch for per-scanline conflicts.")
        if total > 0:
            print(f"[HW] OAM check: {total}/40 sprites tracked", flush=True)

    def _validate_sprites_per_scanline_hint(self, state: dict[str, Any]):
        sprites = []
        for npc in state.get("npcs", {}).values():
            if isinstance(npc, dict) and npc.get("y") is not None:
                sprites.append(int(npc["y"]))
        for ent in state.get("entities", {}).values():
            if isinstance(ent, dict) and ent.get("y") is not None:
                sprites.append(int(ent["y"]))
        if not sprites:
            return
        from collections import Counter
        # Group by approximate scanline band (8px sprite height)
        bands = Counter([y // 8 for y in sprites])
        for band, cnt in bands.items():
            if cnt > 10:
                self.errors.append(f"[OAM-SCANLINE] {cnt} sprites in similar Y band (band~{band}) likely exceed 10 per scanline. Spread vertically or use tilemap.")
            elif cnt > 8:
                self.warnings.append(f"[OAM-SCANLINE] {cnt} sprites in band {band} near 10-per-scanline limit.")
        print(f"[HW] Per-scanline heuristic: checked {len(bands)} bands", flush=True)

    def _validate_vram(self, state: dict[str, Any]):
        # Heuristic: estimate tiles
        tile_count_est = 0
        if state.get("tileset"):
            tiles = state["tileset"].get("tiles") if isinstance(state["tileset"], dict) else None
            if isinstance(tiles, list):
                tile_count_est += len(tiles)
        for asset in state.get("assets", {}).values():
            if isinstance(asset, dict):
                if asset.get("type") == "background":
                    tile_count_est += 256  # rough heuristic for bg
                elif asset.get("type") == "sprite":
                    tile_count_est += 16
        if tile_count_est > 384:
            self.warnings.append(f"[VRAM] Estimated tile usage high (~{tile_count_est}). BG and OBJ share 8KB VRAM. Reuse tiles.")
        elif tile_count_est > 0:
            print(f"[HW] VRAM estimate: ~{tile_count_est} tiles (heuristic)", flush=True)

    def _validate_wram(self, state: dict[str, Any]):
        flags = state.get("flags", {})
        events = state.get("events", {})
        dialogs = state.get("dialogs", {})
        npcs = state.get("npcs", {})
        maps = state.get("maps", {})
        est_bytes = len(flags) * 1 + len(events) * 4 + len(dialogs) * 32 + len(npcs) * 8 + len(maps) * 16
        limit = 8192 if self.platform != "gbc" else 32768
        if est_bytes > limit * 0.6:
            self.warnings.append(f"[WRAM] Estimated state usage ~{est_bytes} bytes approaching WRAM limit ({limit}B). Keep compact.")
        elif est_bytes > 0:
            print(f"[HW] WRAM estimate: ~{est_bytes} bytes / {limit}B", flush=True)

    def _validate_rom_banking(self, state: dict[str, Any]):
        total_items = sum(len(v) if isinstance(v, dict) else 0 for v in [state.get("maps", {}), state.get("npcs", {}), state.get("dialogs", {}), state.get("events", {}), state.get("assets", {})])
        if total_items > 80:
            self.warnings.append(f"[ROM] Large data set ({total_items} entries). May require MBC banking and careful bank placement.")
        elif total_items > 0:
            print(f"[HW] ROM/BANK estimate: {total_items} data entries (heuristic)", flush=True)

    def _validate_cgb_palettes(self, state: dict[str, Any]):
        if self.platform != "gbc":
            return
        assets = state.get("assets", {})
        sprite_palettes = 0
        bg_palettes = 0
        for asset in assets.values():
            if isinstance(asset, dict):
                if asset.get("type") == "sprite":
                    sprite_palettes += 1
                elif asset.get("type") == "background":
                    bg_palettes += 1
        if sprite_palettes > 8:
            self.errors.append(f"[CGB] Sprite palettes exceed 8: {sprite_palettes}")
        if bg_palettes > 8:
            self.errors.append(f"[CGB] Background palettes exceed 8: {bg_palettes}")
        if sprite_palettes > 0 or bg_palettes > 0:
            print(f"[HW] CGB palettes: BG={bg_palettes}/8, OBJ={sprite_palettes}/8", flush=True)

    def _validate_tiles(self, state: dict[str, Any]):
        if state.get("tileset"):
            tiles = state["tileset"].get("tiles") if isinstance(state["tileset"], dict) else None
            if isinstance(tiles, list) and len(tiles) > 192:
                self.warnings.append(f"[TILES] Large tileset ({len(tiles)} tiles). BG/OBJ share VRAM.")
        print(f"[HW] Tileset check done", flush=True)

    def _validate_maps(self, state: dict[str, Any]):
        maps = state.get("maps", {})
        if len(maps) > 16:
            self.warnings.append(f"[MAPS] {len(maps)} maps. Keep minimal for memory/banking.")
        print(f"[HW] Maps check: {len(maps)} maps", flush=True)

    def _validate_dialogs(self, state: dict[str, Any]):
        dialogs = state.get("dialogs", {})
        total = 0
        for d in dialogs.values():
            if isinstance(d, dict):
                text = d.get("text", [])
                if isinstance(text, list):
                    for t in text:
                        if isinstance(t, str):
                            total += len(t)
        if total > 2000:
            self.warnings.append(f"[DIALOG] {total} chars total. Consider compression/conciseness.")
        print(f"[HW] Dialog check: {len(dialogs)} entries, {total} chars", flush=True)
