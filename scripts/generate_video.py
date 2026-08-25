#!/usr/bin/env python3
"""Submit Grok-compatible video generation requests from a generation plan."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import time
from pathlib import Path

from _common import (
    ScriptError,
    asset_value,
    canonical_digest,
    file_to_data_uri,
    find_api_key,
    get_model_config,
    http_json,
    is_url,
    join_url,
    load_config,
    load_json,
    local_asset_digest,
    model_api_key_names,
    model_api_key_keychain_service,
    model_auth_scheme,
    model_provider,
    model_supports_reference_images,
    network_route_summary,
    validate_provider_prompt_length,
    write_json,
)
from _workflow import (
    acquire_paid_submission_lock,
    load_or_create_jobs,
    record_submission_attempt,
    release_paid_submission_lock,
    transition_job,
    verify_contract,
)


VIDEO_SOURCE_ROLE_PRIORITY = {
    "video_source",
    "final_source",
    "final_frame",
    "first_frame",
    "hero_frame",
    "presenter_product",
    "product_presenter",
}
FORBIDDEN_SUBTITLE_PAYLOAD_KEYS = {
    "caption",
    "captions",
    "subtitle",
    "subtitles",
    "subtitle_file",
    "srt",
    "vtt",
    "lower_third",
    "text_overlay",
}
FORBIDDEN_SUBTITLE_PROMPT_PATTERN = re.compile(
    r"\b(?:subtitles?|captions?|srt|vtt|lower[- ]thirds?|text overlays?)\b|中英双语字幕|中文字幕|英文字幕|字幕",
    re.IGNORECASE,
)


def media_url(image_info: dict) -> str:
    value = image_info.get("value") if isinstance(image_info, dict) else str(image_info)
    if not value:
        raise ScriptError("Missing image value for video request")
    if is_url(value):
        return value
    return file_to_data_uri(Path(value).expanduser().resolve())


def source_payload(image_info: dict, model: dict):
    fmt = (model.get("source_payload_format") or "url_object").strip().lower()
    url = media_url(image_info)
    if fmt in {"url_array", "array", "url_strings"}:
        return [url]
    if fmt in {"url_string", "string"}:
        return url
    return {"url": url}


def reference_payload(ref: dict, model: dict):
    value = ref.get("value") or ref.get("path") or ref.get("url")
    if not value:
        raise ScriptError(f"Reference image missing value/path/url: {ref}")
    url = value if is_url(value) else file_to_data_uri(Path(value).expanduser().resolve())
    payload_format = (model.get("reference_payload_format") or "url_objects").strip().lower()
    if payload_format in {"url_strings", "string_urls", "strings"}:
        return url
    if payload_format in {"role_url_objects", "role_url"}:
        return {"role": ref.get("role", "reference"), "url": url}
    if payload_format in {"nested_image_objects", "nested_image"}:
        return {
            "role": ref.get("role", "reference"),
            "kind": ref.get("kind", "file"),
            "image": {"url": url},
        }
    return {"url": url}


def configured_video_references(plan: dict, shot: dict) -> list[dict]:
    contract = plan.get("asset_contract") or {}
    return shot.get("video_references") or contract.get("video_reference_assets") or []


def _flatten_payload_images(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_flatten_payload_images(item))
        return result
    if isinstance(value, dict):
        result: list[str] = []
        for key in ("url", "image_url", "image"):
            if key in value:
                result.extend(_flatten_payload_images(value[key]))
        return result
    return []


def payload_image_evidence(payload: dict, model: dict) -> list[dict]:
    """Fingerprint the exact image values placed in the outbound payload without duplicating their bytes."""
    source_field = str(model.get("source_image_field") or "image")
    reference_field = str(model.get("reference_field") or "reference_images")
    fields = [(source_field, "source")]
    if reference_field != source_field:
        fields.append((reference_field, "reference"))
    evidence: list[dict] = []
    for field, role in fields:
        for index, value in enumerate(_flatten_payload_images(payload.get(field)), start=1):
            item = {"field": field, "index": index, "role": role, "transport": "unknown", "sha256": ""}
            if value.startswith("data:") and "," in value:
                header, encoded = value.split(",", 1)
                try:
                    raw = base64.b64decode(encoded, validate=True)
                except (ValueError, base64.binascii.Error) as exc:
                    raise ScriptError(f"Invalid base64 source image in payload field {field}[{index}]") from exc
                item.update({
                    "transport": "data_uri",
                    "mime_type": header[5:].split(";", 1)[0],
                    "size_bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                })
            elif is_url(value):
                item.update({
                    "transport": "https_url" if value.startswith("https://") else "http_url",
                    "url_sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
                })
            else:
                item.update({
                    "transport": "opaque",
                    "value_sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
                })
            evidence.append(item)
    return evidence


def request_evidence(payload: dict, model: dict) -> dict:
    prompt = str(payload.get("prompt") or "")
    return {
        "schema_version": "1.0",
        "prompt_char_count": len(prompt),
        "prompt_utf8_bytes": len(prompt.encode("utf-8")),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "payload_sha256": canonical_digest(payload),
        "source_images": payload_image_evidence(payload, model),
        "provider_input_receipt_required": True,
    }


def provider_contract_diagnostic(exc: Exception, payload: dict, model: dict) -> dict | None:
    """Classify a Provider image-count rejection that contradicts the exact outbound payload."""
    message = str(exc)
    if "exactly one reference image" not in message.lower():
        return None
    images = payload_image_evidence(payload, model)
    if len(images) != 1:
        return None
    source_field = str(model.get("source_image_field") or "image")
    return {
        "code": "provider_image_contract_mismatch",
        "provider": model.get("provider"),
        "provider_contract_version": model.get("provider_contract_version"),
        "configured_field": source_field,
        "configured_payload_format": model.get("source_payload_format"),
        "local_image_count": 1,
        "local_image_transport": images[0].get("transport"),
        "automatic_retry_allowed": False,
        "recommended_action": "Keep the shot blocked and ask the Provider to inspect image-field conversion or channel routing.",
    }


def asset_trace(plan: dict, shot: dict, model: dict, references_included: bool, reference_assets: list[dict]) -> dict:
    image = shot.get("image") or plan.get("product_asset") or {}
    contract = plan.get("asset_contract") or {}
    creative_contract = plan.get("creative_contract") or {}
    video_source = contract.get("video_source_asset") or {}
    segment_sources = contract.get("segment_source_assets") or []
    return {
        "reference_strategy": shot.get("reference_strategy") or creative_contract.get("reference_strategy") or "",
        "model_input_mode": model.get("input_mode") or model.get("mode"),
        "model_supports_multiple_references": model_supports_reference_images(model),
        "source_image_field": model.get("source_image_field", "image"),
        "reference_field": model.get("reference_field", "reference_images"),
        "reference_payload_format": model.get("reference_payload_format", "url_objects"),
        "references_included_in_payload": references_included,
        "source_image_included_in_payload": not references_included or bool(model.get("include_source_image_with_references")),
        "reference_mode_exclusive_with_source": bool(model.get("reference_mode_exclusive_with_source")),
        "reference_count": len(reference_assets),
        "reference_asset_policy": model.get("reference_asset_policy", "provider_specific"),
        "raw_input_assets_uploaded": bool(
            model.get("require_generated_video_references")
            and any(ref.get("provenance") != "generated_from_approved_visual_plan" for ref in reference_assets)
        ) if model.get("require_generated_video_references") else None,
        "raw_non_product_assets_uploaded": False if model.get("require_generated_video_references") else None,
        "generated_reference_provenance": [ref.get("provenance") for ref in reference_assets],
        "source_image": {
            "role": image.get("role", "product") if isinstance(image, dict) else "unknown",
            "value": asset_value(image),
            "selected_as": image.get("selected_as") if isinstance(image, dict) else None,
        },
        "locked_video_source": {
            "role": video_source.get("role", "product") if isinstance(video_source, dict) else "unknown",
            "value": asset_value(video_source),
            "selected_as": video_source.get("selected_as") if isinstance(video_source, dict) else None,
        },
        "segment_source_count": len(segment_sources),
        "segment_source_values": [asset_value(asset) for asset in segment_sources],
        "reference_prompt_map": shot.get("reference_prompt_map") or contract.get("reference_prompt_map") or [],
        "payload_reference_roles": [ref.get("role", "reference") for ref in reference_assets],
        "confirmed_reference_roles": [ref.get("role", "reference") for ref in (shot.get("references") or plan.get("references") or [])],
        "subtitle_included_in_payload": False,
        "no_generated_overlay_text_requested": "no newly generated written" in str(shot.get("prompt") or "").lower(),
    }


def validate_legal_request_duration(plan: dict, shot: dict, model: dict) -> None:
    references = configured_video_references(plan, shot)
    if references and model.get("allowed_multi_reference_duration_seconds"):
        allowed = model.get("allowed_multi_reference_duration_seconds") or []
    else:
        allowed = model.get("allowed_duration_seconds") or []
    duration = int(shot.get("duration_seconds") or 0)
    if allowed and duration not in {int(value) for value in allowed}:
        raise ScriptError(
            f"Illegal request duration for {shot.get('id')}: {duration}s is not one of {sorted(int(value) for value in allowed)}"
        )


def _payload_keys(value) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key).strip().lower())
            keys.update(_payload_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_payload_keys(item))
    return keys


def validate_clean_provider_payload(plan: dict, shot: dict, payload: dict) -> None:
    subtitle_plan = plan.get("subtitle_plan") or {}
    if subtitle_plan.get("subtitle_included_in_payload") not in {None, False}:
        raise ScriptError("Provider payload is blocked because subtitle_included_in_payload is not false")
    forbidden = sorted(_payload_keys(payload).intersection(FORBIDDEN_SUBTITLE_PAYLOAD_KEYS))
    if forbidden:
        raise ScriptError(f"Provider payload contains forbidden subtitle/overlay fields: {forbidden}")
    prompt = str(shot.get("prompt") or "").lower()
    match = FORBIDDEN_SUBTITLE_PROMPT_PATTERN.search(prompt)
    if match:
        raise ScriptError(
            f"Provider prompt for {shot.get('id')} contains forbidden subtitle/overlay instruction: {match.group(0)!r}"
        )
    if "no newly generated written" not in prompt:
        raise ScriptError(
            f"Provider prompt for {shot.get('id')} is missing the fixed clean-frame no-written-elements policy"
        )
    if int(plan.get("plan_schema_version") or 1) >= 2:
        audio_count = len(re.findall(r"\bAUDIO\s*:", str(shot.get("prompt") or ""), flags=re.IGNORECASE))
        cuts_count = len(re.findall(r"\bCuts\s*:", str(shot.get("prompt") or ""), flags=re.IGNORECASE))
        sequence_count = len(re.findall(r"\bSequence\s*:", str(shot.get("prompt") or ""), flags=re.IGNORECASE))
        reference_map_count = len(re.findall(r"\bReference image map\s*:", str(shot.get("prompt") or ""), flags=re.IGNORECASE))
        expected_reference_maps = 1 if configured_video_references(plan, shot) else 0
        if audio_count != 1:
            raise ScriptError(f"Provider prompt must contain exactly one AUDIO block; got {audio_count}")
        if cuts_count + sequence_count != 1:
            raise ScriptError(
                "Provider prompt must contain exactly one director timeline block; "
                f"Cuts={cuts_count}, Sequence={sequence_count}"
            )
        if reference_map_count != expected_reference_maps:
            raise ScriptError(
                f"Provider prompt reference map count must be {expected_reference_maps}; got {reference_map_count}"
            )
        if re.search(r",\s*,", str(shot.get("prompt") or "")):
            raise ScriptError("Provider prompt contains an empty comma-delimited instruction")


def validate_asset_consistency(plan: dict, shot: dict, model: dict) -> None:
    image = shot.get("image") or plan.get("product_asset") or {}
    source = asset_value(image)
    contract = plan.get("asset_contract") or {}
    locked_source = asset_value(contract.get("video_source_asset"))
    segment_sources = contract.get("segment_source_assets") or []
    segment_source_values = {asset_value(asset) for asset in segment_sources}
    if segment_source_values:
        if source not in segment_source_values:
            raise ScriptError(
                "Asset mismatch: shot image does not match any approved segment_source_asset. "
                f"shot image={source}; segment sources={sorted(segment_source_values)}"
            )
    elif locked_source and source != locked_source:
        raise ScriptError(
            "Asset mismatch: shot image does not match the locked video_source_asset. "
            f"shot image={source}; locked video source={locked_source}"
        )

    references = shot.get("references") or plan.get("references") or []
    if model_supports_reference_images(model):
        video_refs = configured_video_references(plan, shot)
        if references and not video_refs:
            raise ScriptError(
                "Asset mismatch: confirmed reference image(s) exist, but no video reference assets were prepared for this multi-reference model. "
                "Re-run prepare_project.py so it can build the reference prompt map and payload references."
            )
        if model.get("require_generated_video_references"):
            if not video_refs:
                raise ScriptError("Professional reference route requires a complete generated Reference Pack.")
            roles = [str(ref.get("role") or "reference").strip().lower() for ref in video_refs]
            if model.get("require_product_anchor_reference") and (not roles or roles[0] != "product"):
                raise ScriptError("The first Provider reference must be the generated professional product master.")
            if model.get("require_generated_product_reference") and "product" not in roles:
                raise ScriptError("Generated Provider reference set is missing role=product.")
            forbidden = sorted(
                role for role in roles if role in {"storyboard", "storyboard_sheet", "storyboard_preview", "shot_plan"}
            )
            if forbidden and not model.get("allow_storyboard_reference_upload", True):
                raise ScriptError(
                    f"Storyboard/contact-sheet assets are review-only and cannot enter this Provider payload: {forbidden}"
                )
            invalid_provenance = [
                asset_value(ref)
                for ref in video_refs
                if ref.get("provider_upload_allowed") is not True
                or ref.get("provenance") != "generated_from_approved_visual_plan"
            ]
            if invalid_provenance:
                raise ScriptError(
                    "Every Provider reference must be generated from the approved visual plan; raw user images are forbidden. "
                    f"Invalid assets: {invalid_provenance}"
                )
            if model.get("require_local_generated_references"):
                non_local = [
                    asset_value(ref)
                    for ref in video_refs
                    if ref.get("kind") != "file" or not Path(str(asset_value(ref))).is_file()
                ]
                if non_local:
                    raise ScriptError(f"Generated Provider references must be saved local files: {non_local}")
            raw_inputs = contract.get("input_evidence_assets") or plan.get("input_evidence_assets") or []
            if contract.get("raw_inputs_provider_upload_allowed") is not False:
                raise ScriptError("Raw input evidence is not explicitly blocked from Provider upload.")
            raw_digests = {local_asset_digest(asset) for asset in raw_inputs if local_asset_digest(asset)}
            reused_raw = [
                asset_value(ref)
                for ref in video_refs
                if local_asset_digest(ref) and local_asset_digest(ref) in raw_digests
            ]
            if reused_raw:
                raise ScriptError(
                    "A Provider reference is identical to raw user evidence. Generate a professional product master or control "
                    f"from the approved plan instead: {reused_raw}"
                )
            prompt_map = shot.get("reference_prompt_map") or contract.get("reference_prompt_map") or []
            if len(prompt_map) != len(video_refs):
                raise ScriptError("Reference prompt map count does not match the generated Provider reference count.")
            prompt = str(shot.get("prompt") or "")
            invalid_token_counts = {
                str(item.get("token") or ""): prompt.count(str(item.get("token") or ""))
                for item in prompt_map
                if not item.get("token") or prompt.count(str(item.get("token") or "")) != 1
            }
            if invalid_token_counts:
                raise ScriptError(
                    "Provider prompt must contain exactly one canonical token mapping per uploaded reference: "
                    f"{invalid_token_counts}"
                )
        return
    if references and source not in {asset_value(ref) for ref in references if ref.get("role") in VIDEO_SOURCE_ROLE_PRIORITY}:
        roles = ", ".join(ref.get("role", "reference") for ref in references)
        raise ScriptError(
            "Asset mismatch for single-image video model: confirmed reference image(s) exist "
            f"[{roles}], but this model route cannot upload separate references. "
            "Use prepare_project.py --video-source-image <confirmed-final-source.png> with a composite approved image, or switch to a multi-reference model route."
        )


def build_payload(plan: dict, shot: dict, model: dict) -> dict:
    validate_provider_prompt_length(shot.get("prompt") or "", model, str(shot.get("id") or ""))
    validate_asset_consistency(plan, shot, model)
    validate_legal_request_duration(plan, shot, model)
    source_image = shot.get("image") or plan.get("product_asset")
    reference_assets = configured_video_references(plan, shot)
    input_mode = model.get("input_mode") or model.get("mode") or "image-to-video"
    supports_references = model_supports_reference_images(model)
    duration_field = model.get("duration_field", "duration")
    omit_model = bool(model.get("omit_model_from_payload")) or model_provider(model) == "fal_queue"
    payload = {
        "prompt": shot.get("prompt") or "",
        "aspect_ratio": plan.get("aspect_ratio") or model.get("default_aspect_ratio", "9:16"),
        "resolution": plan.get("resolution") or model.get("default_resolution", "720p"),
    }
    if not omit_model:
        payload["model"] = model.get("model")
    payload_defaults = model.get("payload_defaults") or {}
    if isinstance(payload_defaults, dict):
        payload.update(payload_defaults)
    payload[duration_field] = int(shot.get("duration_seconds") or model.get("default_duration_seconds", 15))
    include_source_image = input_mode in {"image-to-video", "image-to-video-with-references", "start-frame"}
    if supports_references and reference_assets:
        include_source_image = bool(model.get("include_source_image_with_references", include_source_image))
    if not reference_assets:
        include_source_image = True
    source_field = model.get("source_image_field", "image")
    reference_field = model.get("reference_field", "reference_images")
    if include_source_image:
        payload[source_field] = source_payload(source_image, model)
    if reference_assets:
        if not supports_references:
            raise ScriptError("Internal error: reference assets prepared for a model that does not support references.")
        refs = [reference_payload(ref, model) for ref in reference_assets]
        if reference_field == source_field and source_field in payload:
            existing = payload[source_field]
            if not isinstance(existing, list):
                existing = [existing]
            payload[source_field] = existing + refs
        else:
            payload[reference_field] = refs
    audio_contract = plan.get("audio_contract") or {}
    voice_ids = [str(value) for value in (audio_contract.get("preset_voice_ids") or []) if str(value).strip()]
    prompt_audio_tokens = re.findall(r"<AUDIO_\d+>", str(shot.get("prompt") or ""))
    if not voice_ids and prompt_audio_tokens:
        raise ScriptError(
            "Provider prompt contains preset AUDIO tokens but the plan sends no reference_audios. "
            "Re-prepare the plan with prompt-native voice direction before paid submission."
        )
    if voice_ids:
        if audio_contract.get("preset_voice_source") not in {"cli_user_explicit", "brief_user_explicit"}:
            raise ScriptError(
                "Preset voice references require an explicit user choice recorded by the current planner. "
                "Re-prepare legacy automatic-voice plans with prompt-native speech before paid submission."
            )
        expected_tokens = [f"<AUDIO_{index}>" for index in range(len(voice_ids))]
        if prompt_audio_tokens != expected_tokens:
            raise ScriptError(
                f"Explicit preset voices require one ordered prompt token each; expected={expected_tokens}, "
                f"actual={prompt_audio_tokens}."
            )
        approved_voices = {
            str(value)
            for value in (model.get("approved_preset_voice_ids") or model.get("known_preset_voice_ids") or [])
        }
        unsupported_voices = [voice_id for voice_id in voice_ids if approved_voices and voice_id not in approved_voices]
        if unsupported_voices:
            raise ScriptError(
                f"Preset voice_id values are not in the configured allowlist: {unsupported_voices}; stop before paid POST."
            )
        if not model.get("supports_preset_voice_references"):
            raise ScriptError("Preset voice references were approved, but the selected model route does not support them.")
        maximum_voices = int(model.get("max_reference_audios") or 0)
        if maximum_voices and len(voice_ids) > maximum_voices:
            raise ScriptError(f"Selected model accepts at most {maximum_voices} preset voice reference(s).")
        payload[model.get("reference_audio_field") or "reference_audios"] = [
            {"voice_id": voice_id} for voice_id in voice_ids
        ]
    min_references = int(model.get("min_reference_images") or 0)
    if input_mode == "reference-to-video" and len(reference_assets) < min_references:
        raise ScriptError(
            f"Reference-to-video requires at least {min_references} reference image(s); got {len(reference_assets)}."
        )
    if (
        model.get("reference_mode_exclusive_with_source")
        and source_field != reference_field
        and source_field in payload
        and reference_field in payload
    ):
        raise ScriptError(
            f"Invalid mixed video mode: {source_field!r} and {reference_field!r} are mutually exclusive."
        )
    validate_clean_provider_payload(plan, shot, payload)
    return payload


def normalize_submit_response(data: dict, shot_id: str) -> dict:
    body = data.get("data") if isinstance(data.get("data"), dict) else data
    request_id = (
        body.get("task_id")
        or body.get("request_id")
        or body.get("id")
        or data.get("task_id")
        or data.get("request_id")
        or data.get("id")
    )
    if not request_id:
        raise ScriptError(f"Submit response missing task_id/request_id for {shot_id}: {data}")
    return {
        "request_id": request_id,
        "task_id": request_id,
        "status_url": body.get("status_url") or data.get("status_url"),
        "response_url": body.get("response_url") or data.get("response_url"),
        "raw_response": data,
    }


def selected_shots(plan: dict, shot_id: str | None) -> list[dict]:
    shots = plan.get("shots") or []
    if shot_id:
        shots = [shot for shot in shots if shot.get("id") == shot_id]
        if not shots:
            raise ScriptError(f"Shot not found in plan: {shot_id}")
    return shots


def current_contract_request_records(plan: dict, model: dict) -> list[dict]:
    """Rebuild every approved request in memory before any paid Provider call."""
    records: list[dict] = []
    for shot in plan.get("shots") or []:
        payload = build_payload(plan, shot, model)
        references = configured_video_references(plan, shot)
        records.append({
            "shot_id": shot.get("id"),
            "model_key": model.get("key"),
            "provider": model.get("provider"),
            "payload": payload,
            "asset_trace": asset_trace(
                plan,
                shot,
                model,
                bool(references and model_supports_reference_images(model)),
                references,
            ),
            "dry_run": True,
            "paid_api_call": False,
        })
    return records


def resolve_confirmation(args) -> dict:
    if args.dry_run:
        return {"confirmed": False, "source": "dry_run"}
    if args.confirmation_file:
        path = Path(args.confirmation_file).expanduser().resolve()
        confirmation = load_json(path)
        image_assets_confirmed = bool(confirmation.get("image_assets_confirmed"))
        video_generation_confirmed = bool(confirmation.get("video_generation_confirmed") or confirmation.get("confirmed"))
        if not image_assets_confirmed or not video_generation_confirmed:
            raise ScriptError(
                "Refusing paid API call without final video confirmation after image asset approval. "
                "The confirmation file must include image_assets_confirmed=true and video_generation_confirmed=true."
            )
        return {
            "confirmed": True,
            "source": "confirmation_file",
            "confirmation_file": str(path),
            "image_assets_confirmed": True,
            "video_generation_confirmed": True,
            "approved_by": confirmation.get("approved_by", ""),
            "approved_at": confirmation.get("approved_at", ""),
        }
    raise ScriptError(
        "Refusing paid API call outside the guarded paid workflow. "
        "Run workflow_engine.py confirm and submit so the immutable confirmation, production contract, "
        "provider readiness check, paid cap, and one-submit ledger are all enforced."
    )


def validate_readiness_binding(path: Path, model: dict) -> dict:
    report = load_json(path)
    if report.get("ok") is not True or report.get("status") not in {"pass", "not_required"}:
        raise ScriptError("Provider readiness did not pass; refusing paid submission")
    expected = {
        "provider": model.get("provider"),
        "model_key": model.get("key"),
        "target_model": model.get("model"),
        "provider_base_url": model.get("base_url"),
    }
    mismatches = [key for key, value in expected.items() if report.get(key) != value]
    if mismatches:
        raise ScriptError(
            "Provider readiness no longer matches the selected route: " + ", ".join(mismatches)
        )
    current_route = network_route_summary()
    if report.get("network_route") != current_route:
        raise ScriptError(
            "Provider network route changed after the free readiness check; refusing paid POST. "
            "Run submit again after restoring the intended route."
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, help="generation-plan.json path")
    parser.add_argument("--config", help="Model config path")
    parser.add_argument("--model-key", help="Override model key")
    parser.add_argument("--shot-id", help="Only submit one shot")
    parser.add_argument("--dry-run", action="store_true", help="Write request payloads without calling API")
    parser.add_argument("--confirmed", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--confirmation-file", help="Immutable confirmation created by workflow_engine.py confirm")
    parser.add_argument("--readiness-file", help="Free Provider readiness report created immediately before submit")
    parser.add_argument("--max-paid-submissions", type=int, help="Guarded workflow cap supplied by workflow_engine.py submit")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout seconds")
    args = parser.parse_args()

    try:
        plan_path = Path(args.plan).expanduser().resolve()
        plan = load_json(plan_path)
        config = load_config(args.config)
        model = get_model_config(config, args.model_key or plan.get("model_key"))
        submit_url = join_url(model["base_url"], model.get("generation_path", "/v1/videos/generations"))
        if not args.dry_run and (
            not args.confirmation_file or not args.readiness_file or args.max_paid_submissions is None
        ):
            raise ScriptError(
                "Refusing paid API call outside the guarded paid workflow. "
                "Use workflow_engine.py confirm and submit; --confirmed alone cannot authorize a Provider POST."
            )
        confirmation_record = resolve_confirmation(args)
        readiness_record = None if args.dry_run else validate_readiness_binding(
            Path(args.readiness_file).expanduser().resolve(), model
        )
        api_key = None if args.dry_run else find_api_key(
            required=True,
            names=model_api_key_names(model),
            keychain_service=model_api_key_keychain_service(model),
        )
        results = []
        project_dir = plan_path.parent
        ledger = None
        paid_lock = None
        if not args.dry_run:
            confirmation = load_json(Path(args.confirmation_file).expanduser().resolve())
            contract = load_json(project_dir / "production-contract.json")
            base_count = len(plan.get("shots") or [])
            if int(args.max_paid_submissions) != base_count:
                raise ScriptError(f"max_paid_submissions must equal the {base_count} base shot(s)")
            if int(confirmation.get("approved_paid_cap") or 0) != base_count:
                raise ScriptError("Confirmation approved_paid_cap does not match the base shot count")
            if confirmation.get("contract_digest") != contract.get("contract_digest"):
                raise ScriptError("Confirmation contract digest does not match production-contract.json")
            if confirmation.get("plan_digest") != canonical_digest(plan):
                raise ScriptError("Confirmation plan digest does not match generation-plan.json")
            if confirmation.get("duration_plan_digest") != plan.get("duration_plan_digest"):
                raise ScriptError("Confirmation duration-plan digest does not match generation-plan.json")
            contract_errors = verify_contract(
                contract,
                plan,
                model,
                current_contract_request_records(plan, model),
            )
            if contract_errors:
                raise ScriptError(
                    "Refusing paid submission because the current model or request payload has drifted from preflight: "
                    + "; ".join(contract_errors)
                    + ". Run preflight again and obtain a new confirmation before any paid request."
                )
            ledger = load_or_create_jobs(
                project_dir,
                plan,
                contract_digest=str(contract.get("contract_digest") or ""),
                approved_paid_cap=base_count,
            )
            paid_lock = acquire_paid_submission_lock(project_dir)

        try:
            for shot in selected_shots(plan, args.shot_id):
                payload = build_payload(plan, shot, model)
                reference_assets = configured_video_references(plan, shot)
                references_included = bool(reference_assets and model_supports_reference_images(model))
                request_file = Path(shot["request_file"]).expanduser().resolve()
                record = {
                    "shot_id": shot["id"],
                    "model_key": model.get("key"),
                    "provider": model.get("provider"),
                    "submit_url": submit_url,
                    "payload": payload,
                    "request_evidence": request_evidence(payload, model),
                    "quality_contract": plan.get("quality_contract") or {},
                    "asset_trace": asset_trace(plan, shot, model, references_included, reference_assets),
                    "confirmation": confirmation_record,
                    "provider_readiness": readiness_record,
                    "dry_run": args.dry_run,
                    "created_at": int(time.time()),
                }
                if args.dry_run:
                    record["response"] = {"request_id": f"dry-run-{shot['id']}"}
                else:
                    if ledger is not None:
                        record_submission_attempt(project_dir, ledger, shot["id"])
                    write_json(request_file, record)
                    try:
                        record["response"] = normalize_submit_response(
                            http_json("POST", submit_url, api_key, payload, timeout=args.timeout, auth_scheme=model_auth_scheme(model)),
                            shot["id"],
                        )
                    except Exception as exc:
                        record["submission_error"] = str(exc)
                        diagnostic = provider_contract_diagnostic(exc, payload, model)
                        if diagnostic:
                            record["provider_contract_diagnostic"] = diagnostic
                        write_json(request_file, record)
                        if ledger is not None:
                            transition_job(project_dir, ledger, shot["id"], "blocked", last_error=str(exc))
                        raise
                write_json(request_file, record)
                request_id = record["response"].get("request_id")
                if ledger is not None:
                    transition_job(
                        project_dir,
                        ledger,
                        shot["id"],
                        "submitted",
                        request_id=request_id,
                        request_file=str(request_file),
                    )
                results.append({"shot_id": shot["id"], "request_file": str(request_file), "request_id": request_id, "dry_run": args.dry_run})
        finally:
            release_paid_submission_lock(paid_lock)

        print(json.dumps({"ok": True, "results": results}, ensure_ascii=False, indent=2))
        return 0
    except ScriptError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
