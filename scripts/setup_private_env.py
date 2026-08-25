#!/usr/bin/env python3
"""Create the private runtime env file for ai-commerce-video."""

from __future__ import annotations

import argparse
import getpass
import os
import shutil
import subprocess
from pathlib import Path


DEFAULT_ENV_FILE = Path.home() / ".codex" / "ai-commerce-video.env"
ROUTES = {
    "miku-reference": {
        "base_url": "https://mikuapi.org",
        "model_key": "GROK_VIDEO_15_REFERENCE",
        "key_env": "AI_COMMERCE_VIDEO_MIKUAPI_KEY",
        "keychain_service": "ai-commerce-video-mikuapi-video",
    },
    "xai-reference": {
        "base_url": "https://api.x.ai",
        "model_key": "GROK_VIDEO_15_REFERENCE_XAI",
        "key_env": "XAI_API_KEY",
        "keychain_service": "ai-commerce-video-xai-video",
    },
    "miku-image": {
        "base_url": "https://mikuapi.org",
        "model_key": "GROK_VIDEO_15",
        "key_env": "AI_COMMERCE_VIDEO_MIKUAPI_KEY",
        "keychain_service": "ai-commerce-video-mikuapi-video",
    },
    "119337-image": {
        "base_url": "https://api.119337.xyz/v1",
        "model_key": "GROK_IMAGE_VIDEO",
        "key_env": "AI_COMMERCE_VIDEO_119337_KEY",
        "keychain_service": "ai-commerce-video-119337-video",
    },
}


def atomic_write_private_env(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = None
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = None
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Private env file path")
    parser.add_argument(
        "--route",
        choices=tuple(ROUTES),
        default="miku-reference",
        help="Configure the default MikuAPI route or one explicitly selected optional Provider route",
    )
    parser.add_argument("--base-url", help="Video API base URL; defaults to the selected route")
    parser.add_argument("--model", default="grok-imagine-video-1.5", help="Video model ID")
    parser.add_argument("--key", help="API key. Omit this for hidden interactive input.")
    parser.add_argument(
        "--storage",
        choices=("keychain", "env-file"),
        default="keychain" if shutil.which("security") else "env-file",
        help="Store the selected route key in macOS Keychain when available, otherwise in the 0600 env file.",
    )
    parser.add_argument("--fal-key", help="Optional fal API key for the seedance2 route.")
    parser.add_argument(
        "--proxy-url",
        help="Optional Skill-only HTTP proxy URL, for example http://127.0.0.1:7897. Does not modify Clash or system settings.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite an existing env file")
    args = parser.parse_args()
    route = ROUTES[args.route]
    base_url = (args.base_url or route["base_url"]).rstrip("/")
    model_key = route["model_key"]
    key_env = route["key_env"]
    keychain_service = route["keychain_service"]

    env_file = Path(args.env_file).expanduser().resolve()
    if env_file.exists() and not args.force:
        print(f"ERROR: env file already exists: {env_file}")
        print("Re-run with --force if you want to replace it.")
        return 1

    api_key = args.key or getpass.getpass("Video API key: ").strip()
    if not api_key:
        print("ERROR: API key is empty")
        return 1

    content = (
        f"AI_COMMERCE_VIDEO_BASE_URL_{model_key}={base_url}\n"
        f"AI_COMMERCE_VIDEO_MODEL_{model_key}={args.model}\n"
    )
    if args.storage == "env-file":
        content = f"{key_env}={api_key}\n" + content
    if args.fal_key:
        content += f"FAL_KEY={args.fal_key}\n"
    if args.proxy_url:
        from urllib.parse import urlparse

        parsed = urlparse(args.proxy_url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            print("ERROR: --proxy-url must be a complete http:// or https:// proxy URL")
            return 1
        content += f"AI_COMMERCE_VIDEO_PROXY_URL={args.proxy_url}\n"
    if args.storage == "keychain":
        security = shutil.which("security")
        if not security:
            print("ERROR: macOS security command is unavailable; use --storage env-file")
            return 1
        result = subprocess.run(
            [security, "add-generic-password", "-U", "-a", getpass.getuser(), "-s", keychain_service, "-w", api_key],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print(f"ERROR: failed to save Keychain item: {result.stderr.strip()}")
            return 1
    atomic_write_private_env(env_file, content)

    print(f"Private video API env file written: {env_file}")
    if args.storage == "keychain":
        print(f"Key saved in macOS Keychain service: {keychain_service}")
    else:
        print("Key saved in the private 0600 env file.")
    print("The key is not stored in the Skill, project records, logs, or package.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
