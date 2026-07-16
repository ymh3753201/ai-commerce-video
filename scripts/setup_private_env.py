#!/usr/bin/env python3
"""Create the private runtime env file for ai-commerce-video."""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path


DEFAULT_ENV_FILE = Path.home() / ".codex" / "ai-commerce-video.env"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Private env file path")
    parser.add_argument("--base-url", default="https://api.119337.xyz/v1", help="Video API base URL")
    parser.add_argument("--model", default="grok-video-1.5", help="Video model ID")
    parser.add_argument("--key", help="API key. Omit this for hidden interactive input.")
    parser.add_argument("--fal-key", help="Optional fal API key for the seedance2 route.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing env file")
    args = parser.parse_args()

    env_file = Path(args.env_file).expanduser().resolve()
    if env_file.exists() and not args.force:
        print(f"ERROR: env file already exists: {env_file}")
        print("Re-run with --force if you want to replace it.")
        return 1

    api_key = args.key or getpass.getpass("Video API key: ").strip()
    if not api_key:
        print("ERROR: API key is empty")
        return 1

    env_file.parent.mkdir(parents=True, exist_ok=True)
    content = (
        f"AI_COMMERCE_VIDEO_API_KEY={api_key}\n"
        f"AI_COMMERCE_VIDEO_BASE_URL={args.base_url.rstrip('/')}\n"
        f"AI_COMMERCE_VIDEO_MODEL={args.model}\n"
    )
    if args.fal_key:
        content += f"FAL_KEY={args.fal_key}\n"
    old_umask = os.umask(0o077)
    try:
        env_file.write_text(content, encoding="utf-8")
        env_file.chmod(0o600)
    finally:
        os.umask(old_umask)

    print(f"Private video API env file written: {env_file}")
    print("Key saved locally only. Do not commit or package this file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
