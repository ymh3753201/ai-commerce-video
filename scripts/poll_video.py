#!/usr/bin/env python3
"""Poll a Grok-compatible video request and download the finished MP4."""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from _common import (
    ScriptError,
    download_file,
    find_api_key,
    get_model_config,
    http_json,
    join_url,
    load_config,
    load_json,
    model_api_key_names,
    model_auth_scheme,
    model_provider,
    verify_media_file,
    write_json,
)


def infer_output_path(request_record: dict, output: str | None) -> Path:
    if output:
        return Path(output).expanduser().resolve()
    request_file = Path(request_record.get("_request_file", "request.json")).resolve()
    shot_id = request_record.get("shot_id", "shot")
    project_dir = request_file.parents[1] if request_file.parent.name == "requests" else request_file.parent
    return project_dir / "clips" / f"{shot_id}.mp4"


def task_body(data: dict) -> dict:
    return data.get("data") if isinstance(data.get("data"), dict) else data


def task_status(data: dict) -> str:
    body = task_body(data)
    return str(body.get("status") or "").upper()


def task_result_url(data: dict) -> str:
    body = task_body(data)
    if body.get("result_url"):
        return str(body["result_url"])
    video = body.get("video") or data.get("video") or {}
    return str(video.get("url") or "")


def task_fail_reason(data: dict) -> str:
    body = task_body(data)
    return str(body.get("fail_reason") or body.get("error") or data.get("message") or data)


def response_value(response: dict, key: str) -> str:
    raw = response.get("raw_response")
    body = task_body(raw) if isinstance(raw, dict) else {}
    return str(response.get(key) or body.get(key) or "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-file", required=True, help="Request JSON written by generate_video.py")
    parser.add_argument("--config", help="Model config path")
    parser.add_argument("--model-key", help="Override model key")
    parser.add_argument("--output", help="Output MP4 path")
    parser.add_argument("--timeout", type=int, default=900, help="Maximum polling time in seconds")
    parser.add_argument("--interval", type=int, default=5, help="Polling interval seconds")
    parser.add_argument("--dry-run", action="store_true", help="Do not call API; validate request file only")
    parser.add_argument("--mock-video", help="Copy this local file as the completed MP4 for offline testing")
    parser.add_argument("--require-audio", action="store_true", help="Fail validation if the downloaded MP4 has no audio stream")
    args = parser.parse_args()

    try:
        request_file = Path(args.request_file).expanduser().resolve()
        request_record = load_json(request_file)
        request_record["_request_file"] = str(request_file)
        response = request_record.get("response") or {}
        request_id = response.get("request_id")
        if not request_id:
            raise ScriptError(f"No request_id in {request_file}")
        output_path = infer_output_path(request_record, args.output)
        result_file = request_file.with_name(request_file.stem.replace("_request", "_poll") + ".json")

        if args.mock_video:
            src = Path(args.mock_video).expanduser().resolve()
            if not src.exists():
                raise ScriptError(f"Mock video not found: {src}")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, output_path)
            media = verify_media_file(output_path, require_audio=args.require_audio)
            result = {"status": "done", "mock": True, "video": {"url": str(src), "local_path": str(output_path)}, "media": media}
            write_json(result_file, result)
            print(json.dumps({"ok": True, "output": str(output_path), "result_file": str(result_file), "mock": True, "media": media}, ensure_ascii=False, indent=2))
            return 0

        if args.dry_run:
            result = {"status": "dry_run", "request_id": request_id, "output_path": str(output_path)}
            write_json(result_file, result)
            print(json.dumps({"ok": True, "dry_run": True, "result_file": str(result_file)}, ensure_ascii=False, indent=2))
            return 0

        config = load_config(args.config)
        model = get_model_config(config, args.model_key or request_record.get("model_key"))
        api_key = find_api_key(required=True, names=model_api_key_names(model))
        poll_path = model.get("poll_path_template", "/video/generations/{request_id}").format(request_id=request_id)
        poll_url = response_value(response, "status_url") or join_url(model["base_url"], poll_path)
        response_url = response_value(response, "response_url")
        if not response_url and model_provider(model) == "fal_queue":
            response_path_template = model.get("result_path_template")
            if not response_path_template:
                raise ScriptError("fal_queue model requires result_path_template to fetch the completed video response.")
            response_url = join_url(model["base_url"], response_path_template.format(request_id=request_id))
        auth_scheme = model_auth_scheme(model)

        deadline = time.time() + args.timeout
        last_data = {}
        while time.time() < deadline:
            data = http_json("GET", poll_url, api_key, timeout=60, auth_scheme=auth_scheme)
            last_data = data
            status = task_status(data)
            if status in {"SUCCESS", "DONE", "COMPLETED"}:
                status_response = data
                result_data = data
                if model_provider(model) == "fal_queue":
                    if not response_url:
                        response_url = response_value(data, "response_url")
                    if not response_url:
                        raise ScriptError(f"Completed fal_queue response missing response_url: {data}")
                    result_data = http_json("GET", response_url, api_key, timeout=60, auth_scheme=auth_scheme)
                url = task_result_url(result_data)
                if not url:
                    raise ScriptError(f"Success response missing result_url/video.url: {result_data}")
                download_file(url, output_path)
                media = verify_media_file(output_path, require_audio=args.require_audio)
                body = task_body(result_data)
                if body is not result_data:
                    result_data.setdefault("data", body)
                    if isinstance(result_data.get("data"), dict):
                        result_data["data"]["local_path"] = str(output_path)
                else:
                    result_data["local_path"] = str(output_path)
                result_data["video"] = {"url": url, "local_path": str(output_path)}
                result_data["media"] = media
                if status_response is not result_data:
                    result_data["poll_status_response"] = status_response
                write_json(result_file, result_data)
                print(json.dumps({"ok": True, "output": str(output_path), "result_file": str(result_file), "media": media}, ensure_ascii=False, indent=2))
                return 0
            if status in {"FAILURE", "FAILED", "EXPIRED", "CANCELED", "CANCELLED"}:
                write_json(result_file, data)
                raise ScriptError(f"Generation {status}: {task_fail_reason(data)}")
            time.sleep(args.interval)
        write_json(result_file, last_data or {"status": "timeout", "request_id": request_id})
        raise ScriptError(f"Polling timed out after {args.timeout}s for request {request_id}")
    except ScriptError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
