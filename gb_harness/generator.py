import json
from pathlib import Path
import shutil
import socket
import subprocess
import time
from typing import Any

from .gbc_image_normalizer import normalize_gbc_image


def render_c_source(spec: dict[str, Any], platform: str = "gb") -> str:
    asset_includes = "".join(
        f'#include "assets/{asset["asset_id"]}.c"\n' for asset in spec["graphics_assets"]
    )
    asset_initializers = _render_asset_initializers(spec["graphics_assets"], platform)
    cgb_include = "#include <gb/cgb.h>\n" if platform == "gbc" else ""
    sprite_mode = "    SPRITES_8x8;\n" if any(
        asset["type"] == "sprite" for asset in spec["graphics_assets"]
    ) else ""
    show_background = "    SHOW_BKG;\n" if any(
        asset["type"] == "background" for asset in spec["graphics_assets"]
    ) else ""
    return (
        "#include <gb/gb.h>\n"
        f"{cgb_include}"
        f"{asset_includes}\n"
        f'{spec["global_variables"].rstrip()}\n\n'
        "void main() {\n"
        "    DISPLAY_ON;\n"
        f"{sprite_mode}"
        "    SHOW_SPRITES;\n"
        f"{show_background}"
        f"{asset_initializers}"
        "    while(1) {\n"
        f'{_indent(spec["logic_update_loop"])}\n'
        "        wait_vbl_done();\n"
        "    }\n"
        "}\n"
    )


