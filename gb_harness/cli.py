from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .client import GenerationError, generate_image, request_spec
from .generator import build_rom, generate_asset_sources, run_emulator, write_project
from .prompt import GBC_SYSTEM_PROMPT, SYSTEM_PROMPT
from .schema import SpecValidationError, validate_spec


DEFAULT_API_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_IMAGE_MODEL = "gpt-image-1"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EMULATOR = str(
    PROJECT_ROOT / "tools" / "mgba" / "mGBA.app" / "Contents" / "MacOS" / "mGBA"
)


def build_parser(default_platform: str = "gb") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate assets, build a GBDK-2020 Game Boy ROM, and optionally run it."
    )
    parser.add_argument("request", nargs="?", help="Describe the game to generate.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("generated_game"),
        help="Output directory (default: generated_game).",
    )
    parser.add_argument(
        "--platform",
        choices=("gb", "gbc"),
        default=default_platform,
        help="Target Game Boy platform.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OPENAI_MODEL", DEFAULT_MODEL),
        help=f"Chat-completions model (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("OPENAI_BASE_URL", DEFAULT_API_BASE_URL),
        help="OpenAI-compatible API base URL (default: https://api.openai.com/v1).",
    )
    parser.add_argument(
        "--image-model",
        default=os.environ.get("OPENAI_IMAGE_MODEL", DEFAULT_IMAGE_MODEL),
        help=f"Image generation model (default: {DEFAULT_IMAGE_MODEL}).",
    )
    parser.add_argument(
        "--generate-images",
        action="store_true",
        help="Generate asset PNGs through the OpenAI Images API.",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Convert asset PNGs and compile a Game Boy ROM.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Build and launch the ROM in the selected emulator.",
    )
    parser.add_argument(
        "--emulator",
        default=os.environ.get("GB_EMULATOR", DEFAULT_EMULATOR),
        help="Emulator executable path or command (also settable with GB_EMULATOR).",
    )
    parser.add_argument(
        "--emulator-debugger",
        action="store_true",
        help="Launch mGBA's command-line debugger instead of normal emulation.",
    )
    parser.add_argument(
        "--gdb-server",
        action="store_true",
        help="Launch mGBA with its GDB remote server (default port 2345).",
    )
    parser.add_argument(
        "--gbdk",
        type=Path,
        default=Path(os.environ.get("GBDK_HOME", PROJECT_ROOT / "tools" / "gbdk")),
        help="GBDK-2020 installation directory.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    return run_cli(argv)


def main_gbc(argv: list[str] | None = None) -> int:
    return run_cli(argv, default_platform="gbc")


def run_cli(argv: list[str] | None = None, default_platform: str = "gb") -> int:
    args = build_parser(default_platform).parse_args(argv)
    if (args.emulator_debugger or args.gdb_server) and not args.run:
        print("Error: debugger options require --run.", file=sys.stderr)
        return 2
    if args.emulator_debugger and args.gdb_server:
        print("Error: choose either --emulator-debugger or --gdb-server.", file=sys.stderr)
        return 2
    api_key = os.environ.get("OPENAI_API_KEY")
    existing_spec = (args.build or args.run) and (args.output / "game_spec.json").is_file()
    if not api_key and (args.generate_images or not existing_spec):
        print("Error: set OPENAI_API_KEY before running the generator.", file=sys.stderr)
        return 2
    if (args.request is None or not args.request.strip()) and not existing_spec:
        print("Error: provide a game request unless building an existing project.", file=sys.stderr)
        return 2

    try:
        if existing_spec:
            spec = validate_spec(json.loads((args.output / "game_spec.json").read_text(encoding="utf-8")))
            files = [args.output / "game_spec.json", args.output / "main.c"]
        else:
            if not api_key:
                raise GenerationError("Set OPENAI_API_KEY to generate the game specification.")
            system_prompt = (
                GBC_SYSTEM_PROMPT if args.platform == "gbc" else SYSTEM_PROMPT
            )
            spec = validate_spec(
                request_spec(
                    args.request or "",
                    api_key,
                    args.model,
                    args.api_base_url,
                    system_prompt=system_prompt,
                )
            )
        files = write_project(spec, args.output, args.platform)

        if args.generate_images:
            for asset in spec["graphics_assets"]:
                image_path = args.output / "assets" / f'{asset["asset_id"]}.png'
                image_prompt = asset["image_prompt"]
                if asset["type"] == "sprite":
                    image_prompt += " Design this as a clearly readable single 8x8 Game Boy hardware sprite."
                if args.platform == "gbc":
                    image_prompt += (
                        " Use up to 8 Game Boy Color palettes with at most 4 colors each, "
                        "using 15-bit RGB colors."
                    )
                generate_image(
                    image_prompt, image_path, api_key, args.image_model, args.api_base_url
                )
                print(f"Generated image: {image_path}")

        if args.build or args.run:
            asset_sources = generate_asset_sources(
                spec["graphics_assets"], args.output, args.gbdk, args.platform
            )
            rom_path = build_rom(args.output, args.gbdk, args.platform)
            files.extend(asset_sources)
            files.append(rom_path)
        if args.run:
            process_id = run_emulator(
                rom_path,
                args.emulator,
                args.emulator_debugger,
                args.gdb_server,
            )
            print(f"Emulator started (PID {process_id}).")
    except (GenerationError, SpecValidationError, OSError, RuntimeError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print("Generated project files:")
    for path in files:
        print(f"  {path}")
    return 0
