#!/usr/bin/env python3
"""Shared helpers for ai-commerce-video scripts."""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import subprocess
import shutil
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse, urlunparse
from pathlib import Path
from typing import Any, Dict, List, Optional


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = SKILL_ROOT / "assets" / "templates" / "model-config.example.json"
KEY_ENV_NAMES = ("AI_COMMERCE_VIDEO_API_KEY", "YUNWU_API_KEY", "XAI_API_KEY")
ENV_FILE_ENV = "AI_COMMERCE_VIDEO_ENV_FILE"
PROXY_URL_ENV = "AI_COMMERCE_VIDEO_PROXY_URL"
DEFAULT_ENV_FILES = (
    Path.home() / ".codex" / "ai-commerce-video-mikuapi.env",
    Path.home() / ".codex" / "ai-commerce-video.env",
    SKILL_ROOT.parent / ".ai-commerce-video.env",
    SKILL_ROOT / ".env.local",
)


class ScriptError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def local_asset_digest(asset: dict) -> str:
    if asset.get("kind") != "file":
        return ""
    path = Path(str(asset_value(asset))).expanduser()
    if not path.is_file():
        return ""
    return sha256_file(path)


def asset_value(asset: dict | None) -> str:
    if not isinstance(asset, dict):
        return ""
    return str(asset.get("value") or asset.get("path") or asset.get("url") or "")


def model_supports_reference_images(model: dict) -> bool:
    return bool(model.get("supports_multiple_references"))


def model_provider(model: dict) -> str:
    return str(model.get("provider") or "").strip().lower()


def model_api_key_names(model: dict) -> list[str] | None:
    names = model.get("api_key_env_names")
    if isinstance(names, list) and names:
        return [str(name) for name in names if str(name).strip()]
    return None


def model_api_key_keychain_service(model: dict) -> str:
    return str(model.get("api_key_keychain_service") or "").strip()


def model_auth_scheme(model: dict) -> str:
    return str(model.get("auth_scheme") or "Bearer")


def prompt_limits(model: Dict[str, Any]) -> tuple[Optional[int], Optional[int]]:
    """Return the configured safe prompt budget and hard Provider limit."""
    max_value = model.get("max_prompt_chars")
    budget_value = model.get("prompt_budget_chars")
    maximum = int(max_value) if max_value not in (None, "") else None
    budget = int(budget_value) if budget_value not in (None, "") else maximum
    return budget, maximum


