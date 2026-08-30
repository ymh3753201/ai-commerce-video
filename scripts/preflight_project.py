#!/usr/bin/env python3
"""Run the complete no-cost commerce readiness gate and freeze a contract."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from _common import (
    ScriptError,
    canonical_digest,
    get_model_config,
    load_config,
    load_json,
    model_supports_reference_images,
    prompt_limits,
)
from _workflow import atomic_write_json, build_contract, verify_contract
from generate_video import asset_trace, build_payload, configured_video_references
from subtitle_runtime import subtitle_runtime_errors
from validate_platform_plan import (
    model_contract_from_config,
    validate_model_and_assets,
    validate_platform_rules,
    validate_production_core,
)


ADVISORY_PLAN_ERROR_MARKERS = (
    "sound_design_contract.mode",
    "required native commercial sound plan",
    "non-speech commercial sound plan",
    "missing an audible synchronized sound cue",
    "missing the planned ambience bed",
    "requires music but disables it",
    "did not preserve the planned clip SFX",
    "did not preserve every planned sound cue",
    "did not link the time-coded sound-on-action cues",
    "sound prompt is not self-contained",
)


def plan_errors(plan: dict, model: dict) -> list[str]:
    errors: list[str] = []
    if plan.get("model_key") != model.get("key"):
        errors.append(f"Plan model_key {plan.get('model_key')} does not match selected model {model.get('key')}")
    ratios = model.get("supported_aspect_ratios") or []
    if ratios and plan.get("aspect_ratio") not in ratios:
        errors.append(f"Aspect ratio {plan.get('aspect_ratio')} is not supported by {model.get('key')}")
    resolutions = model.get("supported_resolutions") or []
    if resolutions and plan.get("resolution") not in resolutions:
        errors.append(f"Resolution {plan.get('resolution')} is not supported by {model.get('key')}")
    if not plan.get("duration_plan_digest"):
        errors.append("duration_plan_digest is missing")
    production = plan.get("production_contract") or {}
    shot_count = len(plan.get("shots") or [])
    if int(production.get("base_request_count") or 0) != shot_count:
        errors.append("production_contract.base_request_count must match the shot count")
    if int(production.get("approved_paid_cap") or 0) != shot_count:
        errors.append("production_contract.approved_paid_cap must equal the base shot count")
    if int(production.get("repair_reserve") or 0) != 0:
        errors.append("repair_reserve must be 0")
    if int(production.get("per_shot_repair_limit") or 0) != 0:
        errors.append("per_shot_repair_limit must be 0")
    for shot in plan.get("shots") or []:
        prompt = str(shot.get("prompt") or "")
        if "no newly generated written" not in prompt.lower():
            errors.append(f"{shot.get('id')} prompt is missing the clean Provider frame policy")
        boundary = shot.get("script_boundary") or {}
        script = str(shot.get("spoken_script") or "").strip()
        if script:
            if boundary.get("stitch_safe") is not True:
                errors.append(f"{shot.get('id')} does not end on a stitch-safe complete sentence")
            occurrences = prompt.count(script)
            contract_occurrences = (shot.get("prompt_contract") or {}).get("spoken_script_occurrences")
            if occurrences != 1 or contract_occurrences != 1:
                errors.append(
                    f"{shot.get('id')} spoken script must appear exactly once in the Provider prompt; "
                    f"actual={occurrences}, prompt_contract={contract_occurrences}"
                )
        if int(plan.get("plan_schema_version") or 1) >= 2:
            counts = {
                "AUDIO": len(re.findall(r"\bAUDIO\s*:", prompt, flags=re.IGNORECASE)),
                "Cuts": len(re.findall(r"\bCuts\s*:", prompt, flags=re.IGNORECASE)),
                "Sequence": len(re.findall(r"\bSequence\s*:", prompt, flags=re.IGNORECASE)),
                "Reference image map": len(re.findall(r"\bReference image map\s*:", prompt, flags=re.IGNORECASE)),
            }
            expected_reference_maps = 1 if configured_video_references(plan, shot) else 0
            if counts["AUDIO"] != 1:
                errors.append(f"{shot.get('id')} must contain exactly one AUDIO block; actual={counts['AUDIO']}")
            if counts["Cuts"] + counts["Sequence"] != 1:
                errors.append(
                    f"{shot.get('id')} must contain exactly one director timeline block; "
                    f"Cuts={counts['Cuts']}, Sequence={counts['Sequence']}"
                )
            if counts["Reference image map"] != expected_reference_maps:
                errors.append(
                    f"{shot.get('id')} reference map count must be {expected_reference_maps}; actual={counts['Reference image map']}"
                )
            if re.search(r",\s*,", prompt):
                errors.append(f"{shot.get('id')} contains an empty comma-delimited instruction")
    audio = plan.get("audio_contract") or {}
    voices = [str(value) for value in (audio.get("preset_voice_ids") or []) if str(value).strip()]
    prompt_audio_tokens = [
        token
        for shot in plan.get("shots") or []
        for token in re.findall(r"<AUDIO_\d+>", str(shot.get("prompt") or ""))
    ]
    if voices:
        if audio.get("preset_voice_source") not in {"cli_user_explicit", "brief_user_explicit"}:
            errors.append(
                "Preset voice references require an explicit user choice recorded by the current planner; "
                "re-prepare legacy automatic-voice plans with prompt-native speech"
            )
        expected_tokens = [f"<AUDIO_{index}>" for index in range(len(voices))] * len(plan.get("shots") or [])
        if prompt_audio_tokens != expected_tokens:
            errors.append(
                f"Explicit preset voices require ordered AUDIO tokens; expected={expected_tokens}, actual={prompt_audio_tokens}"
            )
        approved = {
            str(value)
            for value in (model.get("approved_preset_voice_ids") or model.get("known_preset_voice_ids") or [])
        }
        unsupported = [voice_id for voice_id in voices if approved and voice_id not in approved]
        if unsupported:
            errors.append(f"Preset voice_id values are not in the configured approved voice allowlist: {unsupported}")
    elif prompt_audio_tokens:
        errors.append(
            "Prompt-native speech must not contain <AUDIO_n> tokens when reference_audios is absent; re-prepare the plan"
        )
    speaker_mode = str((plan.get("creative_contract") or {}).get("speaker_mode") or audio.get("speech_mode") or "")
    creative = plan.get("creative_contract") or {}
    expected_presentations = {
        "digital-human-spoken": "on_camera_presenter",
        "voiceover": "off_screen_voiceover",
        "no-speech": "none",
        "silent-captions": "none",
    }
    if speaker_mode not in expected_presentations:
        errors.append(f"Unsupported speaker_mode in the frozen plan: {speaker_mode!r}")
    else:
        if audio.get("speech_mode") and audio.get("speech_mode") != speaker_mode:
            errors.append("creative_contract.speaker_mode and audio_contract.speech_mode drifted apart")
        for owner, contract in (("creative_contract", creative), ("audio_contract", audio)):
            presentation = str(contract.get("speech_presentation") or "")
            if presentation and presentation != expected_presentations[speaker_mode]:
                errors.append(
                    f"{owner}.speech_presentation conflicts with speaker_mode={speaker_mode}"
                )
        speech_required = bool(audio.get("speech_required"))
        if speaker_mode in {"digital-human-spoken", "voiceover"} and not speech_required:
            errors.append(f"speaker_mode={speaker_mode} requires approved speech")
        if speaker_mode in {"no-speech", "silent-captions"} and speech_required:
            errors.append(f"speaker_mode={speaker_mode} forbids human speech")
    if audio.get("speech_required"):
        for shot in plan.get("shots") or []:
            prompt = str(shot.get("prompt") or "")
            normalized = prompt.casefold()
            if speaker_mode == "digital-human-spoken":
                if not all(marker in normalized for marker in ("dialogue=“", "visibly speaks", "natural mouth movement")):
                    errors.append(
                        f"{shot.get('id')} on-camera speech prompt must contain Dialogue=, visible speaking, and natural mouth movement"
                    )
                if any(value in normalized for value in ("off-screen voiceover", "demonstrates silently", "vo=“")):
                    errors.append(f"{shot.get('id')} on-camera speech prompt contains voiceover/silent contradictions")
            elif speaker_mode == "voiceover":
                if "vo=“" not in normalized or "off-screen voiceover" not in normalized:
                    errors.append(f"{shot.get('id')} voiceover prompt must use VO= and explicit off-screen narration")
                if any(value in normalized for value in ("dialogue=“", "visibly speaks", "speaks to camera")):
                    errors.append(f"{shot.get('id')} voiceover prompt contains on-camera speaking contradictions")
    elif speaker_mode in {"no-speech", "silent-captions"}:
        for shot in plan.get("shots") or []:
            prompt = str(shot.get("prompt") or "")
            normalized = prompt.casefold()
            if not all(
                marker in normalized
                for marker in ("speech=none", "voice=none", "no spoken dialogue, narration, or voiceover")
            ):
                errors.append(f"{shot.get('id')} no-speech prompt does not explicitly forbid human voice")
            if any(
                value in normalized
                for value in ("dialogue=“", "vo=“", "visibly speaks", "speaks to camera", "off-screen voiceover.")
            ):
                errors.append(f"{shot.get('id')} no-speech prompt contains spoken-voice contradictions")
    sound = plan.get("sound_design_contract") or {}
    if sound:
        mode = str(sound.get("mode") or "")
        if mode not in {"layered_native", "ambience_led", "voice_only", "silent"}:
            errors.append("sound_design_contract.mode must be layered_native, ambience_led, voice_only, or silent")
        non_speech_required = bool(sound.get("non_speech_required"))
        required_layers = sound.get("required_layers") or {}
        if speaker_mode == "no-speech" and mode == "voice_only":
            errors.append("A no-speech plan cannot use voice_only sound design")
        if speaker_mode == "silent-captions" and (mode != "silent" or non_speech_required):
            errors.append("A silent-captions plan must preserve a fully silent sound contract")
        if non_speech_required and not sound.get("native_provider_sound"):
            errors.append("The selected route does not support the required native commercial sound plan")
        if non_speech_required and not (required_layers.get("sfx") or required_layers.get("ambience")):
            errors.append("A non-speech commercial sound plan must require SFX or ambience")
        for shot in plan.get("shots") or []:
            prompt = str(shot.get("prompt") or "")
            if non_speech_required:
                if required_layers.get("sfx") and (
                    "Cues=" not in prompt or re.search(r"\bCues\s*=\s*(?:none|off|silent)\b", prompt, flags=re.IGNORECASE)
                ):
                    errors.append(f"{shot.get('id')} prompt is missing an audible synchronized sound cue")
                if required_layers.get("ambience") and (
                    "Ambience=" not in prompt or re.search(r"\bAmbience\s*=\s*(?:none|off|silent)\b", prompt, flags=re.IGNORECASE)
                ):
                    errors.append(f"{shot.get('id')} prompt is missing the planned ambience bed")
                if required_layers.get("music") and "Music=no music" in prompt:
                    errors.append(f"{shot.get('id')} requires music but disables it in the Provider prompt")
                prompt_contract = shot.get("prompt_contract") or {}
                if prompt_contract.get("compiler") in {"director-commerce-v8", "director-commerce-v9", "director-commerce-v10"}:
                    coverage = prompt_contract.get("sound_cue_coverage") or {}
                    if coverage.get("clip_sfx_rendered") is not True:
                        errors.append(f"{shot.get('id')} Provider prompt did not preserve the planned clip SFX")
                    if coverage.get("all_beat_cues_rendered_in_timeline") is not True:
                        errors.append(f"{shot.get('id')} Provider timeline did not preserve every planned sound cue")
                    if coverage.get("audio_block_links_timecoded_cues") is not True:
                        errors.append(f"{shot.get('id')} AUDIO block did not link the time-coded sound-on-action cues")
                    if coverage.get("self_contained") is not True:
                        errors.append(
                            f"{shot.get('id')} sound prompt is not self-contained for an independent Provider request"
                        )
    talent = (plan.get("creative_contract") or {}).get("talent_contract") or {}
    presence = str(talent.get("presence") or "")
    combined_prompt = "\n".join(str(shot.get("prompt") or "") for shot in plan.get("shots") or [])
    reference_roles = {
        str(item.get("role") or "").lower()
        for item in ((plan.get("asset_contract") or {}).get("video_reference_assets") or plan.get("video_references") or [])
    }
    if int(plan.get("plan_schema_version") or 1) >= 2 and presence not in {"none", "hands_only", "presenter"}:
        errors.append("plan schema v2+ requires talent_contract.presence=none, hands_only, or presenter")
    if "visible people demonstrate silently" in combined_prompt.lower():
        errors.append("Provider prompt contains the ambiguous legacy instruction 'visible people demonstrate silently'; re-prepare the plan")
    if presence == "none":
        if "No person, face, body, hand, or human silhouette appears" not in combined_prompt:
            errors.append("talent_presence=none requires an explicit no-human render instruction")
        if reference_roles.intersection({"presenter", "wardrobe", "hand_action"}):
            errors.append("talent_presence=none conflicts with human Provider references")
    elif presence == "presenter" and "presenter" not in reference_roles:
        errors.append("A visible presenter requires one generated presenter Provider reference before Stage 2")
    voice_gender = str(audio.get("voice_gender") or "unspecified")
    voice_description = str(audio.get("voice_description") or "")
    if voice_gender == "female" and not re.search(r"\bfemale\b|女性|女声|女生", voice_description, flags=re.IGNORECASE):
        errors.append("voice_gender=female is not preserved in voice_description")
    if voice_gender == "male" and not re.search(r"\bmale\b|男性|男声|男生", voice_description, flags=re.IGNORECASE):
        errors.append("voice_gender=male is not preserved in voice_description")
    return errors


def platform_errors(plan: dict, config_path: str | None, model_key: str | None) -> list[str]:
    return [
        str(item.get("evidence") or item.get("text"))
        for item in platform_findings(plan, config_path, model_key)
        if item.get("severity") == "error" and not item.get("passed")
    ]


def platform_findings(plan: dict, config_path: str | None, model_key: str | None) -> list[dict]:
    checks: list[dict] = []
    validate_platform_rules(plan, checks)
    contract = model_contract_from_config(plan, config_path, model_key)
    validate_model_and_assets(plan, checks, contract)
    validate_production_core(plan, checks, contract)
    return [item for item in checks if not item.get("passed")]


def build_dry_run_records(plan: dict, model: dict) -> tuple[list[dict], list[str]]:
    records: list[dict] = []
    errors: list[str] = []
    for shot in plan.get("shots") or []:
        try:
            payload = build_payload(plan, shot, model)
            references = configured_video_references(plan, shot)
            trace = asset_trace(plan, shot, model, bool(references and model_supports_reference_images(model)), references)
            records.append({
                "shot_id": shot.get("id"),
                "model_key": model.get("key"),
                "provider": model.get("provider"),
                "payload": payload,
                "asset_trace": trace,
                "dry_run": True,
                "paid_api_call": False,
                "created_at": int(time.time()),
            })
        except ScriptError as exc:
            errors.append(str(exc))
    return records, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--config")
    parser.add_argument("--model-key")
    args = parser.parse_args()
    try:
        plan_path = Path(args.plan).expanduser().resolve()
        project_dir = plan_path.parent
        plan = load_json(plan_path)
        config = load_config(args.config)
        model = get_model_config(config, args.model_key or plan.get("model_key"))
        subtitle_postproduction_warnings = subtitle_runtime_errors(plan)
        prompt_budget_chars, max_prompt_chars = prompt_limits(model)
        prompt_summary = []
        for shot in plan.get("shots") or []:
            prompt = str(shot.get("prompt") or "")
            prompt_contract = shot.get("prompt_contract") or {}
            prompt_summary.append({
                "shot_id": shot.get("id"),
                "char_count": len(prompt),
                "utf8_bytes": len(prompt.encode("utf-8")),
                "prompt_budget_chars": prompt_budget_chars,
                "max_prompt_chars": max_prompt_chars,
                "within_budget": prompt_budget_chars is None or len(prompt) <= prompt_budget_chars,
                "within_max": max_prompt_chars is None or len(prompt) <= max_prompt_chars,
                "compiler": prompt_contract.get("compiler") or "",
                "spoken_script_occurrences": prompt.count(str(shot.get("spoken_script") or "").strip())
                if str(shot.get("spoken_script") or "").strip()
                else 0,
            })
        raw_plan_errors = plan_errors(plan, model)
        warnings = [
            item for item in raw_plan_errors
            if any(marker.lower() in item.lower() for marker in ADVISORY_PLAN_ERROR_MARKERS)
        ]
        errors = [item for item in raw_plan_errors if item not in warnings]
        platform_checks = platform_findings(plan, args.config, args.model_key)
        errors.extend(
            str(item.get("evidence") or item.get("text"))
            for item in platform_checks
            if item.get("severity") == "error"
        )
        warnings.extend(
            str(item.get("evidence") or item.get("text"))
            for item in platform_checks
            if item.get("severity") == "warning"
        )
        records: list[dict] = []
        if not errors:
            records, request_errors = build_dry_run_records(plan, model)
            errors.extend(request_errors)
        if not errors and len(records) != len(plan.get("shots") or []):
            errors.append("Dry-run request count does not match shot count")

        contract_file = project_dir / "production-contract.json"
        snapshot_file = project_dir / "model-snapshot.json"
        reused = False
        contract = None
        if not errors:
            contract = build_contract(plan, model, records)
            for item in contract.get("asset_fingerprints") or []:
                if item.get("status") != "local" and item.get("status") != "data_uri":
                    errors.append(
                        f"Production asset is not locally content-bound: role={item.get('role')} status={item.get('status')}"
                    )
            if contract_file.exists() and not errors:
                existing = load_json(contract_file)
                if existing.get("contract_digest") != contract.get("contract_digest"):
                    errors.append("Existing production contract does not match the current plan/model/assets")
                else:
                    existing_records = []
                    for shot in plan.get("shots") or []:
                        path = project_dir / "requests" / "dry-run" / f"{shot.get('id')}.json"
                        if not path.exists():
                            errors.append(f"Immutable dry-run request is missing: {path}")
                        else:
                            existing_records.append(load_json(path))
                    if not errors:
                        errors.extend(verify_contract(existing, plan, model, existing_records))
                    if not errors:
                        contract = existing
                        records = existing_records
                        reused = True
            if not errors and not reused:
                for record in records:
                    atomic_write_json(project_dir / "requests" / "dry-run" / f"{record['shot_id']}.json", record)
                atomic_write_json(contract_file, contract)
                atomic_write_json(snapshot_file, contract["model_snapshot"])

        report = {
            "ok": not errors,
            "paid_api_call": False,
            "plan": str(plan_path),
            "plan_digest": canonical_digest(plan),
            "project_dir": str(project_dir),
            "model_key": model.get("key"),
            "errors": errors,
            "warnings": warnings,
            "warning_count": len(warnings),
            "prompt_summary": prompt_summary,
            "dry_run_request_count": len(records),
            "expected_paid_requests": len(plan.get("shots") or []),
            "paid_generation_allowed": not errors,
            "subtitle_postproduction_deferred": bool((plan.get("subtitle_plan") or {}).get("enabled")),
            "subtitle_postproduction_warnings": subtitle_postproduction_warnings,
            "contract_reused": reused,
            "contract_file": str(contract_file) if not errors else "",
            "model_snapshot_file": str(snapshot_file) if not errors else "",
        }
        atomic_write_json(project_dir / "preflight-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if not errors else 1
    except (ScriptError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "paid_api_call": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
