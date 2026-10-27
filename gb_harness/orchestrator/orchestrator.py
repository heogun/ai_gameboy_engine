from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..client import GenerationError, request_spec
from ..prompt import GBC_SYSTEM_PROMPT, SYSTEM_PROMPT
from ..schema import SpecValidationError, validate_spec

from .context_compiler import ContextCompiler
from .registry import SymbolRegistry
from .state import ProjectState
from .task_graph import TaskGraph
from .validators import ValidationPipeline


ORCHESTRATOR_SYSTEM_PROMPT = r"""
You are a strict Game Boy data orchestrator for a fixed engine.

Your ONLY job is to fill in data for the NEXT task in a strict dependency order.
Do NOT write engine code. Do NOT write a full main.c. Do NOT invent engine systems.
Only output valid JSON that matches the requested schema for this task.

Rules:
- Output raw JSON only, no markdown, no explanation.
- Use short, valid C identifiers for ids.
- Respect Game Boy hardware limits.
- Only reference ids that exist in the provided context symbols/maps/npcs.
- If unsure, create minimal valid data that satisfies references.
- Keep everything data-only.
""".strip()


class Orchestrator:
    def __init__(self, args, output_dir: Path):
        self.args = args
        self.output_dir = output_dir
        self.state = ProjectState(output_dir)
        self.registry = SymbolRegistry()
        self.task_graph = TaskGraph(game_type="topdown_rpg")
        self.compiler = ContextCompiler(self.state, self.registry)
        self.validators = ValidationPipeline(self.registry)

    def run(self) -> int:
        print("[ORCH] 오케스트레이션 모드 시작", flush=True)
        if not self.state.get("request"):
            self.state.set("request", self.args.request or "")
            self.state.set("platform", self.args.platform)
            self.state.save()

        completed = set(self.state.get("completed_tasks") or [])
        max_iterations = 50
        iterations = 0

        while not self.task_graph.is_done(completed):
            iterations += 1
            if iterations > max_iterations:
                print("[ORCH] 최대 반복 횟수 초과", flush=True)
                break
            task = self.task_graph.get_next(completed)
            if not task:
                print("[ORCH] 다음 작업을 찾을 수 없음", flush=True)
                break

            task_id = task["id"]
            print(f"[ORCH] 작업 진행: {task_id} (agent: {task['agent']})", flush=True)
            ctx = self.compiler.compile(task)
            schema = task["schema"]

            prompt = self._build_task_prompt(task, ctx)
            api_key = self.args.api_key if hasattr(self.args, "api_key") else None

            try:
                result = request_spec(
                    prompt,
                    api_key,
                    self.args.model,
                    self.args.api_base_url,
                    system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
                )
            except Exception as e:
                print(f"[ORCH][ERR] 요청 실패: {e}", flush=True)
                break

            ok, errs = self.validators.validate_all(result, schema, self.state)
            repair_count = 0
            while not ok and repair_count < 3:
                repair_count += 1
                print(f"[ORCH] 검증 실패 ({repair_count}/3), 수정 요청 중...", flush=True)
                repair_prompt = self._build_repair_prompt(task, ctx, result, errs)
                try:
                    result = request_spec(
                        repair_prompt,
                        api_key,
                        self.args.model,
                        self.args.api_base_url,
                        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
                    )
                    ok, errs = self.validators.validate_all(result, schema, self.state)
                except Exception as e:
                    print(f"[ORCH][ERR] 수정 요청 실패: {e}", flush=True)
                    break

            if not ok:
                print(f"[ORCH][ERR] 검증 최종 실패: {errs}", flush=True)
                break

            self._apply_result(task_id, result)
            self._register_symbols(task_id, result)
            completed.add(task_id)
            self.state.set("completed_tasks", list(completed))
            self.state.add_history({"task": task_id, "ok": True})
            self.state.save()
            print(f"[ORCH] 작업 완료: {task_id}", flush=True)

        print("[ORCH] 오케스트레이션 완료", flush=True)
        self._write_summary()
        return 0

    def _build_task_prompt(self, task: dict[str, Any], ctx: dict[str, Any]) -> str:
        return (
            f"Generate data for task: {task['id']} (schema: {task['schema']})\n\n"
            f"CONTEXT:\n{json.dumps(ctx, ensure_ascii=False, indent=2)}\n\n"
            f"Return ONLY JSON matching this task schema."
        )

    def _build_repair_prompt(self, task: dict[str, Any], ctx: dict[str, Any], bad: Any, errs: list[str]) -> str:
        return (
            f"Fix the previous JSON for task: {task['id']} (schema: {task['schema']})\n\n"
            f"ERRORS:\n{json.dumps(errs, ensure_ascii=False, indent=2)}\n\n"
            f"PREVIOUS:\n{json.dumps(bad, ensure_ascii=False, indent=2)}\n\n"
            f"CONTEXT:\n{json.dumps(ctx, ensure_ascii=False, indent=2)}\n\n"
            f"Return corrected JSON only."
        )

    def _apply_result(self, task_id: str, result: Any) -> None:
        if not isinstance(result, dict):
            return
        if task_id == "tileset" and "tileset_id" in result:
            self.state.set("tileset", result)
            self.state.data.setdefault("maps", {})["_tileset"] = result.get("tileset_id")
        elif task_id == "map_layout" and "map_id" in result:
            self.state.data.setdefault("maps", {})[result["map_id"]] = result
        elif task_id == "collision_warps":
            if "warps" in result and isinstance(result["warps"], list):
                self.state.data.setdefault("warps", {}).update({w.get("warp_id", f"w{i}"): w for i, w in enumerate(result["warps"])})
            if "collision" in result:
                self.state.data["collision"] = result.get("collision")
        elif task_id == "npcs" and "npcs" in result and isinstance(result["npcs"], list):
            for npc in result["npcs"]:
                if isinstance(npc, dict) and npc.get("npc_id"):
                    self.state.data.setdefault("npcs", {})[npc["npc_id"]] = npc
        elif task_id == "dialogs" and "dialogs" in result and isinstance(result["dialogs"], list):
            for dlg in result["dialogs"]:
                if isinstance(dlg, dict) and dlg.get("dialog_id"):
                    self.state.data.setdefault("dialogs", {})[dlg["dialog_id"]] = dlg
        elif task_id == "events" and "events" in result and isinstance(result["events"], list):
            for ev in result["events"]:
                if isinstance(ev, dict) and ev.get("event_id"):
                    self.state.data.setdefault("events", {})[ev["event_id"]] = ev
        elif task_id == "assets_prompts" and "assets" in result and isinstance(result["assets"], list):
            for asset in result["assets"]:
                if isinstance(asset, dict) and asset.get("asset_id"):
                    self.state.data.setdefault("assets", {})[asset["asset_id"]] = asset
        self.state.save()

    def _register_symbols(self, task_id: str, result: Any) -> None:
        if not isinstance(result, dict):
            return
        if task_id == "tileset" and result.get("tileset_id"):
            try:
                self.registry.register("tileset", result["tileset_id"])
            except Exception:
                pass
        elif task_id == "map_layout" and result.get("map_id"):
            try:
                self.registry.register("map", result["map_id"])
            except Exception:
                pass
        elif task_id == "npcs" and isinstance(result.get("npcs"), list):
            for npc in result["npcs"]:
                if isinstance(npc, dict) and npc.get("npc_id"):
                    try:
                        self.registry.register("npc", npc["npc_id"], npc)
                    except Exception:
                        pass
        elif task_id == "dialogs" and isinstance(result.get("dialogs"), list):
            for dlg in result["dialogs"]:
                if isinstance(dlg, dict) and dlg.get("dialog_id"):
                    try:
                        self.registry.register("dialog", dlg["dialog_id"], dlg)
                    except Exception:
                        pass
        self.state.save()

    def _write_summary(self) -> None:
        summary_path = self.output_dir / "orchestrator_summary.json"
        summary = {
            "request": self.state.get("request"),
            "platform": self.state.get("platform"),
            "completed_tasks": self.state.get("completed_tasks"),
            "maps": list(self.state.data.get("maps", {}).keys()),
            "npcs": list(self.state.data.get("npcs", {}).keys()),
            "dialogs": list(self.state.data.get("dialogs", {}).keys()),
            "assets": list(self.state.data.get("assets", {}).keys()),
        }
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[ORCH] 요약 저장: {summary_path}", flush=True)