def validate_provider_prompt_length(prompt: str, model: Dict[str, Any], shot_id: str = "") -> None:
    """Block an oversized exact payload before any Provider submission."""
    text = str(prompt or "")
    prefix = f"{shot_id} " if shot_id else ""
    budget, maximum = prompt_limits(model)
    if maximum is not None and len(text) > maximum:
        raise ScriptError(
            f"{prefix}prompt length {len(text)} exceeds model max_prompt_chars={maximum}. "
            "Recompile the Provider prompt before paid generation."
        )
    if budget is not None and len(text) > budget:
        raise ScriptError(
            f"{prefix}prompt length {len(text)} exceeds configured prompt_budget_chars={budget}. "
            "Recompile the Provider prompt before paid generation."
        )


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ScriptError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ScriptError(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip().strip('"').strip("'")
    if not key:
        return None
    return key, value


def load_env_file(path: Path) -> bool:
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = parse_env_line(line)
        if parsed:
            key, value = parsed
            if not os.environ.get(key):
                os.environ[key] = value
    return True


def load_runtime_env() -> list[str]:
    loaded: list[str] = []
    explicit = os.getenv(ENV_FILE_ENV)
    candidates = [Path(explicit).expanduser()] if explicit else list(DEFAULT_ENV_FILES)
    for path in candidates:
        resolved = path.expanduser().resolve()
        if load_env_file(resolved):
            loaded.append(str(resolved))
    return loaded


def load_config(config_path: Optional[str]) -> Dict[str, Any]:
    load_runtime_env()
    path = Path(config_path).expanduser().resolve() if config_path else DEFAULT_CONFIG
    return load_json(path)


def model_env_name(model_key: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in model_key.upper()).strip("_")
    return f"AI_COMMERCE_VIDEO_MODEL_{safe}"


def model_base_url_env_name(model_key: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in model_key.upper()).strip("_")
    return f"AI_COMMERCE_VIDEO_BASE_URL_{safe}"


def get_model_config(config: Dict[str, Any], model_key: Optional[str]) -> Dict[str, Any]:
    load_runtime_env()
    requested_key = model_key
    key = model_key or config.get("default_model")
    models = config.get("models") or {}
    if not key or key not in models:
        raise ScriptError(f"Unknown model key: {key!r}")
    model = dict(models[key])
    model["key"] = key
    allow_legacy_global_overrides = bool(model.get("allow_legacy_global_overrides", True))
    key_specific_base_url = os.getenv(model_base_url_env_name(key))
    if key_specific_base_url:
        model["base_url"] = key_specific_base_url
    elif allow_legacy_global_overrides and os.getenv("AI_COMMERCE_VIDEO_BASE_URL") and (requested_key is None or key == config.get("default_model")):
        model["base_url"] = os.environ["AI_COMMERCE_VIDEO_BASE_URL"]
    key_specific_model = os.getenv(model_env_name(key))
    if key_specific_model:
        model["model"] = key_specific_model
    elif allow_legacy_global_overrides and os.getenv("AI_COMMERCE_VIDEO_MODEL"):
        # Keep the legacy/global model override scoped to the default route.
        # Otherwise a private env file for a single-image model can accidentally
        # override a deliberately selected multi-reference model key.
        if requested_key is None or key == config.get("default_model"):
            model["model"] = os.environ["AI_COMMERCE_VIDEO_MODEL"]
    if model.get("base_url"):
        model["base_url"] = normalize_base_url(model["base_url"])
    return model


def find_api_key(
    required: bool = True,
    names: tuple[str, ...] | list[str] | None = None,
    keychain_service: str = "",
) -> Optional[str]:
    loaded = load_runtime_env()
    key_names = tuple(names or KEY_ENV_NAMES)
    for name in key_names:
        value = os.getenv(name)
        if value:
            return value
    service = str(keychain_service or "").strip()
    security = None if os.getenv("AI_COMMERCE_VIDEO_DISABLE_KEYCHAIN") == "1" else shutil.which("security")
    if service and security:
        result = subprocess.run(
            [security, "find-generic-password", "-w", "-s", service],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        value = result.stdout.strip()
        if result.returncode == 0 and value:
            return value
    if required:
        names_text = ", ".join(key_names)
        keychain_hint = f" or macOS Keychain service {service!r}" if service else ""
        hint = f"Run scripts/setup_private_env.py, set a private env variable{keychain_hint}."
        loaded_hint = f" Loaded env files: {', '.join(loaded)}." if loaded else " No private env file was loaded."
        raise ScriptError(f"Missing API key. Set one of: {names_text}. {hint}{loaded_hint}")
    return None


def redact(value: Optional[str]) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def normalize_base_url(base_url: str) -> str:
    if not base_url:
        raise ScriptError("Model base_url is empty")
    cleaned = base_url.rstrip("/")
    parsed = urlparse(cleaned)
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    needs_v1 = host in {"yunwu.ai", "api.yunwu.ai", "api.x.ai", "api.119337.xyz"} and not path.endswith("/v1")
    if needs_v1:
        path = f"{path}/v1" if path else "/v1"
        cleaned = urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
    return cleaned.rstrip("/")


def join_url(base_url: str, path: str) -> str:
    base = normalize_base_url(base_url)
    suffix = path if path.startswith("/") else f"/{path}"
    if base.endswith("/v1") and suffix.startswith("/v1/"):
        suffix = suffix[3:]
    return base + suffix


def configured_proxy_url() -> Optional[str]:
    """Return the Skill-specific proxy without changing system or proxy-app settings."""
    load_runtime_env()
    value = str(os.getenv(PROXY_URL_ENV) or "").strip()
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ScriptError(
            f"{PROXY_URL_ENV} must be a complete http:// or https:// proxy URL. "
            "The Skill never edits Clash or system proxy settings."
        )
    return value


def network_route_summary() -> Dict[str, Any]:
    """Describe the effective HTTP route without exposing proxy credentials."""
    explicit = configured_proxy_url()
    source = PROXY_URL_ENV if explicit else "system_or_standard_environment"
    value = explicit
    if not value:
        proxies = urllib.request.getproxies()
        value = str(proxies.get("https") or proxies.get("http") or "").strip()
    if not value:
        return {"mode": "direct", "source": "none"}
    parsed = urlparse(value if "://" in value else f"http://{value}")
    return {
        "mode": "proxy",
        "source": source,
        "scheme": parsed.scheme or "http",
        "host": parsed.hostname or "",
        "port": parsed.port,
        "has_credentials": bool(parsed.username or parsed.password),
    }


def open_url(request: urllib.request.Request, timeout: int):
    """Open a request through the dedicated Skill proxy when configured."""
    proxy_url = configured_proxy_url()
    if proxy_url:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        )
        return opener.open(request, timeout=timeout)
    return urllib.request.urlopen(request, timeout=timeout)


def http_json(method: str, url: str, api_key: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 60, auth_scheme: str = "Bearer") -> Dict[str, Any]:
    body = None
    auth_value = f"{auth_scheme} {api_key}".strip() if auth_scheme else api_key
    headers = {
        "Authorization": auth_value,
        "Accept": "application/json",
        "User-Agent": "ai-commerce-video-skill/1.0",
    }
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
    try:
        with open_url(request, timeout=timeout) as response:
            text = response.read().decode("utf-8")
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                preview = text[:160].replace("\n", " ")
                raise ScriptError(f"Expected JSON from {url}, got: {preview}") from exc
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise ScriptError(f"HTTP {exc.code} from {url}: {text[:500]}") from exc
    except urllib.error.URLError as exc:
        raise ScriptError(f"Network error calling {url}: {exc}") from exc


def download_file(url: str, output_path: Path, timeout: int = 120) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "ai-commerce-video-skill/1.0"})
    try:
        with open_url(request, timeout=timeout) as response, output_path.open("wb") as out:
            shutil.copyfileobj(response, out)
    except urllib.error.URLError as exc:
        raise ScriptError(f"Failed to download {url}: {exc}") from exc


