from pathlib import Path


GBC_MAX_PALETTES = 8
COLORS_PER_PALETTE = 4
COLOR_CHANNEL_LEVELS = 31


def normalize_gbc_image(image_path: Path, asset_type: str) -> None:
    try:
        from PIL import Image, ImageChops
    except ImportError as error:
        raise RuntimeError(
            "Image conversion requires Pillow. Install it with: python -m pip install Pillow"
        ) from error

    target_size = (8, 8) if asset_type == "sprite" else (80, 72)
    with Image.open(image_path) as source:
        source = source.convert("RGBA" if asset_type == "sprite" else "RGB")
        resized_size = _fit_size(source.size, target_size)
        image = source.resize(resized_size, Image.Resampling.NEAREST)
        left = (resized_size[0] - target_size[0]) // 2
        top = (resized_size[1] - target_size[1]) // 2
        image = image.crop((left, top, left + target_size[0], top + target_size[1]))
        if asset_type == "sprite":
            image = _make_sprite_background_transparent(image, Image, ImageChops)
        else:
            image = image.resize((160, 144), Image.Resampling.NEAREST)

        normalized = _apply_hardware_palettes(image, Image)
        normalized.save(image_path, format="PNG")


def _fit_size(source_size: tuple[int, int], target_size: tuple[int, int]) -> tuple[int, int]:
    source_ratio = source_size[0] / source_size[1]
    target_ratio = target_size[0] / target_size[1]
    if source_ratio > target_ratio:
        height = target_size[1]
        return max(target_size[0], round(height * source_ratio)), height
    width = target_size[0]
    return width, max(target_size[1], round(width / source_ratio))


def _make_sprite_background_transparent(image, image_module, image_chops):
    rgb_image = image.convert("RGB")
    white_background = image_module.eval(
        rgb_image.convert("L"), lambda value: 0 if value >= 245 else 255
    )
    alpha = image_chops.multiply(
        image_module.eval(image.getchannel("A"), lambda value: 255 if value >= 128 else 0),
        white_background,
    )
    image = rgb_image.copy()
    image.putalpha(alpha)
    return image


def _apply_hardware_palettes(image, image_module):
    tiles = []
    palette_candidates: dict[tuple[tuple[int, int, int], ...], None] = {}
    for top in range(0, image.height, 8):
        for left in range(0, image.width, 8):
            tile = image.crop((left, top, left + 8, top + 8))
            quantized = tile.convert("RGB").quantize(
                colors=COLORS_PER_PALETTE,
                method=image_module.Quantize.MEDIANCUT,
                dither=image_module.Dither.NONE,
            )
            snapped_pixels = [_to_rgb555(color) for color in quantized.convert("RGB").getdata()]
            palette = tuple(sorted(set(snapped_pixels)))
            palette_candidates[palette] = None
            tiles.append((left, top, snapped_pixels))

    candidate_palettes = list(palette_candidates)
    selected_palettes = _select_palettes(candidate_palettes)
    pixels = list(image.convert("RGB").getdata())
    image_width = image.width

    for left, top, tile_pixels in tiles:
        palette = min(
            selected_palettes,
            key=lambda candidate: _palette_distance(tile_pixels, candidate),
        )
        for offset, pixel in enumerate(tile_pixels):
            x = left + offset % 8
            y = top + offset // 8
            pixels[y * image_width + x] = min(
                palette,
                key=lambda color: _color_distance(pixel, color),
            )

    normalized = image_module.new("RGB", image.size)
    normalized.putdata(pixels)
    if image.mode == "RGBA":
        normalized.putalpha(image.getchannel("A"))
    return normalized


def _select_palettes(candidate_palettes):
    selected = [candidate_palettes[0]]
    while len(selected) < min(GBC_MAX_PALETTES, len(candidate_palettes)):
        candidate = max(
            candidate_palettes,
            key=lambda palette: min(
                _palette_distance(palette, existing) for existing in selected
            ),
        )
        if candidate in selected:
            break
        selected.append(candidate)

    if len(candidate_palettes) <= GBC_MAX_PALETTES:
        return candidate_palettes
    return selected


def _palette_distance(colors, palette) -> int:
    return sum(min(_color_distance(color, option) for option in palette) for color in colors)


def _color_distance(first: tuple[int, int, int], second: tuple[int, int, int]) -> int:
    return sum((first[channel] - second[channel]) ** 2 for channel in range(3))


def _to_rgb555(color: tuple[int, int, int]) -> tuple[int, int, int]:
    return tuple(
        (((channel * COLOR_CHANNEL_LEVELS + 127) // 255) * 255) // COLOR_CHANNEL_LEVELS
        for channel in color
    )
