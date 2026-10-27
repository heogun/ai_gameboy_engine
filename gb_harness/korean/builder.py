from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

from .extract import extract_used_hangul


class KoreanSubsetBuilder:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.korean_dir = output_dir / "korean"
        self.korean_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir = Path(__file__).parent / "assets"

    def build(self, state: dict[str, Any]) -> dict[str, Any] | None:
        used = sorted(list(extract_used_hangul(state)))
        if not used:
            return None
        mapping = []
        for i, ch in enumerate(used):
            mapping.append({"char": ch, "tile_index": i, "codepoint": ord(ch)})
        meta = {
            "type": "korean_subset_8x8",
            "count": len(used),
            "mapping": mapping,
            "source": "8x8_hangul_base_subset",
            "note": "Use window layer for Korean text output",
        }
        meta_path = self.korean_dir / "korean_subset.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tiles_path = self.korean_dir / "font_korean_tiles.bin"
        # Try to use base font if available
        base_bin = self.assets_dir / "font_korean_base.bin"
        if base_bin.is_file():
            base_data = base_bin.read_bytes()
        else:
            base_data = bytes([0x00] * 2048)
        # Generate subset tiles (copy from base or placeholder)
        out_tiles = bytearray()
        for i in range(len(used)):
            start = i * 8
            if start + 8 <= len(base_data):
                out_tiles.extend(base_data[start : start + 8])
            else:
                out_tiles.extend(bytes([0x00] * 8))
        tiles_path.write_bytes(bytes(out_tiles))
        return {"meta": meta_path, "tiles_bin": tiles_path, "count": len(used)}
