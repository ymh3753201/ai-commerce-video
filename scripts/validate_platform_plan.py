#!/usr/bin/env python3
"""Validate platform, scenario, compliance, model, and asset contracts in a generation plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _common import ScriptError, asset_value, get_model_config, load_config, load_json
from subtitle_policy import enabled_subtitle_contract_errors


def add_check(checks: list[dict], text: str, passed: bool, evidence: str, severity: str = "error") -> None:
    checks.append({
        "text": text,
        "passed": bool(passed),
        "evidence": evidence,
        "severity": severity,
    })


def normalized(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_")


def model_contract_from_config(plan: dict, config_path: str | None, model_key: str | None) -> dict:
    try:
        config = load_config(config_path)
        model = get_model_config(config, model_key or plan.get("model_key"))
    except Exception:
        return plan.get("model_capability_contract") or {}
    payload_defaults = model.get("payload_defaults") if isinstance(model.get("payload_defaults"), dict) else {}
    supports_audio = model.get("supports_audio")
    if supports_audio is None:
        supports_audio = bool(payload_defaults.get("generate_audio")) or model.get("provider") in {"119337", "fal_queue"}
    return {
        "model_key": model.get("key"),
        "model": model.get("model"),
        "provider": model.get("provider"),
        "input_mode": model.get("input_mode") or model.get("mode"),
        "supports_multiple_references": bool(model.get("supports_multiple_references")),
        "max_reference_images": int(model.get("max_reference_images") or 0),
        "supports_audio": bool(supports_audio),
        "supports_lip_sync": bool(model.get("supports_lip_sync", True)),
        "supports_multi_segment_generation": bool(model.get("supports_multi_segment_generation", True)),
        "min_duration_seconds": int(model.get("min_duration_seconds") or 0),
        "max_duration_seconds": int(model.get("max_duration_seconds") or 0),
        "max_prompt_chars": model.get("max_prompt_chars"),
        "prompt_budget_chars": model.get("prompt_budget_chars"),
        "allowed_duration_seconds": [int(value) for value in (model.get("allowed_duration_seconds") or [])],
        "allowed_multi_reference_duration_seconds": [
            int(value) for value in (model.get("allowed_multi_reference_duration_seconds") or [])
        ],
    }


def validate_platform_rules(plan: dict, checks: list[dict]) -> None:
    platform = plan.get("platform_contract") or {}
    creative = plan.get("creative_contract") or {}
    compliance = plan.get("compliance_contract") or {}
    profile_key = normalized(platform.get("profile_key"))
    display = platform.get("display_name") or profile_key or "unknown"
    aspect_ratio = plan.get("aspect_ratio") or platform.get("actual_aspect_ratio")
    duration = int(plan.get("total_duration_seconds") or platform.get("actual_duration_seconds") or 0)
    speaker_mode = creative.get("speaker_mode")

    if profile_key in {"amazon_sponsored_brands_video"}:
        add_check(checks, "Amazon Sponsored Brands Video uses supported 16:9 or 9:16 aspect ratio", aspect_ratio in {"16:9", "9:16"}, f"{display}: aspect_ratio={aspect_ratio}")
        add_check(checks, "Amazon Sponsored Brands Video duration is within 6-45 seconds", 6 <= duration <= 45, f"{display}: duration={duration}s")
        add_check(checks, "Amazon Sponsored Brands Video can be understood muted", platform.get("audio_policy") in {"muted_first", "audio_supported_but_do_not_depend_on_it"}, f"audio_policy={platform.get('audio_policy')}")

    if profile_key in {"amazon_sponsored_products_video"}:
        add_check(checks, "Amazon Sponsored Products Video uses 16:9", aspect_ratio == "16:9", f"{display}: aspect_ratio={aspect_ratio}")
        add_check(checks, "Amazon Sponsored Products Video is at least 7 seconds", duration >= 7, f"{display}: duration={duration}s")
        add_check(checks, "Amazon Sponsored Products Video does not use talking-head spoken selling", speaker_mode != "digital-human-spoken", f"speaker_mode={speaker_mode}")
        add_check(checks, "Amazon Sponsored Products Video does not depend on audio", platform.get("audio_policy") == "no_audio", f"audio_policy={platform.get('audio_policy')}")

    if profile_key in {"tiktok", "tiktok_shop", "tiktok_in_feed", "douyin", "douyin_shop", "douyin_in_feed"}:
        add_check(checks, "TikTok/Douyin plan uses vertical 9:16", aspect_ratio == "9:16", f"{display}: aspect_ratio={aspect_ratio}")
        add_check(checks, "TikTok/Douyin plan has a safe-zone profile", bool(platform.get("safe_zone_profile")), f"safe_zone_profile={platform.get('safe_zone_profile')}")
        add_check(
            checks,
            "TikTok/Douyin plan requires subtitles",
            bool(platform.get("subtitle_required")),
            f"subtitle_required={platform.get('subtitle_required')}; provider_subtitles_are_forbidden",
        )
        structure = str(platform.get("recommended_structure") or "").lower()
        add_check(checks, "TikTok/Douyin plan includes a strong hook structure", "hook" in structure, f"recommended_structure={platform.get('recommended_structure')}")
        add_check(checks, "TikTok/Douyin plan has a CTA type", bool(platform.get("cta_type")), f"cta_type={platform.get('cta_type')}")

    if profile_key == "xiaohongshu":
        risks = " ".join(platform.get("common_risks") or [])
        add_check(checks, "Xiaohongshu plan includes authenticity risk control", "fake" in risks or "experience" in risks or "真实" in risks, f"common_risks={platform.get('common_risks')}")
        add_check(checks, "Xiaohongshu plan has compliance contract", bool(compliance), f"claim_risk={compliance.get('claim_risk')}")

    if profile_key in {"youtube", "youtube_shorts"}:
        structure = str(platform.get("recommended_structure") or "")
        abcd_ok = all(word in structure for word in ["Attention", "Branding", "Connection", "Direction"])
        add_check(checks, "YouTube plan follows ABCD structure", abcd_ok, f"recommended_structure={structure}")
        add_check(checks, "YouTube plan has universal safe-zone profile", bool(platform.get("safe_zone_profile")), f"safe_zone_profile={platform.get('safe_zone_profile')}")


def validate_model_and_assets(plan: dict, checks: list[dict], model_contract: dict) -> None:
    creative = plan.get("creative_contract") or {}
    platform = plan.get("platform_contract") or {}
    asset_contract = plan.get("reference_asset_contract") or plan.get("asset_contract") or {}
    references = plan.get("references") or []
    shots = plan.get("shots") or []
    video_refs = asset_contract.get("video_reference_assets") or []
    segment_sources = asset_contract.get("segment_source_assets") or []
    locked_source = asset_value(asset_contract.get("video_source_asset"))
    segment_values = {asset_value(asset) for asset in segment_sources}
    supports_refs = bool(model_contract.get("supports_multiple_references"))
    max_refs = int(model_contract.get("max_reference_images") or 0)

    add_check(checks, "Model capability contract exists", bool(model_contract), f"model={model_contract.get('model')}")
    if supports_refs:
        add_check(checks, "Multi-reference upload count fits model limit", len(video_refs) <= max_refs, f"reference_count={len(video_refs)}, max_reference_images={max_refs}")
        confirmed_values = {asset_value(ref) for ref in references if asset_value(ref)}
        included_values = {asset_value(ref) for ref in video_refs if asset_value(ref)}
        missing = sorted(confirmed_values - included_values)
        add_check(checks, "Confirmed reference images are included in multi-reference payload plan", not missing, f"missing={missing}")
    else:
        add_check(checks, "Single-image model has no separate video reference payload", not video_refs, f"reference_count={len(video_refs)}")

    strategy = creative.get("reference_strategy") or ""
    if strategy in {"storyboard_sheet_reference", "multi_reference_storyboard"}:
        add_check(checks, "Storyboard reference strategy uses a multi-reference model", supports_refs, f"strategy={strategy}, supports_multiple_references={supports_refs}")
    if strategy == "per_segment_source_frames":
        add_check(checks, "Per-segment strategy has approved segment source frames", bool(segment_values), f"segment_source_count={len(segment_values)}")

    for shot in shots:
        source = asset_value(shot.get("image"))
        if segment_values:
            ok = source in segment_values
            evidence = f"{shot.get('id')}: source={source}; segment_sources={sorted(segment_values)}"
        else:
            ok = bool(locked_source) and source == locked_source
            evidence = f"{shot.get('id')}: source={source}; locked_source={locked_source}"
        add_check(checks, f"{shot.get('id')} uses the locked confirmed source image", ok, evidence)

    audio_policy = platform.get("audio_policy")
    if audio_policy == "no_audio":
        add_check(checks, "No-audio placement avoids spoken selling", creative.get("speaker_mode") != "digital-human-spoken", f"speaker_mode={creative.get('speaker_mode')}")
    if creative.get("speaker_mode") == "digital-human-spoken":
        add_check(checks, "Selected model reports lip-sync support for spoken presenter plan", bool(model_contract.get("supports_lip_sync")), f"supports_lip_sync={model_contract.get('supports_lip_sync')}")
    if len(shots) > 1:
        add_check(checks, "Selected model route supports multi-segment generation workflow", bool(model_contract.get("supports_multi_segment_generation", True)), f"shot_count={len(shots)}")


def validate_production_core(plan: dict, checks: list[dict], model_contract: dict) -> None:
    shots = plan.get("shots") or []
    duration_plan = plan.get("duration_plan") or {}
    production = plan.get("production_contract") or {}
    subtitle_plan = plan.get("subtitle_plan") or {}
    has_multi_refs = any(shot.get("video_references") for shot in shots)
    allowed = (
        model_contract.get("allowed_multi_reference_duration_seconds")
        if has_multi_refs and model_contract.get("allowed_multi_reference_duration_seconds")
        else model_contract.get("allowed_duration_seconds")
    ) or []
    allowed = [int(value) for value in allowed]

    shot_durations = [int(shot.get("duration_seconds") or 0) for shot in shots]
    if allowed:
        for shot, seconds in zip(shots, shot_durations):
            add_check(
                checks,
                f"{shot.get('id')} uses a legal request duration",
                seconds in allowed,
                f"duration_seconds={seconds}; legal request duration slots={allowed}",
            )
    else:
        minimum = int(model_contract.get("min_duration_seconds") or 0)
        maximum = int(model_contract.get("max_duration_seconds") or 0)
        for shot, seconds in zip(shots, shot_durations):
            add_check(
                checks,
                f"{shot.get('id')} uses a legal request duration",
                minimum <= seconds <= maximum,
                f"duration_seconds={seconds}; legal request duration range={minimum}-{maximum}",
            )

    planned_durations = [int(value) for value in (duration_plan.get("request_durations_seconds") or [])]
    add_check(
        checks,
        "Duration plan matches the paid shot requests",
        bool(shots) and planned_durations == shot_durations,
        f"duration_plan={planned_durations}; shots={shot_durations}",
    )

    for index, shot in enumerate(shots):
        prompt = str(shot.get("prompt") or "")
        prompt_contract = shot.get("prompt_contract") or {}
        max_prompt_chars = model_contract.get("max_prompt_chars")
        prompt_budget_chars = model_contract.get("prompt_budget_chars")
        if max_prompt_chars is not None:
            maximum = int(max_prompt_chars)
            add_check(
                checks,
                f"{shot.get('id')} Provider prompt fits the hard model limit",
                len(prompt) <= maximum,
                f"{shot.get('id')} prompt length {len(prompt)}; max_prompt_chars={maximum}",
            )
        if prompt_budget_chars is not None:
            budget = int(prompt_budget_chars)
            add_check(
                checks,
                f"{shot.get('id')} Provider prompt fits the safe budget",
                len(prompt) <= budget,
                f"{shot.get('id')} prompt length {len(prompt)}; prompt_budget_chars={budget}",
            )
        if prompt_contract:
            add_check(
                checks,
                f"{shot.get('id')} prompt contract matches the exact Provider prompt",
                int(prompt_contract.get("char_count") or -1) == len(prompt)
                and prompt_contract.get("truncated") is False,
                (
                    f"prompt_contract.char_count={prompt_contract.get('char_count')}; "
                    f"actual={len(prompt)}; truncated={prompt_contract.get('truncated')}"
                ),
            )
        script = str(shot.get("spoken_script") or "").strip()
        boundary = shot.get("script_boundary") or {}
        if script:
            add_check(
                checks,
                f"{shot.get('id')} spoken script has a stitch-safe complete boundary",
                boundary.get("stitch_safe") is True,
                f"script_boundary.stitch_safe={boundary.get('stitch_safe')}; is_final={index == len(shots) - 1}",
            )

    expected_count = len(shots)
    add_check(
        checks,
        "Paid submission cap equals the minimum planned request count",
        int(production.get("base_request_count") or -1) == expected_count
        and int(production.get("approved_paid_cap") or -1) == expected_count,
        (
            f"base_request_count={production.get('base_request_count')}; "
            f"approved_paid_cap={production.get('approved_paid_cap')}; shot_count={expected_count}"
        ),
    )
    add_check(
        checks,
        "No automatic paid repair reserve is allowed",
        int(production.get("repair_reserve") or 0) == 0
        and int(production.get("per_shot_repair_limit") or 0) == 0,
        (
            f"repair_reserve={production.get('repair_reserve')}; "
            f"per_shot_repair_limit={production.get('per_shot_repair_limit')}"
        ),
    )

    provider_subtitles_absent = subtitle_plan.get("subtitle_included_in_payload") is False
    add_check(
        checks,
        "Provider payload must keep subtitle_included_in_payload false",
        provider_subtitles_absent,
        f"subtitle_included_in_payload={subtitle_plan.get('subtitle_included_in_payload')!r}",
    )
    subtitle_errors = enabled_subtitle_contract_errors(subtitle_plan)
    add_check(
        checks,
        "Enabled subtitles use confirmed local postproduction only",
        not subtitle_errors,
        "subtitle contract valid" if not subtitle_errors else "; ".join(subtitle_errors),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, help="Path to generation-plan.json")
    parser.add_argument("--config", help="Path to model config JSON")
    parser.add_argument("--model-key", help="Override model key for validation")
    args = parser.parse_args()

    try:
        plan_path = Path(args.plan).expanduser().resolve()
        plan = load_json(plan_path)
        checks: list[dict] = []
        validate_platform_rules(plan, checks)
        model_contract = model_contract_from_config(plan, args.config, args.model_key)
        validate_model_and_assets(plan, checks, model_contract)
        validate_production_core(plan, checks, model_contract)
        errors = [check for check in checks if check["severity"] == "error" and not check["passed"]]
        warnings = [check for check in checks if check["severity"] == "warning" and not check["passed"]]
        report = {
            "ok": not errors,
            "plan": str(plan_path),
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "passed": sum(1 for check in checks if check["passed"]),
                "failed": sum(1 for check in checks if not check["passed"]),
                "error_count": len(errors),
                "warning_count": len(warnings),
            },
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if not errors else 1
    except (ScriptError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
