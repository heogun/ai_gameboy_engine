import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from gb_harness.gbc_image_normalizer import normalize_gbc_image
from gb_harness.generator import render_c_source, write_project
from gb_harness.schema import SpecValidationError, validate_spec


def valid_spec() -> dict:
    return {
        "global_variables": "UINT8 p_x = 80;\nUINT8 p_y = 72;",
        "logic_update_loop": "UINT8 keys = joypad();\nif (keys & J_RIGHT) p_x++;\nmove_sprite(0, p_x, p_y);",
        "graphics_assets": [
            {
                "asset_id": "spr_player",
                "type": "sprite",
                "image_prompt": (
                    "pixel art, 16-bit retro, flat colors, white background, "
                    "isolated object: a cheerful adventurer"
                ),
            }
        ],
        "audio_sfx": [
            {
                "trigger_event": "on_jump",
                "gb_registers": {
                    "NR10_REG": "0x16",
                    "NR11_REG": "0x40",
                    "NR12_REG": "0x73",
                    "NR13_REG": "0x00",
                    "NR14_REG": "0xC3",
                },
            }
        ],
        "bgm_mml": "T120 O4 C8 E8 G8 O5 C4",
    }


class SchemaTests(unittest.TestCase):
    def test_accepts_valid_spec(self) -> None:
        self.assertEqual(validate_spec(valid_spec()), valid_spec())

    def test_rejects_missing_image_prompt_requirements(self) -> None:
        spec = valid_spec()
        spec["graphics_assets"][0]["image_prompt"] = "A pixel-art hero"
        with self.assertRaisesRegex(SpecValidationError, "missing required text"):
            validate_spec(spec)

    def test_rejects_template_redefinition_in_c_fragments(self) -> None:
        spec = valid_spec()
        spec["logic_update_loop"] = "void main() {}"
        with self.assertRaisesRegex(SpecValidationError, "C fragment"):
            validate_spec(spec)

    def test_rejects_non_string_asset_type(self) -> None:
        spec = valid_spec()
        spec["graphics_assets"][0]["type"] = []
        with self.assertRaisesRegex(SpecValidationError, "type must be"):
            validate_spec(spec)


class GeneratorTests(unittest.TestCase):
    def test_renders_template_and_asset_includes(self) -> None:
        source = render_c_source(valid_spec())
        self.assertIn('#include "assets/spr_player.c"', source)
        self.assertIn("UINT8 p_x = 80;", source)
        self.assertIn("move_sprite(0, p_x, p_y);", source)
        self.assertIn("set_sprite_data(0, sizeof(spr_player_tiles) / 16, spr_player_tiles);", source)
        self.assertIn("wait_vbl_done();", source)
        self.assertEqual(source.count("void main()"), 1)

    def test_renders_color_gameboy_palettes_and_map_attributes(self) -> None:
        spec = valid_spec()
        spec["graphics_assets"].append(
            {
                "asset_id": "bg_scene",
                "type": "background",
                "image_prompt": (
                    "pixel art, 16-bit retro, flat colors, white background, isolated object"
                ),
            }
        )
        source = render_c_source(spec, "gbc")
        self.assertIn("#include <gb/cgb.h>", source)
        self.assertIn(
            "set_sprite_palette(0, sizeof(spr_player_palettes) / (4 * sizeof(palette_color_t)), spr_player_palettes);",
            source,
        )
        self.assertIn("set_sprite_prop(0, 0);", source)
        self.assertIn(
            "set_bkg_palette(0, sizeof(bg_scene_palettes) / (4 * sizeof(palette_color_t)), bg_scene_palettes);",
            source,
        )
        self.assertIn("set_bkg_attributes(0, 0, 20, 18, bg_scene_map_attributes);", source)

    def test_gbc_normalizer_keeps_multiple_15_bit_palettes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            image_path = Path(temporary_directory) / "background.png"
            image = Image.new("RGB", (160, 144), "black")
            draw = ImageDraw.Draw(image)
            for tile_y in range(18):
                for tile_x in range(20):
                    base = (tile_x * 5 + tile_y * 3) % 31
                    colors = [
                        tuple(min(255, ((base + offset * 7) % 32) * 8) for _ in range(3))
                        for offset in range(4)
                    ]
                    for pixel_y in range(8):
                        for pixel_x in range(8):
                            draw.point(
                                (tile_x * 8 + pixel_x, tile_y * 8 + pixel_y),
                                fill=colors[(pixel_x + pixel_y) % 4],
                            )
            image.save(image_path)

            normalize_gbc_image(image_path, "background")

            with Image.open(image_path) as normalized:
                colors = set(normalized.convert("RGB").getdata())
                tile_palettes = set()
                for top in range(0, 144, 8):
                    for left in range(0, 160, 8):
                        tile = normalized.crop((left, top, left + 8, top + 8))
                        tile_palettes.add(tuple(sorted(set(tile.getdata()))))
                self.assertGreater(len(colors), 4)
                self.assertLessEqual(len(tile_palettes), 8)
                self.assertTrue(
                    all(
                        (((channel * 31 + 127) // 255) * 255) // 31 == channel
                        for color in colors
                        for channel in color
                    )
                )

    def test_writes_spec_source_and_asset_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "game"
            files = write_project(valid_spec(), output)
            self.assertEqual(len(files), 3)
            self.assertTrue((output / "main.c").is_file())
            self.assertEqual(
                json.loads((output / "game_spec.json").read_text(encoding="utf-8")),
                valid_spec(),
            )
            prompts = json.loads(
                (output / "assets" / "asset_prompts.json").read_text(encoding="utf-8")
            )
            self.assertEqual(prompts, valid_spec()["graphics_assets"])


if __name__ == "__main__":
    unittest.main()