def write_project(
    spec: dict[str, Any], output_dir: Path, platform: str = "gb"
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    spec_path = output_dir / "game_spec.json"
    source_path = output_dir / "main.c"
    prompts_path = assets_dir / "asset_prompts.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    source_path.write_text(render_c_source(spec, platform), encoding="utf-8")
    prompts_path.write_text(
        json.dumps(spec["graphics_assets"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return [spec_path, source_path, prompts_path]


def generate_asset_sources(
    assets: list[dict[str, Any]],
    output_dir: Path,
    gbdk_root: Path,
    platform: str = "gb",
) -> list[Path]:
    if platform == "gbc" and sum(asset["type"] == "sprite" for asset in assets) > 8:
        raise RuntimeError(
            "The GBC harness supports at most 8 independently paletted sprite assets."
        )
    png2asset = gbdk_root / "bin" / "png2asset"
    if not png2asset.is_file():
        raise FileNotFoundError(f"GBDK png2asset not found: {png2asset}")
    assets_dir = output_dir / "assets"
    generated: list[Path] = []
    for asset in assets:
        asset_id = asset["asset_id"]
        image_path = assets_dir / f"{asset_id}.png"
        if not image_path.is_file():
            raise FileNotFoundError(
                f"Missing image for {asset_id}: {image_path}. Generate images or add the PNG."
            )
        if platform == "gbc":
            normalize_gbc_image(image_path, asset["type"])
        else:
            _normalize_image(image_path, asset["type"])
        source_path = assets_dir / f"{asset_id}.c"
        command = [str(png2asset), str(image_path), "-o", str(source_path)]
        if asset["type"] == "sprite":
            command.append("-spr8x8")
        else:
            command.append("-map")
        if platform == "gbc":
            command.extend(["-max_palettes", "8"])
            if asset["type"] == "background":
                command.append("-use_map_attributes")
        _run(command, cwd=output_dir)
        generated.append(source_path)
    return generated


def build_rom(output_dir: Path, gbdk_root: Path, platform: str = "gb") -> Path:
    lcc = gbdk_root / "bin" / "lcc"
    if not lcc.is_file():
        raise FileNotFoundError(f"GBDK lcc compiler not found: {lcc}")
    source_path = output_dir / "main.c"
    if not source_path.is_file():
        raise FileNotFoundError(f"Generated C source not found: {source_path}")
    rom_path = output_dir / ("game.gbc" if platform == "gbc" else "game.gb")
    command = [str(lcc)]
    if platform == "gbc":
        command.append("-Wm-yC")
    command.extend(["-o", str(rom_path), str(source_path)])
    _run(command, cwd=output_dir)
    return rom_path


def run_emulator(
    rom_path: Path,
    emulator: str,
    debugger: bool = False,
    gdb_server: bool = False,
) -> int:
    executable = shutil.which(emulator)
    if executable is None and Path(emulator).is_file():
        executable = emulator
    if executable is None:
        raise FileNotFoundError(
            f"Emulator executable not found: {emulator}. Install an emulator and set --emulator."
        )
    command = [executable]
    if debugger:
        command.append("--debug")
    if gdb_server:
        command.append("--gdb")
    command.append(str(rom_path))
    try:
        process = subprocess.Popen(command, cwd=rom_path.parent)
    except OSError as error:
        raise RuntimeError(f"Could not launch emulator {executable}: {error}") from error
    time.sleep(0.25)
    return_code = process.poll()
    if return_code is not None:
        raise RuntimeError(f"Emulator exited immediately with status {return_code}.")
    if gdb_server:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and process.poll() is None:
            try:
                with socket.create_connection(("127.0.0.1", 2345), timeout=0.25):
                    return process.pid
            except OSError:
                time.sleep(0.1)
        raise RuntimeError(
            f"mGBA did not start its GDB server on localhost:2345 (PID {process.pid})."
        )
    return process.pid


def _normalize_image(image_path: Path, asset_type: str) -> None:
    try:
        from PIL import Image, ImageChops
    except ImportError as error:
        raise RuntimeError(
            "Image conversion requires Pillow. Install it with: python -m pip install Pillow"
        ) from error

    target_size = (8, 8) if asset_type == "sprite" else (80, 72)
    with Image.open(image_path) as image:
        image = image.convert("RGBA" if asset_type == "sprite" else "RGB")
        source_ratio = image.width / image.height
        target_ratio = target_size[0] / target_size[1]
        if source_ratio > target_ratio:
            resized_height = target_size[1]
            resized_width = max(1, round(resized_height * source_ratio))
        else:
            resized_width = target_size[0]
            resized_height = max(1, round(resized_width / source_ratio))
        image = image.resize((resized_width, resized_height), Image.Resampling.NEAREST)
        left = (resized_width - target_size[0]) // 2
        top = (resized_height - target_size[1]) // 2
        image = image.crop((left, top, left + target_size[0], top + target_size[1]))
        if asset_type == "sprite":
            rgb_image = image.convert("RGB")
            white_background = Image.eval(
                rgb_image.convert("L"), lambda value: 0 if value >= 245 else 255
            )
            alpha = ImageChops.multiply(
                Image.eval(image.getchannel("A"), lambda value: 255 if value >= 128 else 0),
                white_background,
            )
            image = rgb_image.quantize(
                colors=4, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
            ).convert("RGB")
            image.putalpha(alpha)
        else:
            image = image.quantize(
                colors=4, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
            )
        if asset_type == "background":
            image = image.resize((160, 144), Image.Resampling.NEAREST)
        image.save(image_path, format="PNG")


def _render_asset_initializers(assets: list[dict[str, Any]], platform: str) -> str:
    lines: list[str] = []
    if platform == "gbc":
        lines.extend(["    if (_cpu == CGB_TYPE) {"])
        sprite_index = 0
        for asset in assets:
            asset_id = asset["asset_id"]
            if asset["type"] == "sprite":
                palette_index = sprite_index % 8
                lines.extend(
                    [
                        f"        set_sprite_palette({palette_index}, sizeof({asset_id}_palettes) / (4 * sizeof(palette_color_t)), {asset_id}_palettes);",
                        f"        set_sprite_prop({sprite_index}, {palette_index});",
                    ]
                )
                sprite_index += 1
            else:
                lines.extend(
                    [
                        f"        set_bkg_palette(0, sizeof({asset_id}_palettes) / (4 * sizeof(palette_color_t)), {asset_id}_palettes);",
                        f"        set_bkg_attributes(0, 0, 20, 18, {asset_id}_map_attributes);",
                    ]
                )
        lines.append("    }")

    sprite_index = 0
    tile_index = 0
    for asset in assets:
        asset_id = asset["asset_id"]
        if asset["type"] == "sprite":
            lines.extend(
                [
                    f"    set_sprite_data({tile_index}, sizeof({asset_id}_tiles) / 16, {asset_id}_tiles);",
                    f"    set_sprite_tile({sprite_index}, {tile_index});",
                    f"    move_sprite({sprite_index}, 80, 72);",
                ]
            )
            tile_index += 1
            sprite_index += 1
        else:
            lines.extend(
                [
                    f"    set_bkg_data(0, sizeof({asset_id}_tiles) / 16, {asset_id}_tiles);",
                    f"    set_bkg_tiles(0, 0, 20, 18, {asset_id}_map);",
                ]
            )
    return "".join(f"{line}\n" for line in lines)


def _run(command: list[str], cwd: Path) -> None:
    try:
        subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        details = (error.stderr or error.stdout or "").strip()
        raise RuntimeError(
            f"Command failed with exit code {error.returncode}: {' '.join(command)}"
            + (f"\n{details}" if details else "")
        ) from error
    except OSError as error:
        raise RuntimeError(f"Could not run command {command[0]}: {error}") from error


def _indent(fragment: str) -> str:
    if not fragment.strip():
        return "        "
    return "\n".join(f"        {line}" if line else "" for line in fragment.rstrip().splitlines())
