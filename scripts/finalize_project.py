#!/usr/bin/env python3
"""Create a commerce delivery manifest only after every production gate passes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _common import ScriptError, canonical_digest, load_json, media_summary, sha256_file, write_json
from _workflow import (
    delivery_review_policy,
    voice_contract_review_required,
    voice_review_errors,
    voice_review_path,
)
from subtitle_policy import enabled_subtitle_contract_errors


CLEAN_VISUAL_FIELDS = {
    "video_complete_and_coherent": "The complete video and its joins were not verified as coherent",
    "source_frame_consistency": "Overall consistency with the approved reference frames was not verified",
    "approved_product_identity": "Approved product identity was not verified",
    "presenter_identity_consistency": "Presenter identity consistency with the approved reference was not verified",
    "presenter_outfit_consistency": "Presenter outfit consistency with the approved reference was not verified",
    "scene_composition_consistency": "Scene and composition consistency with the approved reference was not verified",
    "speech_intelligible": "Speech intelligibility was not verified",
    "speech_meaning_preserved": "The approved selling meaning was not approximately preserved",
}
TALENT_VISUAL_FIELDS = {
    "unexpected_person_absent": "A person, face, body, hand, or human silhouette appeared against the approved product-only plan",
    "hands_only_boundary_preserved": "The approved hands-only boundary was not preserved",
    "unexpected_presenter_absent": "A presenter appeared in an approved hands-only plan",
    "talent_presence_matches_plan": "Visible talent presence does not match the approved plan",
    "talent_gender_matches_plan": "Visible presenter gender does not match the explicitly approved plan",
    "voice_gender_matches_plan": "Generated voice gender does not match the explicitly approved voice direction",
}
SOUND_VISUAL_FIELDS = {
    "planned_sfx_audible": "The planned commercial sound effects were not verified as audible",
    "planned_ambience_audible": "The planned scene ambience was not verified as audible",
    "planned_music_audible": "The planned original background music was not verified as audible",
    "non_speech_sound_supports_story": "The required non-speech sound design was not verified as supporting the commercial story",
    "audio_mix_balanced": "The audio mix of voice, sound effects, ambience, and music was not verified as balanced",
}
CAPTION_VISUAL_FIELDS = {
    "subtitle_present": "Captioned delivery does not verify subtitle presence",
    "subtitle_postproduced": "Caption origin is not verified as local postproduction",
    "subtitle_safe": "Caption safe-zone placement was not verified",
    "subtitle_readable": "Caption readability was not verified",
    "subtitle_matches_speech": "Captions were not verified against final speech",
    "no_unapproved_text": "Captioned delivery contains or may contain unapproved text",
}


def _job_items(jobs: dict) -> list[dict]:
    value = jobs.get("jobs") or []
    if isinstance(value, dict):
        return list(value.values())
    return list(value)


def delivery_errors(
    plan: dict,
    jobs: dict,
    technical_review: dict,
    clean_visual_review: dict | None,
    caption_review: dict | None,
    voice_review: dict | None = None,
) -> list[str]:
    errors: list[str] = []
    clean_visual_review = clean_visual_review or {}
    strict_business_review = delivery_review_policy(plan) == "strict_business_review"
    shots = plan.get("shots") or []
    production = plan.get("production_contract") or {}
    base_count = int(production.get("base_request_count") or len(shots))
    paid_cap = int(production.get("approved_paid_cap") or 0)
    if base_count != len(shots):
        errors.append(f"Base request count {base_count} does not match shot count {len(shots)}")
    if paid_cap != base_count:
        errors.append(f"Approved paid cap {paid_cap} must equal base request count {base_count}")
    if int(production.get("repair_reserve") or 0) != 0:
        errors.append("repair_reserve must remain 0")
    if int(production.get("per_shot_repair_limit") or 0) != 0:
        errors.append("per_shot_repair_limit must remain 0")

    job_items = _job_items(jobs)
    if len(job_items) != len(shots):
        errors.append(f"Verified job count {len(job_items)} does not match shot count {len(shots)}")
    attempts = sum(int(item.get("submission_attempts") or 0) for item in job_items)
    if attempts > paid_cap:
        errors.append(f"Paid submission attempts {attempts} exceed approved cap {paid_cap}")
    for item in job_items:
        shot_id = item.get("shot_id") or "unknown"
        if item.get("state") != "verified":
            errors.append(f"Job {shot_id} is not verified: state={item.get('state')}")
        if int(item.get("submission_attempts") or 0) != 1:
            errors.append(f"Job {shot_id} must have exactly one paid submission attempt")

    if technical_review.get("status") != "pass":
        errors.append("Technical review status is not pass")
    if technical_review.get("delivery_duration_hard_limit_pass") is not True:
        errors.append("Final delivery exceeds or does not verify the hard duration limit")
    if int(plan.get("plan_schema_version") or 1) >= 2 and technical_review.get("provider_duration_shortfall_pass") is not True:
        errors.append("Provider clip duration is too short; long static padding cannot be used to claim a complete ad")

    if strict_business_review and clean_visual_review.get("status") not in {"pass", "pass_with_notes"}:
        errors.append("Clean visual review status is not pass/pass_with_notes")
    speech_required = bool((plan.get("audio_contract") or {}).get("speech_required"))
    schema_v2 = int(plan.get("plan_schema_version") or 1) >= 2
    talent = ((plan.get("creative_contract") or {}).get("talent_contract") or {})
    talent_presence = str(talent.get("presence") or "none")
    required_visual_fields = dict(CLEAN_VISUAL_FIELDS)
    if schema_v2:
        required_visual_fields.pop("presenter_identity_consistency", None)
        required_visual_fields.pop("presenter_outfit_consistency", None)
        if talent_presence == "none":
            required_visual_fields["unexpected_person_absent"] = TALENT_VISUAL_FIELDS["unexpected_person_absent"]
        elif talent_presence == "hands_only":
            required_visual_fields["hands_only_boundary_preserved"] = TALENT_VISUAL_FIELDS["hands_only_boundary_preserved"]
            required_visual_fields["unexpected_presenter_absent"] = TALENT_VISUAL_FIELDS["unexpected_presenter_absent"]
        elif talent_presence == "presenter":
            required_visual_fields["presenter_identity_consistency"] = CLEAN_VISUAL_FIELDS["presenter_identity_consistency"]
            required_visual_fields["presenter_outfit_consistency"] = CLEAN_VISUAL_FIELDS["presenter_outfit_consistency"]
            required_visual_fields["talent_presence_matches_plan"] = TALENT_VISUAL_FIELDS["talent_presence_matches_plan"]
            if talent.get("gender") in {"female", "male"}:
                required_visual_fields["talent_gender_matches_plan"] = TALENT_VISUAL_FIELDS["talent_gender_matches_plan"]
        audio = plan.get("audio_contract") or {}
        if speech_required and audio.get("voice_gender") in {"female", "male"}:
            required_visual_fields["voice_gender_matches_plan"] = TALENT_VISUAL_FIELDS["voice_gender_matches_plan"]
        sound = plan.get("sound_design_contract") or {}
        if sound.get("verification_required") and sound.get("non_speech_required"):
            required_layers = sound.get("required_layers") or {}
            if required_layers.get("sfx"):
                required_visual_fields["planned_sfx_audible"] = SOUND_VISUAL_FIELDS["planned_sfx_audible"]
            if required_layers.get("ambience"):
                required_visual_fields["planned_ambience_audible"] = SOUND_VISUAL_FIELDS["planned_ambience_audible"]
            if required_layers.get("music"):
                required_visual_fields["planned_music_audible"] = SOUND_VISUAL_FIELDS["planned_music_audible"]
            required_visual_fields["non_speech_sound_supports_story"] = SOUND_VISUAL_FIELDS["non_speech_sound_supports_story"]
            required_visual_fields["audio_mix_balanced"] = SOUND_VISUAL_FIELDS["audio_mix_balanced"]
    if strict_business_review:
        for field, message in required_visual_fields.items():
            if field in {"speech_intelligible", "speech_meaning_preserved"} and int(plan.get("plan_schema_version") or 1) >= 2 and not speech_required:
                continue
            if clean_visual_review.get(field) is not True:
                errors.append(message)
    if strict_business_review and speech_required and (
        clean_visual_review.get("speech_intelligible") is not True
        or clean_visual_review.get("speech_meaning_preserved") is not True
    ):
        errors.append("Planned speech is missing, unintelligible, or does not preserve the approved selling meaning; visual review must be blocked")
    if voice_contract_review_required(plan):
        errors.extend(voice_review_errors(plan, voice_review))
    sound = plan.get("sound_design_contract") or {}
    if strict_business_review and sound.get("verification_required") and sound.get("non_speech_required"):
        sound_fields = [
            field
            for field in ("planned_sfx_audible", "planned_ambience_audible", "planned_music_audible")
            if (sound.get("required_layers") or {}).get(field.removeprefix("planned_").removesuffix("_audible"))
        ]
        sound_fields.extend(["non_speech_sound_supports_story", "audio_mix_balanced"])
        if any(clean_visual_review.get(field) is not True for field in sound_fields):
            errors.append(
                "Planned commercial sound design is missing or unbalanced; visual review must be blocked and no automatic paid retry is allowed"
            )

    subtitle_plan = plan.get("subtitle_plan") or {}
    if subtitle_plan.get("enabled"):
        errors.extend(enabled_subtitle_contract_errors(subtitle_plan, prefix="Final delivery subtitles"))
        if not isinstance(caption_review, dict):
            errors.append("Caption review is required for an enabled subtitle delivery")
        else:
            if caption_review.get("status") not in {"pass", "pass_with_notes"}:
                errors.append("Caption review status is not pass/pass_with_notes")
            for field, message in CAPTION_VISUAL_FIELDS.items():
                if caption_review.get(field) is not True:
                    errors.append(message)
    return errors


def delivery_warnings(plan: dict, clean_visual_review: dict | None) -> list[str]:
    """Keep optional creative observations visible without blocking a technically valid delivery."""
    if delivery_review_policy(plan) == "strict_business_review":
        return []
    review = clean_visual_review or {}
    if not review:
        return ["Optional post-generation visual and listening review was not recorded"]
    warnings = []
    if review.get("status") not in {"pass", "pass_with_notes"}:
        warnings.append("Optional post-generation business review did not pass")
    for field in planned_optional_review_fields(plan):
        if review.get(field) is not True:
            warnings.append(f"Optional review finding not confirmed: {field}")
    return warnings


def planned_optional_review_fields(plan: dict) -> list[str]:
    fields = list(CLEAN_VISUAL_FIELDS)
    if not bool((plan.get("audio_contract") or {}).get("speech_required")) or voice_contract_review_required(plan):
        fields = [field for field in fields if field not in {"speech_intelligible", "speech_meaning_preserved"}]
    sound = plan.get("sound_design_contract") or {}
    if sound.get("non_speech_required"):
        fields.extend(SOUND_VISUAL_FIELDS)
    return fields


def review_binding_errors(
    subtitles_enabled: bool,
    clean_video_sha256: str,
    final_video_sha256: str,
    technical_review: dict,
    clean_visual_review: dict,
    caption_review: dict | None,
    require_visual_review: bool = True,
    voice_review: dict | None = None,
    require_voice_review: bool = False,
) -> list[str]:
    errors: list[str] = []
    if not clean_video_sha256:
        errors.append("Clean video hash is missing")
    if technical_review.get("video_sha256") != clean_video_sha256:
        errors.append("Technical review video hash does not match the clean video")
    if require_visual_review and clean_visual_review.get("video_sha256") != clean_video_sha256:
        errors.append("Clean visual review video hash does not match the clean video")
    if require_voice_review and (voice_review or {}).get("video_sha256") != clean_video_sha256:
        errors.append("Voice contract review video hash does not match the clean video")
    if subtitles_enabled:
        if not isinstance(caption_review, dict) or caption_review.get("video_sha256") != final_video_sha256:
            errors.append("Caption review video hash does not match the captioned delivery")
    elif final_video_sha256 != clean_video_sha256:
        errors.append("Clean delivery hash does not match the reviewed clean video hash")
    return errors


def contract_binding_errors(plan: dict, jobs: dict, contract: dict, confirmation: dict) -> list[str]:
    errors: list[str] = []
    contract_digest = str(contract.get("contract_digest") or "")
    current_plan_digest = canonical_digest(plan)
    duration_digest = str(plan.get("duration_plan_digest") or "")
    paid_cap = int((plan.get("production_contract") or {}).get("approved_paid_cap") or 0)
    if not contract_digest:
        errors.append("Production contract digest is missing")
    if contract.get("plan_digest") != current_plan_digest:
        errors.append("Generation plan hash no longer matches the frozen production contract")
    if str(contract.get("duration_plan_digest") or "") != duration_digest:
        errors.append("Duration plan hash no longer matches the frozen production contract")
    if confirmation.get("contract_digest") != contract_digest:
        errors.append("Video confirmation is not bound to the frozen production contract")
    if confirmation.get("plan_digest") != current_plan_digest:
        errors.append("Video confirmation plan hash does not match the current generation plan")
    if str(confirmation.get("duration_plan_digest") or "") != duration_digest:
        errors.append("Video confirmation duration hash does not match the current generation plan")
    if jobs.get("contract_digest") != contract_digest:
        errors.append("Paid job ledger is not bound to the frozen production contract")
    if int(contract.get("approved_paid_cap") or 0) != paid_cap:
        errors.append("Production contract paid cap does not match the generation plan")
    if int(confirmation.get("approved_paid_cap") or 0) != paid_cap:
        errors.append("Video confirmation paid cap does not match the generation plan")
    return errors


def artifact_entry(path: Path) -> dict:
    if not path.is_file():
        return {"path": str(path), "exists": False, "sha256": ""}
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "media": media_summary(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--video", help="Override final delivery MP4")
    args = parser.parse_args()
    project_dir = Path(args.project_dir).expanduser().resolve()
    try:
        plan = load_json(project_dir / "generation-plan.json")
        jobs = load_json(project_dir / "jobs.json")
        contract = load_json(project_dir / "production-contract.json")
        confirmation = load_json(project_dir / "video-confirmation.json")
        subtitles_enabled = bool((plan.get("subtitle_plan") or {}).get("enabled"))
        require_visual_review = delivery_review_policy(plan) == "strict_business_review"
        technical_path = project_dir / ("final-review.clean.json" if subtitles_enabled else "final-review.json")
        clean_visual_path = project_dir / ("visual-review.clean.json" if subtitles_enabled else "visual-review.json")
        required_voice_path = voice_review_path(project_dir, plan)
        caption_path = project_dir / "visual-review.json"
        technical = load_json(technical_path)
        clean_visual = load_json(clean_visual_path) if clean_visual_path.exists() else {}
        voice_review = load_json(required_voice_path) if required_voice_path.exists() else {}
        caption = load_json(caption_path) if subtitles_enabled and caption_path.exists() else None
        if args.video:
            final_path = Path(args.video).expanduser().resolve()
        elif subtitles_enabled:
            final_path = project_dir / "final.captioned.mp4"
        else:
            final_path = project_dir / "final.mp4"
        artifact = artifact_entry(final_path)
        clean_path = project_dir / "final.mp4" if subtitles_enabled else final_path
        clean_artifact = artifact_entry(clean_path)
        errors = delivery_errors(plan, jobs, technical, clean_visual, caption, voice_review)
        warnings = delivery_warnings(plan, clean_visual)
        errors.extend(contract_binding_errors(plan, jobs, contract, confirmation))
        if not artifact.get("exists"):
            errors.append(f"Final delivery MP4 does not exist: {final_path}")
        if not clean_artifact.get("exists"):
            errors.append(f"Clean reviewed MP4 does not exist: {clean_path}")
        errors.extend(
            review_binding_errors(
                subtitles_enabled,
                str(clean_artifact.get("sha256") or ""),
                str(artifact.get("sha256") or ""),
                technical,
                clean_visual,
                caption,
                require_visual_review=require_visual_review,
                voice_review=voice_review,
                require_voice_review=voice_contract_review_required(plan),
            )
        )
        report = {
            "status": "blocked" if errors else "pass",
            "project_dir": str(project_dir),
            "errors": errors,
            "warnings": warnings,
            "delivery_review_policy": delivery_review_policy(plan),
            "final_artifact": artifact,
            "clean_artifact": clean_artifact,
            "technical_review": str(technical_path),
            "clean_visual_review": str(clean_visual_path) if clean_visual_path.exists() else "",
            "voice_review": str(required_voice_path) if required_voice_path.exists() else "",
            "caption_review": str(caption_path) if subtitles_enabled else "",
            "paid_submission_attempts": sum(int(item.get("submission_attempts") or 0) for item in _job_items(jobs)),
            "approved_paid_cap": int((plan.get("production_contract") or {}).get("approved_paid_cap") or 0),
        }
        write_json(project_dir / "finalize-report.json", report)
        if errors:
            print(json.dumps({"ok": False, **report}, ensure_ascii=False, indent=2))
            return 1
        delivery = {
            **report,
            "status": "pass",
            "delivery_type": "captioned" if subtitles_enabled else "clean",
            "no_additional_paid_repairs": True,
        }
        write_json(project_dir / "delivery-manifest.json", delivery)
        print(json.dumps({"ok": True, **delivery}, ensure_ascii=False, indent=2))
        return 0
    except (ScriptError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"ok": False, "status": "blocked", "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
