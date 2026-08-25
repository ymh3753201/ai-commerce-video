#!/usr/bin/env python3
"""Poll a Grok-compatible video request and download the finished MP4."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import time
from pathlib import Path
from urllib.parse import urlsplit

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
    model_api_key_keychain_service,
    model_auth_scheme,
    model_provider,
    verify_media_file,
    sha256_file,
    write_json,
)


def auth_origin(value: str) -> tuple[str, str, int | None]:
    parsed = urlsplit(str(value or ""))
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ScriptError(f"Provider auth URL must be an absolute HTTP(S) URL: {value!r}")
    return parsed.scheme.lower(), parsed.hostname.lower(), parsed.port


def require_authorized_provider_url(candidate: str, frozen_submit_url: str, label: str) -> str:
    if not frozen_submit_url:
        raise ScriptError("Request evidence is missing the frozen submit_url; refusing credentialed polling")
    if auth_origin(candidate) != auth_origin(frozen_submit_url):
        raise ScriptError(
            f"Refusing to send Provider credentials to a different host for {label}: {candidate}"
        )
    return candidate


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
    for key in ("result_url", "video_url", "download_url"):
        if body.get(key):
            return str(body[key])
    video = body.get("video") or data.get("video") or {}
    return str(video.get("url") or "")


def task_fail_reason(data: dict) -> str:
    body = task_body(data)
    return str(body.get("fail_reason") or body.get("error") or data.get("message") or data)


def response_value(response: dict, key: str) -> str:
    raw = response.get("raw_response")
    body = task_body(raw) if isinstance(raw, dict) else {}
    return str(response.get(key) or body.get(key) or "")


def recursive_key_values(value, wanted: set[str]) -> list:
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in wanted:
                found.append(item)
            found.extend(recursive_key_values(item, wanted))
    elif isinstance(value, list):
        for item in value:
            found.extend(recursive_key_values(item, wanted))
    return found


def first_scalar(values: list, default=""):
    for value in values:
        if isinstance(value, (str, int, float)) and str(value).strip():
            return value
    return default


def legacy_payload_image_hashes(value) -> set[str]:
    """Recover image-byte evidence from old request records that predate request_evidence."""
    hashes: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            hashes.update(legacy_payload_image_hashes(item))
    elif isinstance(value, list):
        for item in value:
            hashes.update(legacy_payload_image_hashes(item))
    elif isinstance(value, str) and value.startswith("data:image/") and ";base64," in value:
        try:
            raw = base64.b64decode(value.split(",", 1)[1], validate=True)
        except (ValueError, base64.binascii.Error):
            return hashes
        hashes.add(hashlib.sha256(raw).hexdigest())
    return hashes


def build_provider_trace(request_record: dict, provider_response: dict, result_url: str = "") -> dict:
    evidence = request_record.get("request_evidence") or {}
    gateway_task_id = str((request_record.get("response") or {}).get("request_id") or "")
    body = task_body(provider_response)
    gateway_record_id = body.get("id") if isinstance(body, dict) and isinstance(body.get("id"), (int, float)) else ""
    nested_body = body.get("data") if isinstance(body, dict) and isinstance(body.get("data"), dict) else {}
    upstream_candidates = []
    if isinstance(body, dict):
        upstream_candidates.extend([body.get("upstream_task_id"), nested_body.get("upstream_task_id")])
        upstream_candidates.extend([nested_body.get("task_id"), nested_body.get("request_id"), nested_body.get("id")])
        if isinstance(body.get("id"), str):
            upstream_candidates.append(body.get("id"))
    task_ids = [
        str(value)
        for value in recursive_key_values(provider_response, {"id", "task_id", "request_id", "upstream_task_id"})
        if isinstance(value, (str, int)) and str(value)
    ]
    upstream_task_id = next(
        (str(value) for value in upstream_candidates if isinstance(value, str) and value and value != gateway_task_id),
        "",
    )
    if not upstream_task_id:
        upstream_task_id = next(
            (value for value in task_ids if value != gateway_task_id and (value.startswith("task_") or value.startswith("request_"))),
            "",
        )
    returned_prompt = str(first_scalar(recursive_key_values(provider_response, {"prompt"}), ""))
    returned_prompt_sha256 = hashlib.sha256(returned_prompt.encode("utf-8")).hexdigest() if returned_prompt else ""
    expected_prompt_sha256 = str(evidence.get("prompt_sha256") or "")
    if not expected_prompt_sha256:
        legacy_prompt = str((request_record.get("payload") or {}).get("prompt") or "")
        if legacy_prompt:
            expected_prompt_sha256 = hashlib.sha256(legacy_prompt.encode("utf-8")).hexdigest()
    prompt_match = None if not returned_prompt or not expected_prompt_sha256 else returned_prompt_sha256 == expected_prompt_sha256
    receipt_hashes = {
        str(value).lower()
        for value in recursive_key_values(
            provider_response,
            {"image_sha256", "input_image_sha256", "source_image_sha256", "reference_image_sha256"},
        )
        if isinstance(value, str) and len(value) == 64
    }
    sent_hashes = {
        str(item.get("sha256") or "").lower()
        for item in (evidence.get("source_images") or [])
        if item.get("sha256")
    }
    if not sent_hashes:
        sent_hashes = legacy_payload_image_hashes(request_record.get("payload") or {})
    receipt_verified = bool(sent_hashes and receipt_hashes.intersection(sent_hashes))
    channel_id = first_scalar(recursive_key_values(provider_response, {"channel_id"}), "")
    return {
        "schema_version": "1.0",
        "gateway_task_id": gateway_task_id,
        "gateway_record_id": gateway_record_id,
        "upstream_task_id": upstream_task_id,
        "task_ids_observed": list(dict.fromkeys(task_ids)),
        "channel_id": channel_id,
        "expected_prompt_sha256": expected_prompt_sha256,
        "returned_prompt_sha256": returned_prompt_sha256,
        "returned_prompt_matches_request": prompt_match,
        "sent_image_sha256": sorted(sent_hashes),
        "provider_reported_image_sha256": sorted(receipt_hashes),
        "provider_input_receipt_status": "verified" if receipt_verified else "unverified_provider_input",
        "result_url_sha256": hashlib.sha256(result_url.encode("utf-8")).hexdigest() if result_url else "",
    }


def build_duration_contract(request_record: dict, media: dict) -> dict:
    payload = request_record.get("payload") or {}
    requested = float(payload.get("duration") or payload.get("seconds") or 0)
    actual = float(media.get("duration_seconds") or 0)
    quality = request_record.get("quality_contract") or {}
    limit = float(quality.get("max_provider_duration_shortfall_seconds", 1.0))
    shortfall = max(0.0, requested - actual)
    return {
        "requested_seconds": requested,
        "actual_seconds": actual,
        "shortfall_seconds": round(shortfall, 3),
        "allowed_shortfall_seconds": limit,
        "pass": requested <= 0 or shortfall <= limit,
    }


def print_duration_block_and_fail(output_path: Path, result_file: Path, media: dict, duration_contract: dict) -> int:
    print(json.dumps({
        "ok": False,
        "error_code": "QC_DURATION_SHORTFALL",
        "error": (
            f"Provider returned {duration_contract['actual_seconds']:.3f}s for a "
            f"{duration_contract['requested_seconds']:.3f}s request; delivery is blocked without automatic retry"
        ),
        "output": str(output_path),
        "result_file": str(result_file),
        "media": media,
        "duration_contract": duration_contract,
        "paid_retry_attempted": False,
    }, ensure_ascii=False, indent=2))
    return 1


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
            duration_contract = build_duration_contract(request_record, media)
            result = {"status": "done", "mock": True, "video": {"url": str(src), "local_path": str(output_path)}, "media": media, "duration_contract": duration_contract}
            write_json(result_file, result)
            if not duration_contract["pass"]:
                return print_duration_block_and_fail(output_path, result_file, media, duration_contract)
            print(json.dumps({"ok": True, "output": str(output_path), "result_file": str(result_file), "mock": True, "media": media}, ensure_ascii=False, indent=2))
            return 0

        if args.dry_run:
            result = {"status": "dry_run", "request_id": request_id, "output_path": str(output_path)}
            write_json(result_file, result)
            print(json.dumps({"ok": True, "dry_run": True, "result_file": str(result_file)}, ensure_ascii=False, indent=2))
            return 0

        config = load_config(args.config)
        model = get_model_config(config, args.model_key or request_record.get("model_key"))
        frozen_submit_url = str(request_record.get("submit_url") or "")
        require_authorized_provider_url(str(model.get("base_url") or ""), frozen_submit_url, "configured base URL")
        poll_path = model.get("poll_path_template", "/v1/videos/{request_id}").format(request_id=request_id)
        poll_url = response_value(response, "status_url") or join_url(model["base_url"], poll_path)
        require_authorized_provider_url(poll_url, frozen_submit_url, "poll URL")
        response_url = response_value(response, "response_url")
        if not response_url and model_provider(model) == "fal_queue":
            response_path_template = model.get("result_path_template")
            if not response_path_template:
                raise ScriptError("fal_queue model requires result_path_template to fetch the completed video response.")
            response_url = join_url(model["base_url"], response_path_template.format(request_id=request_id))
        if response_url:
            require_authorized_provider_url(response_url, frozen_submit_url, "response URL")
        api_key = find_api_key(
            required=True,
            names=model_api_key_names(model),
            keychain_service=model_api_key_keychain_service(model),
        )
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
                    require_authorized_provider_url(response_url, frozen_submit_url, "response URL")
                    result_data = http_json("GET", response_url, api_key, timeout=60, auth_scheme=auth_scheme)
                url = task_result_url(result_data)
                if not url:
                    raise ScriptError(f"Success response missing result_url/video.url: {result_data}")
                trace = build_provider_trace(request_record, result_data, url)
                if trace.get("returned_prompt_matches_request") is False:
                    blocked = {
                        "status": "blocked",
                        "error": "Provider returned a prompt that does not match the submitted request",
                        "provider_trace": trace,
                        "provider_response": result_data,
                    }
                    write_json(result_file, blocked)
                    raise ScriptError(blocked["error"])
                download_file(url, output_path)
                media = verify_media_file(output_path, require_audio=args.require_audio)
                duration_contract = build_duration_contract(request_record, media)
                trace["downloaded_video_sha256"] = sha256_file(output_path)
                body = task_body(result_data)
                if body is not result_data:
                    result_data.setdefault("data", body)
                    if isinstance(result_data.get("data"), dict):
                        result_data["data"]["local_path"] = str(output_path)
                else:
                    result_data["local_path"] = str(output_path)
                result_data["video"] = {"url": url, "local_path": str(output_path)}
                result_data["media"] = media
                result_data["duration_contract"] = duration_contract
                result_data["provider_trace"] = trace
                if status_response is not result_data:
                    result_data["poll_status_response"] = status_response
                write_json(result_file, result_data)
                if not duration_contract["pass"]:
                    return print_duration_block_and_fail(output_path, result_file, media, duration_contract)
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
