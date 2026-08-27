#!/usr/bin/env python3
"""Validate platform, scenario, compliance, model, and asset contracts in a generation plan."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from _common import ScriptError, asset_value, get_model_config, load_config, load_json, local_asset_digest
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
        supports_audio = bool(payload_defaults.get("generate_audio")) or model.get("provider") in {"mikuapi.org", "119337", "fal_queue"}
    return {
        "model_key": model.get("key"),
        "model": model.get("model"),
        "provider": model.get("provider"),
        "input_mode": model.get("input_mode") or model.get("mode"),
        "supports_multiple_references": bool(model.get("supports_multiple_references")),
        "max_reference_images": int(model.get("max_reference_images") or 0),
        "reference_index_base": int(model.get("reference_index_base", 1)),
        "reference_mode_exclusive_with_source": bool(model.get("reference_mode_exclusive_with_source")),
        "supports_audio": bool(supports_audio),
        "supports_preset_voice_references": bool(model.get("supports_preset_voice_references")),
        "max_reference_audios": int(model.get("max_reference_audios") or 0),
        "supports_native_speech_output": bool(
            model.get("supports_native_speech_output", model.get("supports_lip_sync", supports_audio))
        ),
        "supports_voice_conditioned_speech": bool(
            model.get("supports_voice_conditioned_speech", False)
        ),
        "frame_exact_lip_sync_guaranteed": bool(model.get("frame_exact_lip_sync_guaranteed", False)),
        "supports_timecoded_story_beats": bool(
            model.get("supports_timecoded_story_beats", model.get("supports_multi_segment_generation", True))
        ),
        "min_duration_seconds": int(model.get("min_duration_seconds") or 0),
        "max_duration_seconds": int(model.get("max_duration_seconds") or 0),
        "official_max_duration_seconds": int(model.get("official_capability_max_duration_seconds") or model.get("max_duration_seconds") or 0),
        "planning_max_duration_seconds": int(model.get("planning_max_duration_seconds") or model.get("max_duration_seconds") or 0),
        "duration_reliability_status": model.get("duration_reliability_status") or "configured_contract",
        "max_prompt_chars": model.get("max_prompt_chars"),
        "prompt_budget_chars": model.get("prompt_budget_chars"),
        "allowed_duration_seconds": [int(value) for value in (model.get("allowed_duration_seconds") or [])],
        "allowed_multi_reference_duration_seconds": [
            int(value) for value in (model.get("allowed_multi_reference_duration_seconds") or [])
        ],
        "reference_asset_policy": model.get("reference_asset_policy", "provider_specific"),
        "require_generated_video_references": bool(model.get("require_generated_video_references")),
        "require_generated_product_reference": bool(model.get("require_generated_product_reference")),
        "require_product_anchor_reference": bool(model.get("require_product_anchor_reference")),
        "product_anchor_first": bool(model.get("product_anchor_first")),
        "require_local_generated_references": bool(model.get("require_local_generated_references")),
        "allow_storyboard_reference_upload": bool(model.get("allow_storyboard_reference_upload", True)),
        "raw_product_assets_are_provider_inputs": bool(model.get("raw_product_assets_are_provider_inputs", True)),
        "raw_non_product_assets_are_provider_inputs": bool(model.get("raw_non_product_assets_are_provider_inputs", True)),
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
            severity="warning",
        )
        structure = str(platform.get("recommended_structure") or "").lower()
        add_check(checks, "TikTok/Douyin plan includes a strong hook structure", "hook" in structure, f"recommended_structure={platform.get('recommended_structure')}")
        add_check(checks, "TikTok/Douyin plan has a CTA type", bool(platform.get("cta_type")), f"cta_type={platform.get('cta_type')}", severity="warning")

    if profile_key == "xiaohongshu":
        risks = " ".join(platform.get("common_risks") or [])
        add_check(checks, "Xiaohongshu plan includes authenticity risk control", "fake" in risks or "experience" in risks or "真实" in risks, f"common_risks={platform.get('common_risks')}")
        add_check(checks, "Xiaohongshu plan has compliance contract", bool(compliance), f"claim_risk={compliance.get('claim_risk')}", severity="warning")

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
    require_generated = bool(model_contract.get("require_generated_video_references"))

    add_check(checks, "Model capability contract exists", bool(model_contract), f"model={model_contract.get('model')}")
    if supports_refs:
        add_check(checks, "Multi-reference upload count fits model limit", len(video_refs) <= max_refs, f"reference_count={len(video_refs)}, max_reference_images={max_refs}")
        confirmed_values = {asset_value(ref) for ref in references if asset_value(ref)}
        included_values = {asset_value(ref) for ref in video_refs if asset_value(ref)}
        missing = sorted(confirmed_values - included_values)
        add_check(checks, "Confirmed reference images are included in multi-reference payload plan", not missing, f"missing={missing}")
        prompt_maps = [item for shot in shots for item in (shot.get("reference_prompt_map") or [])]
        tokens = [str(item.get("token") or "") for item in prompt_maps]
        add_check(
            checks,
            "Every reference has one unique prompt token and role instruction",
            bool(video_refs) and len(tokens) == len(video_refs) * max(1, len(shots))
            and len(set(tokens[:len(video_refs)])) == len(video_refs)
            and all(item.get("instruction") for item in prompt_maps),
            f"reference_count={len(video_refs)}; first_shot_tokens={tokens[:len(video_refs)]}",
        )
        if require_generated:
            raw_inputs = asset_contract.get("input_evidence_assets") or plan.get("input_evidence_assets") or []
            raw_digests = {local_asset_digest(asset) for asset in raw_inputs if local_asset_digest(asset)}
            uploaded_digests = {local_asset_digest(asset) for asset in video_refs if local_asset_digest(asset)}
            roles = [normalized(str(asset.get("role") or "reference")) for asset in video_refs]
            product_anchor_ok = bool(video_refs) and roles[0] == "product" and video_refs[0].get("provenance") == "generated_from_approved_visual_plan"
            support_refs = video_refs
            provenance_ok = all(
                asset.get("provenance") == "generated_from_approved_visual_plan"
                and asset.get("provider_upload_allowed") is True
                for asset in support_refs
            )
            local_ok = all(asset.get("kind") == "file" and Path(str(asset_value(asset))).is_file() for asset in support_refs)
            forbidden_storyboards = sorted(
                role for role in roles if role in {"storyboard", "storyboard_sheet", "shot_plan", "storyboard_preview"}
            )
            previews = asset_contract.get("approval_preview_assets") or plan.get("approval_preview_assets") or []
            preview_values = {asset_value(asset) for asset in previews if asset_value(asset)}
            uploaded_values = {asset_value(asset) for asset in video_refs if asset_value(asset)}
            add_check(
                checks,
                "All Provider references are generated and the product master is first",
                bool(raw_inputs)
                and product_anchor_ok
                and asset_contract.get("raw_product_inputs_provider_upload_allowed") is False
                and asset_contract.get("raw_non_product_inputs_provider_upload_allowed") is False
                and not (uploaded_digests & raw_digests),
                f"product_anchor_ok={product_anchor_ok}; provider_raw_overlap={sorted(uploaded_digests & raw_digests)}",
            )
            add_check(
                checks,
                "Every Provider reference was generated from the approved visual plan",
                bool(support_refs) and provenance_ok,
                f"support_reference_count={len(support_refs)}; provenance_ok={provenance_ok}",
            )
            if model_contract.get("require_generated_product_reference"):
                add_check(
                    checks,
                    "Generated reference set includes a professional product master",
                    "product" in roles,
                    f"roles={roles}",
                )
            if model_contract.get("require_local_generated_references"):
                add_check(
                    checks,
                    "Generated Provider references are locally saved files",
                    local_ok,
                    f"local_ok={local_ok}",
                )
            if not model_contract.get("allow_storyboard_reference_upload", True):
                add_check(
                    checks,
                    "Storyboard/contact sheet remains review-only",
                    not forbidden_storyboards and not (preview_values & uploaded_values),
                    f"forbidden_roles={forbidden_storyboards}; preview_upload_overlap={sorted(preview_values & uploaded_values)}",
                )
            visual_reference_plan = ((plan.get("visual_design_contract") or {}).get("reference_plan") or [])
            visual_roles = {normalized(str(item.get("role") or "reference")): item for item in visual_reference_plan}
            incomplete_visual_roles = sorted(
                role for role in roles
                if role not in visual_roles
                or visual_roles[role].get("source") != "generated_from_approved_visual_plan"
                or not str(visual_roles[role].get("image_prompt") or "").strip()
            )
            add_check(
                checks,
                "Visual plan defines a generation prompt for every uploaded reference",
                not incomplete_visual_roles,
                f"incomplete_roles={incomplete_visual_roles}",
                severity="warning",
            )
            qc_failures = []
            missing_fact_sources = []
            for asset in video_refs:
                role = normalized(str(asset.get("role") or "reference"))
                qc_status = normalized(str((asset.get("multimodal_qc_result") or {}).get("status") or ""))
                if qc_status not in {"pass", "passed", "approved"}:
                    qc_failures.append(f"{role}:{qc_status or 'missing'}")
                fact_ids = [
                    str(value).strip()
                    for value in (asset.get("fact_source_asset_ids") or [])
                    if str(value).strip()
                ]
                if not fact_ids:
                    missing_fact_sources.append(role)
            add_check(
                checks,
                "Optional AI consistency review is recorded before Stage 2",
                not qc_failures,
                f"Stage 2 user review remains the approval gate; advisory_findings={qc_failures}",
                severity="warning",
            )
            add_check(
                checks,
                "Generated Provider references cite concrete input evidence assets",
                not missing_fact_sources,
                f"missing_fact_source_asset_ids={missing_fact_sources}",
                severity="warning",
            )
            product_identity_evidence = asset_contract.get("product_identity_evidence") or []
            if product_identity_evidence:
                product_identity_ids = [
                    str(asset.get("id") or "").strip()
                    for asset in product_identity_evidence
                    if str(asset.get("id") or "").strip()
                ]
                input_by_id = {
                    str(asset.get("id")): asset
                    for asset in raw_inputs
                    if str(asset.get("id") or "").strip()
                }
                identity_collection_failures = []
                for asset_id in product_identity_ids:
                    if asset_id not in input_by_id:
                        identity_collection_failures.append(f"unknown_identity_asset:{asset_id}")
                recorded_identity_ids = [
                    str(value).strip()
                    for value in (asset_contract.get("product_identity_evidence_asset_ids") or [])
                    if str(value).strip()
                ]
                if recorded_identity_ids != product_identity_ids:
                    identity_collection_failures.append(
                        f"ordered_id_mismatch:{recorded_identity_ids}!={product_identity_ids}"
                    )
                add_check(
                    checks,
                    "Product identity evidence is an ordered subset of saved input evidence",
                    bool(product_identity_ids) and not identity_collection_failures,
                    f"product_identity_evidence_asset_ids={product_identity_ids}; failures={identity_collection_failures}",
                    severity="warning",
                )

                imagegen_record_failures = []
                product_dependent_count = 0
                for asset in support_refs:
                    if asset.get("product_identity_required") is not True:
                        continue
                    product_dependent_count += 1
                    role = normalized(str(asset.get("role") or "reference"))
                    generation_ids = [
                        str(value).strip()
                        for value in (asset.get("generation_input_asset_ids") or [])
                        if str(value).strip()
                    ]
                    missing_identity_ids = [
                        asset_id for asset_id in product_identity_ids if asset_id not in generation_ids
                    ]
                    unknown_generation_ids = [
                        asset_id for asset_id in generation_ids if asset_id not in input_by_id
                    ]
                    expected_paths = [asset_value(input_by_id[asset_id]) for asset_id in generation_ids if asset_id in input_by_id]
                    expected_hashes = [local_asset_digest(input_by_id[asset_id]) for asset_id in generation_ids if asset_id in input_by_id]
                    recorded_paths = [str(value) for value in (asset.get("generation_input_paths") or [])]
                    recorded_hashes = [str(value) for value in (asset.get("generation_input_sha256") or [])]
                    checked_ids = [
                        str(value).strip()
                        for value in ((asset.get("multimodal_qc_result") or {}).get("checked_against_asset_ids") or [])
                        if str(value).strip()
                    ]
                    if missing_identity_ids:
                        imagegen_record_failures.append(f"{role}:missing={missing_identity_ids}")
                    if unknown_generation_ids:
                        imagegen_record_failures.append(f"{role}:unknown={unknown_generation_ids}")
                    if recorded_paths != expected_paths:
                        imagegen_record_failures.append(f"{role}:path_record_mismatch")
                    if recorded_hashes != expected_hashes:
                        imagegen_record_failures.append(f"{role}:sha256_record_mismatch")
                    if any(asset_id not in checked_ids for asset_id in product_identity_ids):
                        imagegen_record_failures.append(f"{role}:qc_missing_identity_evidence")
                    if asset.get("generation_input_policy") != "all_relevant_product_identity_evidence":
                        imagegen_record_failures.append(f"{role}:wrong_generation_input_policy")
                add_check(
                    checks,
                    "Product-dependent generated references used the complete product identity evidence set",
                    product_dependent_count > 0 and not imagegen_record_failures,
                    "complete product identity evidence set; "
                    f"product_dependent_count={product_dependent_count}; failures={imagegen_record_failures}",
                    severity="warning",
                )
            for shot in shots:
                prompt = str(shot.get("prompt") or "")
                shot_tokens = [str(item.get("token") or "") for item in (shot.get("reference_prompt_map") or [])]
                repeated = {token: prompt.count(token) for token in shot_tokens if prompt.count(token) != 1}
                add_check(
                    checks,
                    f"{shot.get('id')} uses one canonical reference-token map",
                    not repeated,
                    f"noncanonical_token_counts={repeated}",
                )
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
        add_check(
            checks,
            "Selected model supports native on-camera speech output",
            bool(model_contract.get("supports_native_speech_output")),
            (
                f"supports_native_speech_output={model_contract.get('supports_native_speech_output')}; "
                f"supports_voice_conditioned_speech={model_contract.get('supports_voice_conditioned_speech')}; "
                f"frame_exact_lip_sync_guaranteed={model_contract.get('frame_exact_lip_sync_guaranteed')}"
            ),
        )
    if len(shots) > 1:
        add_check(
            checks,
            "Selected model route supports planned time-coded or multi-request storytelling",
            bool(model_contract.get("supports_timecoded_story_beats", True)),
            f"shot_count={len(shots)}",
        )


def validate_production_core(plan: dict, checks: list[dict], model_contract: dict) -> None:
    shots = plan.get("shots") or []
    asset_contract = plan.get("reference_asset_contract") or plan.get("asset_contract") or {}
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
    planning_max = int(model_contract.get("planning_max_duration_seconds") or model_contract.get("max_duration_seconds") or 0)
    if planning_max:
        add_check(
            checks,
            "Every paid request stays within the selected route's reliable planning ceiling",
            all(seconds <= planning_max for seconds in shot_durations),
            f"shots={shot_durations}; planning_max_duration_seconds={planning_max}; reliability={model_contract.get('duration_reliability_status')}",
        )
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
        director_clip = shot.get("director_clip") or {}
        beat_timeline = director_clip.get("beat_timeline") or []
        beat_moves = [beat.get("camera_move") for beat in beat_timeline if isinstance(beat, dict)]
        add_check(
            checks,
            f"{shot.get('id')} has one declared main camera move per beat",
            (
                bool(beat_moves)
                and all(move in {"push_in", "pull_back", "pan", "tilt", "orbit", "track", "locked_macro", "static", "crane", "pedestal", "handheld_follow", "dolly_zoom", "zoom", "whip_pan"} for move in beat_moves)
                and prompt_contract.get("camera_move") == "timecoded_per_beat"
                and prompt_contract.get("camera_moves_by_beat") == beat_moves
            ) if beat_timeline else (
                bool(director_clip.get("camera_move"))
                and prompt_contract.get("camera_move") == director_clip.get("camera_move")
            ),
            (
                f"director_beats={beat_moves}; prompt_contract={prompt_contract.get('camera_moves_by_beat')}"
                if beat_timeline else
                f"director={director_clip.get('camera_move')}; prompt_contract={prompt_contract.get('camera_move')}"
            ),
        )
        add_check(
            checks,
            f"{shot.get('id')} ends with a structured AUDIO block",
            prompt.count("AUDIO:") == 1 and prompt.rstrip().endswith("."),
            f"audio_block_count={prompt.count('AUDIO:')}",
        )
        if int(plan.get("plan_schema_version") or 1) >= 2:
            reference_count = len(shot.get("video_references") or [])
            add_check(
                checks,
                f"{shot.get('id')} has exactly one compiler-owned director timeline",
                prompt.count("Cuts:") + prompt.count("Sequence:") == 1,
                f"cuts_count={prompt.count('Cuts:')}; sequence_count={prompt.count('Sequence:')}",
            )
            add_check(
                checks,
                f"{shot.get('id')} has one compiler-owned reference map when references are uploaded",
                prompt.count("Reference image map:") == (1 if reference_count else 0),
                f"reference_count={reference_count}; map_count={prompt.count('Reference image map:')}",
            )
            add_check(
                checks,
                f"{shot.get('id')} has no empty comma-delimited instruction",
                re.search(r",\s*,", prompt) is None,
                f"empty_comma_instruction={re.search(r',\s*,', prompt) is not None}",
            )
        script = str(shot.get("spoken_script") or "").strip()
        boundary = shot.get("script_boundary") or {}
        if script:
            actual_occurrences = prompt.count(script)
            contract_occurrences = prompt_contract.get("spoken_script_occurrences")
            add_check(
                checks,
                f"{shot.get('id')} spoken script appears exactly once in the Provider prompt",
                actual_occurrences == 1 and contract_occurrences == 1,
                f"actual={actual_occurrences}; prompt_contract.spoken_script_occurrences={contract_occurrences}",
            )
            add_check(
                checks,
                f"{shot.get('id')} spoken script has a stitch-safe complete boundary",
                boundary.get("stitch_safe") is True,
                f"script_boundary.stitch_safe={boundary.get('stitch_safe')}; is_final={index == len(shots) - 1}",
            )

    audio_contract = plan.get("audio_contract") or {}
    if int(plan.get("plan_schema_version") or 1) >= 2:
        talent = ((plan.get("creative_contract") or {}).get("talent_contract") or {})
        presence = str(talent.get("presence") or "")
        add_check(
            checks,
            "Visible-talent presence is explicit and unambiguous",
            presence in {"none", "hands_only", "presenter"},
            f"talent_presence={presence}",
        )
        prompts = [str(shot.get("prompt") or "") for shot in shots]
        roles = {normalized(str(asset.get("role") or "")) for asset in (asset_contract.get("video_reference_assets") or [])}
        if presence == "none":
            add_check(
                checks,
                "Product-only plan explicitly forbids all visible humans",
                all("No person, face, body, hand, or human silhouette appears" in prompt for prompt in prompts),
                "required explicit no-human directive in every Provider prompt",
            )
        if presence == "presenter" and model_contract.get("require_generated_video_references"):
            add_check(
                checks,
                "Visible presenter has a generated presenter control reference",
                "presenter" in roles,
                f"reference_roles={sorted(roles)}",
            )
    if int(plan.get("plan_schema_version") or 1) >= 2 and audio_contract.get("speech_required"):
        voice_ids = [str(value) for value in (audio_contract.get("preset_voice_ids") or []) if str(value).strip()]
        if voice_ids:
            add_check(
                checks,
                "audio.preset_voice_is_explicit_user_choice",
                audio_contract.get("preset_voice_source") in {"cli_user_explicit", "brief_user_explicit"},
                f"preset_voice_source={audio_contract.get('preset_voice_source')}",
            )
            add_check(
                checks,
                "Explicit preset voice plan maps each reference audio to one prompt token",
                len(voice_ids) <= int(model_contract.get("max_reference_audios") or len(voice_ids))
                and audio_contract.get("voice_prompt_token") == "<AUDIO_0>",
                f"voice_ids={voice_ids}; voice_prompt_token={audio_contract.get('voice_prompt_token')}",
            )
        else:
            audio_tokens = [
                token
                for shot in shots
                for token in re.findall(r"<AUDIO_\d+>", str(shot.get("prompt") or ""))
            ]
            add_check(
                checks,
                "Prompt-native speech needs no preset voice or voice-roster gate",
                not audio_tokens and bool(audio_contract.get("voice_description") or plan.get("spoken_script")),
                (
                    f"voice_policy={audio_contract.get('voice_policy')}; voice_ids={voice_ids}; "
                    f"audio_tokens={audio_tokens}; voice_description={bool(audio_contract.get('voice_description'))}"
                ),
            )

    sound = plan.get("sound_design_contract") or {}
    if int(plan.get("plan_schema_version") or 1) >= 2 and sound:
        mode = str(sound.get("mode") or "")
        required_layers = sound.get("required_layers") or {}
        non_speech_required = bool(sound.get("non_speech_required"))
        add_check(
            checks,
            "Commercial sound mode is explicit",
            mode in {"layered_native", "ambience_led", "voice_only"},
            f"sound_mode={mode}",
            severity="warning",
        )
        add_check(
            checks,
            "Required non-speech sound has at least one sonic bed",
            not non_speech_required or bool(required_layers.get("sfx") or required_layers.get("ambience")),
            f"non_speech_required={non_speech_required}; required_layers={required_layers}",
            severity="warning",
        )
        add_check(
            checks,
            "Required commercial sound uses an audio-capable Provider route",
            not non_speech_required or sound.get("native_provider_sound") is True,
            f"native_provider_sound={sound.get('native_provider_sound')}",
            severity="warning",
        )
        if non_speech_required:
            add_check(
                checks,
                "Every Provider prompt contains the planned synchronized sound layers",
                all(
                    "Cues=" in str(shot.get("prompt") or "")
                    and "Ambience=" in str(shot.get("prompt") or "")
                    and "Mix=" in str(shot.get("prompt") or "")
                    for shot in shots
                ),
                "required semantic fields: Cues, Ambience and Mix",
                severity="warning",
            )
            sound_coverage = [
                (shot.get("prompt_contract") or {}).get("sound_cue_coverage") or {}
                for shot in shots
                if (shot.get("prompt_contract") or {}).get("compiler") == "director-commerce-v8"
            ]
            add_check(
                checks,
                "Every v8 sound prompt is self-contained and preserves planned clip/beat cues",
                all(
                    item.get("clip_sfx_rendered") is True
                    and item.get("all_beat_cues_rendered_in_timeline") is True
                    and item.get("audio_block_links_timecoded_cues") is True
                    and item.get("self_contained") is True
                    for item in sound_coverage
                ) if sound_coverage else True,
                f"sound_cue_coverage={sound_coverage}",
                severity="warning",
            )
        if required_layers.get("music"):
            add_check(
                checks,
                "Music-required prompts do not disable music",
                all("Music=no music" not in str(shot.get("prompt") or "") for shot in shots),
                "Music=no music is incompatible with original_instrumental policy",
                severity="warning",
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
        severity="warning",
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