def run_json_command(cmd: List[str], timeout: int = 60) -> Dict[str, Any]:
    try:
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=True)
        return json.loads(proc.stdout)
    except FileNotFoundError as exc:
        raise ScriptError(f"Required command not found: {cmd[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise ScriptError(f"Command failed: {' '.join(cmd)}\n{exc.stderr[:500]}") from exc
    except json.JSONDecodeError as exc:
        raise ScriptError(f"Command did not return JSON: {' '.join(cmd)}") from exc


def ffprobe_media(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ScriptError(f"Media file not found: {path}")
    if path.stat().st_size <= 0:
        raise ScriptError(f"Media file is empty: {path}")
    return run_json_command([
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ])


def media_summary(path: Path) -> Dict[str, Any]:
    data = ffprobe_media(path)
    video = next((stream for stream in data.get("streams", []) if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in data.get("streams", []) if stream.get("codec_type") == "audio"), None)
    fmt = data.get("format") or {}
    try:
        duration = float(fmt.get("duration", 0) or 0)
    except (TypeError, ValueError):
        duration = 0.0
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "duration_seconds": round(duration, 3),
        "has_video": video is not None,
        "has_audio": audio is not None,
        "video": {
            "codec": video.get("codec_name"),
            "width": video.get("width"),
            "height": video.get("height"),
            "fps": video.get("r_frame_rate"),
            "pixel_format": video.get("pix_fmt"),
        } if video else None,
        "audio": {
            "codec": audio.get("codec_name"),
            "sample_rate": audio.get("sample_rate"),
            "channels": audio.get("channels"),
        } if audio else None,
    }


def verify_media_file(path: Path, require_audio: bool = False) -> Dict[str, Any]:
    summary = media_summary(path)
    if not summary["has_video"]:
        raise ScriptError(f"Downloaded file has no video stream: {path}")
    if require_audio and not summary["has_audio"]:
        raise ScriptError(f"Downloaded file has no audio stream: {path}")
    if summary["duration_seconds"] <= 0:
        raise ScriptError(f"Media duration is zero or unavailable: {path}")
    return summary


def file_to_data_uri(path: Path) -> str:
    if not path.exists():
        raise ScriptError(f"Image file not found: {path}")
    mime, _ = mimetypes.guess_type(str(path))
    if not mime:
        mime = "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://") or value.startswith("data:")


def sanitize_name(name: str) -> str:
    allowed = []
    for ch in name.strip().lower().replace(" ", "-"):
        if ch.isalnum() or ch in ("-", "_"):
            allowed.append(ch)
    cleaned = "".join(allowed).strip("-_")
    return cleaned or f"commerce-video-{int(time.time())}"


def require_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise ScriptError("ffmpeg not found. Install ffmpeg or run stitch_clips.py --dry-run.")
    return path
