from __future__ import annotations

import shutil
from pathlib import Path


TEMPLATES = Path(__file__).parent / "templates"


def inject_korean_support(output_dir: Path) -> list[Path]:
    korean_dir = output_dir / "korean"
    korean_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for name in ["hangul_text.c", "hangul_text.h"]:
        src = TEMPLATES / name
        if src.is_file():
            dst = korean_dir / name
            shutil.copy2(src, dst)
            copied.append(dst)
    return copied
