from __future__ import annotations

import re
from typing import Any


class SymbolRegistry:
    def __init__(self):
        self.symbols: dict[str, dict[str, Any]] = {}

    def register(self, symbol_type: str, symbol_id: str, meta: dict[str, Any] | None = None) -> None:
        key = f"{symbol_type}:{symbol_id}"
        if key in self.symbols:
            raise ValueError(f"Duplicate symbol: {key}")
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", symbol_id):
            raise ValueError(f"Invalid symbol id: {symbol_id}")
        self.symbols[key] = {"type": symbol_type, "id": symbol_id, "meta": meta or {}}
        print(f"[REG] 심볼 등록: {key}", flush=True)

    def has(self, symbol_type: str, symbol_id: str) -> bool:
        return f"{symbol_type}:{symbol_id}" in self.symbols

    def get(self, symbol_type: str, symbol_id: str) -> dict[str, Any] | None:
        return self.symbols.get(f"{symbol_type}:{symbol_id}")

    def list_by_type(self, symbol_type: str) -> list[dict[str, Any]]:
        return [v for v in self.symbols.values() if v["type"] == symbol_type]

    def all(self) -> dict[str, dict[str, Any]]:
        return dict(self.symbols)

    def export(self) -> dict[str, Any]:
        return {"symbols": list(self.symbols.values())}

    def import_from(self, data: dict[str, Any]) -> None:
        self.symbols.clear()
        for item in data.get("symbols", []):
            if isinstance(item, dict) and item.get("type") and item.get("id"):
                key = f"{item['type']}:{item['id']}"
                self.symbols[key] = item
