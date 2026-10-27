from __future__ import annotations

from pathlib import Path
from typing import Any


def render_guide(spec: dict[str, Any], output_dir: Path, platform: str) -> str:
    assets = spec.get("graphics_assets", [])
    rom_name = "game.gbc" if platform == "gbc" else "game.gb"
    harness = "gbc_harness" if platform == "gbc" else "gb_harness"

    lines: list[str] = []
    lines.append("# Game Boy 게임 제작 가이드 (무료 OpenRouter 기반)")
    lines.append("")
    lines.append("이 가이드는 스펙만 생성된 상태에서, 이미지 생성부터 빌드까지 직접 진행하는 순서입니다.")
    lines.append("")

    lines.append("## 1) 이미지 생성")
    lines.append("아래 프롬프트를 복사해서 무료 이미지 생성 툴에 넣어 PNG로 만드세요.")
    lines.append("- 추천: ChatGPT 이미지, Google Gemini, Ideogram, Bing Image Creator")
    lines.append("")

    if not assets:
        lines.append("> 에셋이 없습니다.")
    else:
        for asset in assets:
            asset_id = asset["asset_id"]
            asset_type = asset["type"]
            prompt = asset["image_prompt"]
            lines.append(f"### {asset_id} ({asset_type})")
            lines.append(f"파일명: `assets/{asset_id}.png`")
            lines.append("```text")
            lines.append(prompt)
            if asset_type == "sprite":
                lines.append("Design this as a clearly readable single 8x8 Game Boy hardware sprite.")
            if platform == "gbc":
                lines.append("Use up to 8 Game Boy Color palettes with at most 4 colors each, using 15-bit RGB colors.")
            lines.append("```")
            lines.append("")

    lines.append("## 2) 이미지 배치")
    lines.append(f"생성한 PNG를 아래 경로에 저장하세요: `{output_dir}/assets/`")
    lines.append("")
    for asset in assets:
        lines.append(f"- {asset['asset_id']}.png")
    lines.append("")

    lines.append("## 3) 빌드 & 실행")
    lines.append("모든 PNG를 배치한 뒤 터미널에서 실행하세요.")
    lines.append("")
    lines.append("```bash")
    lines.append(f"python -m {harness} --build --run")
    lines.append("```")
    lines.append("")
    lines.append(f"- ROM 위치: `{output_dir}/{rom_name}`")
    lines.append("- `main.c`, `game_spec.json` 을 수정해서 로직/구성을 직접 바꿔도 됩니다.")
    lines.append("")

    return "\n".join(lines) + "\n"


def write_guide(spec: dict[str, Any], output_dir: Path, platform: str) -> Path:
    guide_path = output_dir / "GUIDE.md"
    guide_path.write_text(render_guide(spec, output_dir, platform), encoding="utf-8")
    return guide_path
