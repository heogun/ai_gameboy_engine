import re
from typing import Any


class SpecValidationError(ValueError):
    """Raised when an AI response does not match the game specification schema."""


_ASSET_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_REGISTER_VALUE = re.compile(r"^0x[0-9A-Fa-f]{1,2}$")
_REQUIRED_IMAGE_TEXT = (
    "pixel art",
    "16-bit retro",
    "flat colors",
    "white background",
    "isolated object",
)
_REGISTER_NAMES = {"NR10_REG", "NR11_REG", "NR12_REG", "NR13_REG", "NR14_REG"}
_TOP_LEVEL_KEYS = {
    "global_variables",
    "logic_update_loop",
    "graphics_assets",
    "audio_sfx",
    "bgm_mml",
}


def validate_spec(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SpecValidationError("The response must be a JSON object.")
    if set(value) != _TOP_LEVEL_KEYS:
        missing = sorted(_TOP_LEVEL_KEYS - set(value))
        extra = sorted(set(value) - _TOP_LEVEL_KEYS)
        details = []
        if missing:
            details.append(f"missing keys: {', '.join(missing)}")
        if extra:
            details.append(f"unexpected keys: {', '.join(extra)}")
        raise SpecValidationError("Invalid top-level schema (" + "; ".join(details) + ").")

    _validate_c_fragment(value["global_variables"], "global_variables")
    _validate_c_fragment(value["logic_update_loop"], "logic_update_loop")

    assets = value["graphics_assets"]
    if not isinstance(assets, list):
        raise SpecValidationError("graphics_assets must be an array.")
    asset_ids: set[str] = set()
    sprite_count = 0
    background_count = 0
    for index, asset in enumerate(assets):
        label = f"graphics_assets[{index}]"
        _require_keys(asset, {"asset_id", "type", "image_prompt"}, label)
        asset_id = asset["asset_id"]
        if not isinstance(asset_id, str) or not _ASSET_ID.fullmatch(asset_id):
            raise SpecValidationError(f"{label}.asset_id must be a valid C identifier.")
        if asset_id in asset_ids:
            raise SpecValidationError(f"Duplicate asset_id: {asset_id}.")
        asset_ids.add(asset_id)
        if not isinstance(asset["type"], str) or asset["type"] not in {"sprite", "background"}:
            raise SpecValidationError(f"{label}.type must be 'sprite' or 'background'.")
        if asset["type"] == "sprite":
            sprite_count += 1
        else:
            background_count += 1
        image_prompt = asset["image_prompt"]
        if not isinstance(image_prompt, str) or not image_prompt.strip():
            raise SpecValidationError(f"{label}.image_prompt must be a non-empty string.")
        lowered_prompt = image_prompt.lower()
        missing_terms = [term for term in _REQUIRED_IMAGE_TEXT if term not in lowered_prompt]
        if missing_terms:
            raise SpecValidationError(
                f"{label}.image_prompt is missing required text: {', '.join(missing_terms)}."
            )
    if sprite_count > 40:
        raise SpecValidationError("graphics_assets cannot contain more than 40 sprites.")
    if background_count > 1:
        raise SpecValidationError("graphics_assets can contain at most one background.")

    sounds = value["audio_sfx"]
    if not isinstance(sounds, list):
        raise SpecValidationError("audio_sfx must be an array.")
    for index, sound in enumerate(sounds):
        label = f"audio_sfx[{index}]"
        _require_keys(sound, {"trigger_event", "gb_registers"}, label)
        if not isinstance(sound["trigger_event"], str) or not sound["trigger_event"].strip():
            raise SpecValidationError(f"{label}.trigger_event must be a non-empty string.")
        registers = sound["gb_registers"]
        _require_keys(registers, _REGISTER_NAMES, f"{label}.gb_registers")
        for name, register_value in registers.items():
            if not isinstance(register_value, str) or not _REGISTER_VALUE.fullmatch(register_value):
                raise SpecValidationError(
                    f"{label}.gb_registers.{name} must be a hexadecimal byte string such as '0x16'."
                )

    bgm = value["bgm_mml"]
    if bgm is not None and (not isinstance(bgm, str) or not bgm.strip()):
        raise SpecValidationError("bgm_mml must be null or a non-empty string.")
    return value


def _validate_c_fragment(value: Any, field: str) -> None:
    if not isinstance(value, str):
        raise SpecValidationError(f"{field} must be a string.")
    forbidden = ("#include", "void main", "while(1)", "while (1)")
    lowered = value.lower()
    if any(token in lowered for token in forbidden):
        raise SpecValidationError(
            f"{field} must be a C fragment and cannot redefine the harness template."
        )


def _require_keys(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise SpecValidationError(f"{label} must contain exactly: {', '.join(sorted(expected))}.")
