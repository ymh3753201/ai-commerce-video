#!/usr/bin/env python3
"""Validate ai-commerce-video model config and environment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _common import ScriptError, find_api_key, get_model_config, load_config, load_runtime_env, model_api_key_names, redact


def validate_model(model: dict) -> list[str]:
    issues: list[str] = []
    required = ["provider", "base_url", "generation_path", "model", "min_duration_seconds", "max_duration_seconds", "default_duration_seconds"]
    for field in required:
        if model.get(field) in (None, ""):
            if model.get("enabled") is False and field in {"base_url", "generation_path"}:
                continue
            issues.append(f"missing {field}")
    min_duration = int(model.get("min_duration_seconds", 1))
    max_duration = int(model.get("max_duration_seconds", 15))
    default_duration = int(model.get("default_duration_seconds", 15))
    if min_duration <= 0:
        issues.append("min_duration_seconds must be positive")
    if max_duration < min_duration:
        issues.append("max_duration_seconds must be >= min_duration_seconds")
    if not (min_duration <= default_duration <= max_duration):
        issues.append("default_duration_seconds must be within model duration limits")
    allowed_raw = model.get("allowed_duration_seconds")
    if allowed_raw is not None:
        if not isinstance(allowed_raw, list) or not allowed_raw:
            issues.append("allowed_duration_seconds must be a non-empty list when provided")
        else:
            allowed = [int(value) for value in allowed_raw]
            if len(set(allowed)) != len(allowed):
                issues.append("allowed_duration_seconds must not contain duplicates")
            if any(value < min_duration or value > max_duration for value in allowed):
                issues.append("allowed_duration_seconds values must stay within model duration limits")
            if default_duration not in allowed:
                issues.append("default_duration_seconds must be included in allowed_duration_seconds")
    multi_allowed_raw = model.get("allowed_multi_reference_duration_seconds")
    if multi_allowed_raw is not None:
        if not isinstance(multi_allowed_raw, list) or not multi_allowed_raw:
            issues.append("allowed_multi_reference_duration_seconds must be a non-empty list when provided")
        else:
            multi_allowed = [int(value) for value in multi_allowed_raw]
            if len(set(multi_allowed)) != len(multi_allowed):
                issues.append("allowed_multi_reference_duration_seconds must not contain duplicates")
            if allowed_raw is not None and any(value not in set(int(item) for item in allowed_raw) for value in multi_allowed):
                issues.append("allowed_multi_reference_duration_seconds must be a subset of allowed_duration_seconds")
            multi_max = int(model.get("max_duration_multi_reference_seconds") or max_duration)
            if any(value < min_duration or value > multi_max for value in multi_allowed):
                issues.append("allowed_multi_reference_duration_seconds values must stay within multi-reference limits")
    if model.get("supports_multiple_references"):
        if not model.get("reference_field"):
            issues.append("supports_multiple_references requires reference_field")
        if not model.get("reference_payload_format"):
            issues.append("supports_multiple_references requires reference_payload_format")
        if int(model.get("max_reference_images") or 0) <= 0:
            issues.append("supports_multiple_references requires positive max_reference_images")
        if model.get("input_mode") == "image-to-video" and not model.get("source_image_field"):
            issues.append("image-to-video reference routes require source_image_field")
    if model.get("provider") == "fal_queue":
        if not model.get("result_path_template"):
            issues.append("fal_queue requires result_path_template")
        if model.get("reference_field") != "image_urls":
            issues.append("fal_queue Seedance reference-to-video expects reference_field=image_urls")
        if model.get("auth_scheme") != "Key":
            issues.append("fal_queue expects auth_scheme=Key")
    if model.get("max_paid_submissions_per_shot") is not None and int(model.get("max_paid_submissions_per_shot")) != 1:
        issues.append("max_paid_submissions_per_shot must be 1 for guarded commerce production")
    max_prompt_raw = model.get("max_prompt_chars")
    prompt_budget_raw = model.get("prompt_budget_chars")
    if max_prompt_raw is not None or prompt_budget_raw is not None:
        if max_prompt_raw is None:
            issues.append("prompt_budget_chars requires max_prompt_chars")
        elif prompt_budget_raw is None:
            issues.append("max_prompt_chars requires prompt_budget_chars")
        else:
            max_prompt_chars = int(max_prompt_raw)
            prompt_budget_chars = int(prompt_budget_raw)
            if max_prompt_chars <= 0:
                issues.append("max_prompt_chars must be positive")
            if prompt_budget_chars <= 0:
                issues.append("prompt_budget_chars must be positive")
            if prompt_budget_chars > max_prompt_chars:
                issues.append("prompt_budget_chars must be <= max_prompt_chars")
    if model.get("provider_overlay_text_policy") is not None and model.get("provider_overlay_text_policy") != "forbid_generated_written_elements":
        issues.append("provider_overlay_text_policy must forbid generated written elements")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Path to model config JSON")
    parser.add_argument("--model-key", help="Model key to validate as selected default")
    parser.add_argument("--require-key", action="store_true", help="Fail if no API key env var is set")
    args = parser.parse_args()

    try:
        loaded_env_files = load_runtime_env()
        config = load_config(args.config)
        selected = get_model_config(config, args.model_key)
        selected_key_names = model_api_key_names(selected)
        selected_api_key = find_api_key(required=False, names=selected_key_names)
        report = {
            "config": str(Path(args.config).resolve()) if args.config else "default",
            "default_model": config.get("default_model"),
            "selected_model": selected.get("key"),
            "selected_model_id": selected.get("model"),
            "selected_base_url": selected.get("base_url"),
            "selected_generation_path": selected.get("generation_path"),
            "selected_api_key_env_names": selected_key_names,
            "models": {},
            "loaded_env_files": loaded_env_files,
            "api_key_present": bool(selected_api_key),
            "api_key_preview": redact(selected_api_key),
        }
        errors: list[str] = []
        for key, model in (config.get("models") or {}).items():
            issues = validate_model(model)
            report["models"][key] = {
                "enabled": model.get("enabled", True),
                "model": model.get("model"),
                "official_model_family": model.get("official_model_family") or model.get("model"),
                "provider_model_alias": model.get("provider_model_alias") or model.get("model"),
                "provider_contract_version": model.get("provider_contract_version"),
                "provider": model.get("provider"),
                "base_url_set": bool(model.get("base_url")),
                "duration": [model.get("min_duration_seconds"), model.get("max_duration_seconds")],
                "allowed_duration_seconds": model.get("allowed_duration_seconds"),
                "allowed_multi_reference_duration_seconds": model.get("allowed_multi_reference_duration_seconds"),
                "billing_unit": model.get("billing_unit", "provider_defined"),
                "cost_guard_unit": model.get("cost_guard_unit", "provider_submission"),
                "max_paid_submissions_per_shot": model.get("max_paid_submissions_per_shot", 1),
                "max_prompt_chars": model.get("max_prompt_chars"),
                "prompt_budget_chars": model.get("prompt_budget_chars"),
                "duration_field": model.get("duration_field", "duration"),
                "source_image_field": model.get("source_image_field"),
                "source_payload_format": model.get("source_payload_format"),
                "input_mode": model.get("input_mode") or model.get("mode"),
                "supports_text_to_video": bool(model.get("supports_text_to_video")),
                "supports_audio": bool(model.get("supports_audio", False)),
                "supports_lip_sync": bool(model.get("supports_lip_sync", False)),
                "supports_multi_segment_generation": bool(model.get("supports_multi_segment_generation", False)),
                "supports_multiple_references": bool(model.get("supports_multiple_references")),
                "reference_field": model.get("reference_field"),
                "reference_payload_format": model.get("reference_payload_format"),
                "reference_prompt_style": model.get("reference_prompt_style"),
                "max_reference_images": model.get("max_reference_images"),
                "max_duration_multi_reference_seconds": model.get("max_duration_multi_reference_seconds"),
                "max_duration_with_references_seconds": model.get("max_duration_with_references_seconds"),
                "api_key_env_names": model.get("api_key_env_names"),
                "auth_scheme": model.get("auth_scheme", "Bearer"),
                "result_path_template": model.get("result_path_template"),
                "payload_defaults": model.get("payload_defaults"),
                "omit_model_from_payload": bool(model.get("omit_model_from_payload")),
                "issues": issues,
            }
            if issues and model.get("enabled", True):
                errors.extend(f"{key}: {issue}" for issue in issues)
        if args.require_key:
            find_api_key(required=True, names=selected_key_names)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if errors:
            raise ScriptError("; ".join(errors))
        return 0
    except ScriptError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
