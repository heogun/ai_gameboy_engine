import json
import base64
import binascii
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
) -> None:
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


def request_spec(
    user_request: str,
    api_key: str | None = None,
    model: str = "deepseek/deepseek-chat-v3-0324:free",
    base_url: str = "https://openrouter.ai/api/v1",
    system_prompt: str = SYSTEM_PROMPT,
    timeout: float = 90,
) -> Any:
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
    try:
        return json.loads(content)
    except json.JSONDecodeError as error:
        raise GenerationError("The model response was not valid JSON.") from error
