from __future__ import annotations

import json
import base64
import binascii
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .prompt import SYSTEM_PROMPT


class GenerationError(RuntimeError):
    """Raised when the model cannot return a usable game specification."""


def generate_image(
    prompt: str,
    output_path: Path,
    api_key: str | None = None,
    model: str = "gpt-image-1",
    base_url: str = "https://api.openai.com/v1",
    timeout: float = 180,
    backend: str | None = None,
    image_backend: str | None = None,
) -> None:
    backend_resolved = (image_backend or backend or os.environ.get("IMAGE_BACKEND") or "openai").lower()

    if backend_resolved == "ideogram":
        ideogram_key = api_key or os.environ.get("IDEOGRAM_API_KEY")
        if not ideogram_key:
            raise GenerationError("Set IDEOGRAM_API_KEY to generate images with Ideogram.")
        _generate_image_ideogram(prompt, output_path, ideogram_key, timeout)
        return

    if not api_key:
        raise GenerationError("Set an API key to generate images with the image backend.")
    url = base_url.rstrip("/") + "/images/generations"
    payload = {
        "model": model,
        "prompt": prompt,
        "size": "1024x1024",
        "n": 1,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise GenerationError(
            f"Image API returned HTTP {error.code}: {details[:1000]}"
        ) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise GenerationError(f"Could not reach the image API: {error}") from error

    try:
        envelope = json.loads(response_body)
        encoded_image = envelope["data"][0]["b64_json"]
        image_bytes = base64.b64decode(encoded_image, validate=True)
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, binascii.Error) as error:
        raise GenerationError("The image API returned an unexpected response.") from error
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_bytes)


def _generate_image_ideogram(
    prompt: str,
    output_path: Path,
    api_key: str,
    timeout: float = 180,
) -> None:
    url = "https://api.ideogram.ai/generate"
    payload = {
        "image_request": {
            "prompt": prompt,
            "aspect_ratio": "1x1",
            "model": "V_2",
            "magic_prompt_option": "AUTO",
            "style_type": "GENERAL",
        }
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Api-Key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise GenerationError(
            f"Ideogram API returned HTTP {error.code}: {details[:1000]}"
        ) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise GenerationError(f"Could not reach Ideogram API: {error}") from error

    try:
        envelope = json.loads(response_body)
        image_url = envelope["data"][0]["url"]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
        raise GenerationError("The Ideogram API returned an unexpected response shape.") from error

    try:
        img_req = urllib.request.Request(image_url, method="GET")
        with urllib.request.urlopen(img_req, timeout=timeout) as response:
            image_bytes = response.read()
    except (urllib.error.URLError, TimeoutError) as error:
        raise GenerationError(f"Could not download image from Ideogram: {error}") from error

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_bytes)


def request_spec(
    user_request: str,
    api_key: str | None = None,
    model: str = "deepseek/deepseek-chat-v3-0324:free",
    base_url: str = "https://openrouter.ai/api/v1",
    system_prompt: str = SYSTEM_PROMPT,
    timeout: float = 90,
) -> Any:
    print(f"[INFO] OpenRouter에 게임 스펙 요청 중... (모델: {model})", flush=True)
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_request},
        ],
    }
    headers = {
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/heogun/ai_gameboy_engine",
        "X-Title": "gbdk-game-harness",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            print("[INFO] 응답 수신 중...", flush=True)
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise GenerationError(
            f"Model API returned HTTP {error.code}: {details[:1000]}"
        ) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise GenerationError(f"Could not reach the model API: {error}") from error

    try:
        envelope = json.loads(response_body)
        content = envelope["choices"][0]["message"]["content"]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
        raise GenerationError("The model API returned an unexpected response shape.") from error
    if not isinstance(content, str):
        raise GenerationError("The model API did not return text content.")
    print("[INFO] JSON 파싱 중...", flush=True)
    try:
        result = json.loads(content)
        print("[INFO] 스펙 생성 완료", flush=True)
        return result
    except json.JSONDecodeError as error:
        raise GenerationError("The model response was not valid JSON.") from error
