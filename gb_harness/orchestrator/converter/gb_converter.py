from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..validator_hardware import HardwareValidator


class GBDataConverter:
    def __init__(self, output_dir: Path, platform: str = "gb"):
        self.output_dir = output_dir
        self.platform = platform
        self.converter_dir = output_dir / "orchestrator_converted"
        self.validator = HardwareValidator(platform)

    def load_state(self) -> dict[str, Any]:
        state_path = self.output_dir / "orchestrator_state.json"
        if not state_path.is_file():
            raise FileNotFoundError(f"Missing orchestrator state: {state_path}")
        return json.loads(state_path.read_text(encoding="utf-8"))

    def convert(self) -> dict[str, Path]:
        print("[CONV] 오케스트레이션 데이터 변환 시작", flush=True)
        state = self.load_state()
        print("[CONV] 하드웨어 엄밀 검증 실행", flush=True)
        ok, errors, warnings = self.validator.validate(state)
        self.converter_dir.mkdir(parents=True, exist_ok=True)
        hw_report = self.converter_dir / "hardware_report.json"
        report = {"ok": ok, "errors": errors, "warnings": warnings, "platform": self.platform}
        hw_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[CONV] 하드웨어 리포트 저장: {hw_report}", flush=True)
        for e in errors:
            print(f"[CONV][HW-ERR] {e}", flush=True)
        for w in warnings:
            print(f"[CONV][HW-WARN] {w}", flush=True)
        if not ok:
            print("[CONV] 하드웨어 제약 위반으로 변환 중단", flush=True)
            return {"hardware_report": hw_report}

        maps_c = self.converter_dir / "maps_data.c"
        npcs_c = self.converter_dir / "npcs_data.c"
        dialogs_c = self.converter_dir / "dialogs_data.c"
        events_c = self.converter_dir / "events_data.c"
        assets_c = self.converter_dir / "assets_data.c"
        header_h = self.converter_dir / "orchestrator_data.h"

        maps_c.write_text(self._gen_maps(state), encoding="utf-8")
        npcs_c.write_text(self._gen_npcs(state), encoding="utf-8")
        dialogs_c.write_text(self._gen_dialogs(state), encoding="utf-8")
        events_c.write_text(self._gen_events(state), encoding="utf-8")
        assets_c.write_text(self._gen_assets(state), encoding="utf-8")
        header_h.write_text(self._gen_header(state), encoding="utf-8")

        print(f"[CONV] 생성: {maps_c.name}, {npcs_c.name}, {dialogs_c.name}, {events_c.name}, {assets_c.name}, {header_h.name}", flush=True)
        print("[CONV] 변환 완료", flush=True)
        return {
            "hardware_report": hw_report,
            "maps_c": maps_c,
            "npcs_c": npcs_c,
            "dialogs_c": dialogs_c,
            "events_c": events_c,
            "assets_c": assets_c,
            "header_h": header_h,
        }

    def _gen_header(self, state: dict[str, Any]) -> str:
        return (
            "#ifndef ORCHESTRATOR_DATA_H\n"
            "#define ORCHESTRATOR_DATA_H\n\n"
            "#include <gb/gb.h>\n\n"
            f"// Generated from orchestrator state (platform: {self.platform})\n"
            f"// Maps: {len(state.get('maps', {}))}, NPCs: {len(state.get('npcs', {}))}, Dialogs: {len(state.get('dialogs', {}))}\n\n"
            "#endif\n"
        )

    def _gen_maps(self, state: dict[str, Any]) -> str:
        lines = ["#include \"orchestrator_data.h\"", ""]
        for mid, m in state.get("maps", {}).items():
            if mid == "_tileset":
                continue
            lines.append(f"// map: {mid}")
            lines.append(f"const unsigned char map_{mid}[] = {{ 0x00 }};")
            lines.append("")
        return "\n".join(lines) + "\n"

    def _gen_npcs(self, state: dict[str, Any]) -> str:
        lines = ["#include \"orchestrator_data.h\"", ""]
        for nid, n in state.get("npcs", {}).items():
            lines.append(f"// npc: {nid} map:{n.get('map_id')} x:{n.get('x')} y:{n.get('y')}")
            lines.append(f"const unsigned char npc_{nid}_data[] = {{ 0x00 }};")
            lines.append("")
        return "\n".join(lines) + "\n"

    def _gen_dialogs(self, state: dict[str, Any]) -> str:
        lines = ["#include \"orchestrator_data.h\"", ""]
        for did, d in state.get("dialogs", {}).items():
            lines.append(f"// dialog: {did} npc:{d.get('npc_id')}")
            lines.append(f"const unsigned char dialog_{did}[] = {{ 0x00 }};")
            lines.append("")
        return "\n".join(lines) + "\n"

    def _gen_events(self, state: dict[str, Any]) -> str:
        lines = ["#include \"orchestrator_data.h\"", ""]
        for eid, e in state.get("events", {}).items():
            lines.append(f"// event: {eid} type:{e.get('type')}")
            lines.append(f"const unsigned char event_{eid}[] = {{ 0x00 }};")
            lines.append("")
        return "\n".join(lines) + "\n"

    def _gen_assets(self, state: dict[str, Any]) -> str:
        lines = ["#include \"orchestrator_data.h\"", ""]
        for aid, a in state.get("assets", {}).items():
            lines.append(f"// asset: {aid} type:{a.get('type')}")
            lines.append(f"const unsigned char asset_{aid}_meta[] = {{ 0x00 }};")
            lines.append("")
        return "\n".join(lines) + "\n"
