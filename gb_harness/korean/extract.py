from __future__ import annotations

import re
from typing import Any

HANGUL_RE = re.compile(r"[가-힣]")


def extract_used_hangul(state: dict[str, Any]) -> set[str]:
    used: set[str] = set()
    for d in state.get("dialogs", {}).values():
        if isinstance(d, dict):
            text_list = d.get("text")
            if isinstance(text_list, list):
                for t in text_list:
                    if isinstance(t, str):
                        used.update(HANGUL_RE.findall(t))
            elif isinstance(text_list, str):
                used.update(HANGUL_RE.findall(text_list))
    for e in state.get("events", {}).values():
        if isinstance(e, dict):
            text_list = e.get("text")
            if isinstance(text_list, list):
                for t in text_list:
                    if isinstance(t, str):
                        used.update(HANGUL_RE.findall(t))
            elif isinstance(text_list, str):
                used.update(HANGUL_RE.findall(text_list))
    for npc in state.get("npcs", {}).values():
        if isinstance(npc, dict):
            text_list = npc.get("dialogue")
            if isinstance(text_list, list):
                for t in text_list:
                    if isinstance(t, str):
                        used.update(HANGUL_RE.findall(t))
            elif isinstance(text_list, str):
                used.update(HANGUL_RE.findall(text_list))
    return used
