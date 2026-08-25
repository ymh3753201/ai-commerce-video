#!/usr/bin/env python3
"""Check Provider model visibility without creating a paid video task."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from _common import (
    ScriptError,
    find_api_key,
    get_model_config,
    http_json,
    join_url,
    load_config,
    load_json,
    model_api_key_names,
    model_api_key_keychain_service,
    model_auth_scheme,
    network_route_summary,
)
from _workflow import atomic_write_json


def model_ids(response: dict) -> list[str]:
    items = response.get("data") if isinstance(response, dict) else None
    if not isinstance(items, list):
        return []
    result: list[str] = []
    for item in items:
        if isinstance(item, dict):
            value = item.get("id") or item.get("model") or item.get("name")
        else:
            value = item
        if value:
            result.append(str(value))
    return result


def classify_error(message: str) -> str:
    lower = message.lower()
    region_markers = (
        "访问受限",
        "当前地区",
        "country, region, or territory",
        "country or region",
        "region restriction",
        "not available in your country",
    )
    if "http 403" in lower and any(marker.lower() in lower for marker in region_markers):
        return "region_restricted"
    if "http 403" in lower:
        return "access_forbidden"
    if "http 401" in lower:
        return "authentication_failed"
    if "network error" in lower or "name or service not known" in lower or "nodename nor servname" in lower:
        return "network_unavailable"
    return "provider_readiness_failed"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--config", help="Model config path")
    parser.add_argument("--model-key", help="Configured model key; defaults to the project plan")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    output_path = project_dir / "provider-readiness.json"
    report = {
        "schema_version": "1.0",
        "checked_at": int(time.time()),
        "project_dir": str(project_dir),
        "paid_api_call": False,
        "provider_generation_post_attempted": False,
        "network_route": {},
        "status": "blocked",
        "ok": False,
    }
    try:
        plan_path = project_dir / "generation-plan.json"
        plan = load_json(plan_path) if plan_path.exists() else {}
        config = load_config(args.config)
        model = get_model_config(config, args.model_key or plan.get("model_key"))
        report.update({
            "provider": model.get("provider"),
            "model_key": model.get("key"),
            "target_model": model.get("model"),
            "provider_base_url": model.get("base_url"),
            "network_route": network_route_summary(),
        })
        readiness_required = bool(model.get("require_pre_submit_readiness"))
        models_path = str(model.get("models_path") or "").strip()
        if not readiness_required or not models_path:
            report.update({"ok": True, "status": "not_required", "model_visible": None})
            atomic_write_json(output_path, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        api_key = find_api_key(
            required=True,
            names=model_api_key_names(model),
            keychain_service=model_api_key_keychain_service(model),
        )
        response = http_json(
            "GET",
            join_url(model["base_url"], models_path),
            api_key,
            timeout=args.timeout,
            auth_scheme=model_auth_scheme(model),
        )
        visible_models = model_ids(response)
        target = str(model.get("model") or "")
        visible = target in visible_models
        report.update({
            "visible_models": visible_models,
            "model_visible": visible,
            "models_path": models_path,
        })
        if not visible:
            report.update({
                "error_code": "model_not_visible",
                "error": f"Configured model {target!r} is not visible to the current credential.",
            })
            atomic_write_json(output_path, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 1

        audio = plan.get("audio_contract") if isinstance(plan.get("audio_contract"), dict) else {}
        preset_voices = [str(value).strip() for value in audio.get("preset_voice_ids") or [] if str(value).strip()]
        speech_required = bool(audio.get("speech_required"))
        report.update({
            "speech_required": speech_required,
            "speech_readiness_mode": "explicit_preset_optional" if preset_voices else ("prompt_native" if speech_required else "not_applicable"),
            "voice_roster_checked": False,
            "voice_roster_policy": "not_a_paid_submission_gate",
        })
        if preset_voices:
            report["selected_preset_voice_ids"] = preset_voices
        report.update({"ok": True, "status": "pass", "error_code": "", "error": ""})
        atomic_write_json(output_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (ScriptError, OSError, ValueError, json.JSONDecodeError) as exc:
        message = str(exc)
        report.update({"error_code": classify_error(message), "error": message})
        atomic_write_json(output_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
