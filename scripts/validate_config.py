#!/usr/bin/env python3
"""Validate ai-commerce-video model config and environment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _common import (
    ScriptError,
    find_api_key,
    get_model_config,
    load_config,
    load_runtime_env,
    model_api_key_keychain_service,
    model_api_key_names,
)


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
    planning_max_duration = int(model.get("planning_max_duration_seconds") or max_duration)
    default_duration = int(model.get("default_duration_seconds", 15))
    if min_duration <= 0:
        issues.append("min_duration_seconds must be positive")
    if max_duration < min_duration:
        issues.append("max_duration_seconds must be >= min_duration_seconds")
    if not (min_duration <= planning_max_duration <= max_duration):
        issues.append("planning_max_duration_seconds must stay within model duration limits")
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
        reference_index_base = int(model.get("reference_index_base", 1))
        if reference_index_base not in {0, 1}:
            issues.append("reference_index_base must be 0 or 1")
        if model.get("input_mode") == "image-to-video" and not model.get("source_image_field"):
            issues.append("image-to-video reference routes require source_image_field")
        if model.get("input_mode") == "reference-to-video" and model.get("reference_mode_exclusive_with_source") is not True:
            issues.append("reference-to-video routes must set reference_mode_exclusive_with_source=true")
        if model.get("require_generated_video_references"):
            if model.get("reference_asset_policy") != "generated_reference_pack_only":
                issues.append("professional reference routes require reference_asset_policy=generated_reference_pack_only")
            if model.get("include_product_as_reference") is not False:
                issues.append("professional reference routes must not auto-upload the raw product evidence")
            if model.get("raw_product_assets_are_provider_inputs") is not False:
                issues.append("professional reference routes must set raw_product_assets_are_provider_inputs=false")
            if model.get("raw_non_product_assets_are_provider_inputs") is not False:
                issues.append("professional reference routes must block raw non-product evidence")
            if model.get("require_generated_product_reference") is not True:
                issues.append("professional reference routes must require a generated professional product master")
            if model.get("require_product_anchor_reference") is not True or model.get("product_anchor_first") is not True:
                issues.append("professional reference routes must require the product anchor in the first slot")
            if model.get("require_local_generated_references") is not True:
                issues.append("generated reference routes must require locally saved generated references")
            if model.get("allow_storyboard_reference_upload") is not False:
                issues.append("generated reference routes must keep storyboard/contact sheets review-only")
        if model.get("supports_preset_voice_references"):
            if not model.get("reference_audio_field"):
                issues.append("preset voice references require reference_audio_field")
            if int(model.get("max_reference_audios") or 0) <= 0:
                issues.append("preset voice references require positive max_reference_audios")
            approved_voices = model.get("approved_preset_voice_ids") or model.get("known_preset_voice_ids")
            if not isinstance(approved_voices, list) or not approved_voices:
                issues.append("preset voice references require a non-empty approved_preset_voice_ids allowlist")
            if model.get("supports_voice_conditioned_speech") is not True:
                issues.append("preset voice references must declare supports_voice_conditioned_speech=true")
            if model.get("frame_exact_lip_sync_guaranteed") is not False:
                issues.append("preset voice references must declare frame_exact_lip_sync_guaranteed=false")
    if model.get("provider") == "fal_queue":
        if not model.get("result_path_template"):
            issues.append("fal_queue requires result_path_template")
        if model.get("reference_field") != "image_urls":
            issues.append("fal_queue Seedance reference-to-video expects reference_field=image_urls")
        if model.get("auth_scheme") != "Key":
            issues.append("fal_queue expects auth_scheme=Key")
    if model.get("require_pre_submit_readiness") and not model.get("models_path"):
        issues.append("require_pre_submit_readiness requires models_path")
    if model.get("supports_audio"):
        if model.get("native_sound_design_prompting") not in {
            "prompt_directed_best_effort",
            "unsupported",
            "provider_specific",
        }:
            issues.append(
                "audio-capable models must declare native_sound_design_prompting as prompt_directed_best_effort, unsupported, or provider_specific"
            )
        if not isinstance(model.get("native_sound_layers_guaranteed"), bool):
            issues.append("audio-capable models must declare native_sound_layers_guaranteed as a boolean")
        if model.get("native_sound_delivery_strategy") not in {
            "prompt_directed_best_effort",
            "provider_guaranteed",
            "unsupported",
        }:
            issues.append(
                "audio-capable models must declare native_sound_delivery_strategy as prompt_directed_best_effort, provider_guaranteed, or unsupported"
            )
        if not isinstance(model.get("native_cross_clip_audio_state_shared"), bool):
            issues.append("audio-capable models must declare native_cross_clip_audio_state_shared as a boolean")
        if not isinstance(model.get("exact_score_continuity_requires_local_post_mix"), bool):
            issues.append(
                "audio-capable models must declare exact_score_continuity_requires_local_post_mix as a boolean"
            )
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
    if any(
        field in model
        for field in (
            "provider_documented_max_prompt_chars",
            "adapter_max_prompt_chars",
            "workflow_prompt_budget_chars",
            "prompt_limit_source",
        )
    ):
        if int(model.get("adapter_max_prompt_chars") or 0) != int(max_prompt_raw or 0):
            issues.append("adapter_max_prompt_chars must match the legacy max_prompt_chars compatibility field")
        if int(model.get("workflow_prompt_budget_chars") or 0) != int(prompt_budget_raw or 0):
            issues.append("workflow_prompt_budget_chars must match the legacy prompt_budget_chars compatibility field")
        if not str(model.get("prompt_limit_source") or "").strip():
            issues.append("prompt_limit_source is required when prompt limit provenance fields are used")
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
        selected_keychain_service = model_api_key_keychain_service(selected)
        selected_api_key = find_api_key(
            required=False,
            names=selected_key_names,
            keychain_service=selected_keychain_service,
        )
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
                "models_path": model.get("models_path"),
                "voices_path": model.get("voices_path"),
                "voice_roster_policy": model.get("voice_roster_policy"),
                "default_voice_policy": model.get("default_voice_policy"),
                "approved_preset_voice_ids": model.get("approved_preset_voice_ids"),
                "require_pre_submit_readiness": bool(model.get("require_pre_submit_readiness")),
                "duration": [model.get("min_duration_seconds"), model.get("max_duration_seconds")],
                "planning_max_duration_seconds": model.get("planning_max_duration_seconds") or model.get("max_duration_seconds"),
                "duration_reliability_status": model.get("duration_reliability_status"),
                "allowed_duration_seconds": model.get("allowed_duration_seconds"),
                "allowed_multi_reference_duration_seconds": model.get("allowed_multi_reference_duration_seconds"),
                "billing_unit": model.get("billing_unit", "provider_defined"),
                "cost_guard_unit": model.get("cost_guard_unit", "provider_submission"),
                "max_paid_submissions_per_shot": model.get("max_paid_submissions_per_shot", 1),
                "max_prompt_chars": model.get("max_prompt_chars"),
                "prompt_budget_chars": model.get("prompt_budget_chars"),
                "provider_documented_max_prompt_chars": model.get("provider_documented_max_prompt_chars"),
                "adapter_max_prompt_chars": model.get("adapter_max_prompt_chars", model.get("max_prompt_chars")),
                "workflow_prompt_budget_chars": model.get("workflow_prompt_budget_chars", model.get("prompt_budget_chars")),
                "prompt_limit_source": model.get("prompt_limit_source", "legacy_provider_configuration"),
                "duration_field": model.get("duration_field", "duration"),
                "source_image_field": model.get("source_image_field"),
                "source_payload_format": model.get("source_payload_format"),
                "input_mode": model.get("input_mode") or model.get("mode"),
                "supports_text_to_video": bool(model.get("supports_text_to_video")),
                "supports_audio": bool(model.get("supports_audio", False)),
                "supports_native_speech_output": bool(
                    model.get("supports_native_speech_output", model.get("supports_lip_sync", False))
                ),
                "native_sound_design_prompting": model.get("native_sound_design_prompting"),
                "native_sound_layers_guaranteed": bool(model.get("native_sound_layers_guaranteed", False)),
                "native_sound_delivery_strategy": model.get("native_sound_delivery_strategy"),
                "native_cross_clip_audio_state_shared": bool(
                    model.get("native_cross_clip_audio_state_shared", False)
                ),
                "exact_score_continuity_requires_local_post_mix": bool(
                    model.get("exact_score_continuity_requires_local_post_mix", True)
                ),
                "supports_voice_conditioned_speech": bool(
                    model.get("supports_voice_conditioned_speech", False)
                ),
                "frame_exact_lip_sync_guaranteed": bool(model.get("frame_exact_lip_sync_guaranteed", False)),
                "supports_timecoded_story_beats": bool(
                    model.get("supports_timecoded_story_beats", model.get("supports_multi_segment_generation", False))
                ),
                "supports_multiple_references": bool(model.get("supports_multiple_references")),
                "reference_field": model.get("reference_field"),
                "reference_payload_format": model.get("reference_payload_format"),
                "reference_prompt_style": model.get("reference_prompt_style"),
                "reference_index_base": model.get("reference_index_base", 1),
                "reference_index_contract_source": model.get("reference_index_contract_source", "provider_route_configuration"),
                "supports_video_extension": bool(model.get("supports_video_extension", False)),
                "video_extension_status": model.get("video_extension_status", "not_configured"),
                "reference_mode_exclusive_with_source": bool(model.get("reference_mode_exclusive_with_source")),
                "max_reference_images": model.get("max_reference_images"),
                "max_duration_multi_reference_seconds": model.get("max_duration_multi_reference_seconds"),
                "max_duration_with_references_seconds": model.get("max_duration_with_references_seconds"),
                "reference_asset_policy": model.get("reference_asset_policy", "provider_specific"),
                "require_generated_video_references": bool(model.get("require_generated_video_references")),
                "require_generated_product_reference": bool(model.get("require_generated_product_reference")),
                "require_product_anchor_reference": bool(model.get("require_product_anchor_reference")),
                "product_anchor_first": bool(model.get("product_anchor_first")),
                "require_local_generated_references": bool(model.get("require_local_generated_references")),
                "allow_storyboard_reference_upload": bool(model.get("allow_storyboard_reference_upload", True)),
                "raw_product_assets_are_provider_inputs": bool(model.get("raw_product_assets_are_provider_inputs", True)),
                "raw_non_product_assets_are_provider_inputs": bool(model.get("raw_non_product_assets_are_provider_inputs", True)),
                "reference_audio_field": model.get("reference_audio_field"),
                "supports_preset_voice_references": bool(model.get("supports_preset_voice_references")),
                "max_reference_audios": model.get("max_reference_audios"),
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
            find_api_key(
                required=True,
                names=selected_key_names,
                keychain_service=selected_keychain_service,
            )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if errors:
            raise ScriptError("; ".join(errors))
        return 0
    except ScriptError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
