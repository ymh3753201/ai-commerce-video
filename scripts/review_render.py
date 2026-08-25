#!/usr/bin/env python3
"""Review a rendered commerce MP4 and its multi-clip boundaries without spending API credits."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from _common import ScriptError, asset_value, is_url, load_json, require_ffmpeg, sha256_file, verify_media_file, write_json


QC_FAILURE_CODES = {
    "QC_PRODUCT_DRIFT": "repair the product anchor or only the affected clip",
    "QC_CAMERA_MOVE_CONFLICT": "rewrite and regenerate only the affected clip",
    "QC_REFERENCE_CONTAMINATION": "replace the contaminated support plate and affected clip",
    "QC_SPEECH_OVERRUN": "shorten or retime only that clip's script and AUDIO block",
    "QC_HAND_ANATOMY": "replace the hand-action plate and affected clip",
    "QC_CTA_UNREADABLE": "redo local CTA packaging only",
    "QC_DURATION_SHORTFALL": "block delivery; do not disguise a missing commercial beat with a long static hold",
    "QC_SPEECH_MISSING": "block delivery when planned speech is missing or unintelligible",
    "QC_TALENT_MISMATCH": "block delivery when a person appears against plan or presenter identity/gender changes",
    "QC_VOICE_GENDER_MISMATCH": "block delivery when an explicitly approved female or male voice direction is not preserved",
    "QC_SOUND_DESIGN_MISSING": "block delivery when planned non-speech sound effects, ambience, or music are absent",
    "QC_AUDIO_MIX_FAILURE": "block delivery when voice masks the planned soundscape or the soundscape masks speech",
}


def planned_visual_review_fields(plan: dict) -> list[str]:
    fields = [
        "video_complete_and_coherent",
        "approved_product_identity",
        "source_frame_consistency",
        "scene_composition_consistency",
    ]
    if int(plan.get("plan_schema_version") or 1) < 2:
        return fields + [
            "presenter_identity_consistency",
            "presenter_outfit_consistency",
            "speech_intelligible",
            "speech_meaning_preserved",
        ]
    talent = ((plan.get("creative_contract") or {}).get("talent_contract") or {})
    presence = str(talent.get("presence") or "none")
    if presence == "none":
        fields.append("unexpected_person_absent")
    elif presence == "hands_only":
        fields.extend(["hands_only_boundary_preserved", "unexpected_presenter_absent"])
    elif presence == "presenter":
        fields.extend([
            "presenter_identity_consistency",
            "presenter_outfit_consistency",
            "talent_presence_matches_plan",
        ])
        if talent.get("gender") in {"female", "male"}:
            fields.append("talent_gender_matches_plan")
    audio = plan.get("audio_contract") or {}
    if audio.get("speech_required"):
        fields.extend(["speech_intelligible", "speech_meaning_preserved"])
        if audio.get("voice_gender") in {"female", "male"}:
            fields.append("voice_gender_matches_plan")
    sound = plan.get("sound_design_contract") or {}
    if sound.get("verification_required") and sound.get("non_speech_required"):
        required_layers = sound.get("required_layers") or {}
        if required_layers.get("sfx"):
            fields.append("planned_sfx_audible")
        if required_layers.get("ambience"):
            fields.append("planned_ambience_audible")
        if required_layers.get("music"):
            fields.append("planned_music_audible")
        fields.extend(["non_speech_sound_supports_story", "audio_mix_balanced"])
    return fields


def run_ffmpeg(cmd: list[str]) -> str:
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0:
        raise ScriptError(f"FFmpeg review command failed: {' '.join(cmd)}\n{output[-1200:]}")
    return output


def detect_silence(path: Path, threshold_db: float = -35.0, min_duration: float = 0.4) -> list[dict]:
    output = run_ffmpeg([
        "ffmpeg", "-hide_banner", "-i", str(path),
        "-af", f"silencedetect=noise={threshold_db}dB:d={min_duration}",
        "-f", "null", "-",
    ])
    starts = [float(value) for value in re.findall(r"silence_start:\s*([0-9.]+)", output)]
    ends = [
        (float(end), float(duration))
        for end, duration in re.findall(r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)", output)
    ]
    return [
        {"start": round(start, 3), "end": round(end, 3), "duration": round(duration, 3)}
        for start, (end, duration) in zip(starts, ends)
    ]


def detect_freeze(path: Path, noise: float = 0.003, min_duration: float = 1.5) -> list[dict]:
    output = run_ffmpeg([
        "ffmpeg", "-hide_banner", "-i", str(path),
        "-vf", f"freezedetect=n={noise}:d={min_duration}",
        "-an", "-f", "null", "-",
    ])
    starts = [float(value) for value in re.findall(r"freeze_start:\s*([0-9.]+)", output)]
    durations = [float(value) for value in re.findall(r"freeze_duration:\s*([0-9.]+)", output)]
    ends = [float(value) for value in re.findall(r"freeze_end:\s*([0-9.]+)", output)]
    return [
        {"start": round(start, 3), "end": round(end, 3), "duration": round(duration, 3)}
        for start, end, duration in zip(starts, ends, durations)
    ]


def sound_signal_screening(plan: dict, silences: list[dict]) -> dict:
    """Flag likely missing continuous beds without pretending signal analysis is listening."""
    sound = plan.get("sound_design_contract") or {}
    required_layers = sound.get("required_layers") or {}
    continuous_bed_expected = bool(
        sound.get("non_speech_required")
        and (required_layers.get("ambience") or required_layers.get("music"))
    )
    longest_silence = max((float(item.get("duration") or 0) for item in silences), default=0.0)
    potential_missing_bed = continuous_bed_expected and longest_silence >= 0.4
    return {
        "continuous_bed_expected": continuous_bed_expected,
        "longest_detected_silence_seconds": round(longest_silence, 3),
        "potential_missing_continuous_bed": potential_missing_bed,
        "candidate_qc_failure_codes": ["QC_SOUND_DESIGN_MISSING"] if potential_missing_bed else [],
        "interpretation": (
            "Signal screening found a silence gap inconsistent with the planned continuous bed; human or multimodal listening must decide."
            if potential_missing_bed else
            "No decisive missing-bed signal was found; human or multimodal listening is still required."
        ),
        "listening_verdict": False,
    }


def read_stitch_report(video: Path) -> dict:
    candidates = [video.with_suffix(".stitch-report.json"), video.parent / "final.stitch-report.json"]
    for path in candidates:
        if path.exists():
            return load_json(path)
    return {}


def expected_clip_errors(plan: dict) -> list[str]:
    errors = []
    for shot in plan.get("shots") or []:
        path = Path(str(shot.get("clip_file") or "")).expanduser()
        if not path.is_file():
            errors.append(f"Expected clip is missing: {shot.get('id')} -> {path}")
    return errors


def script_boundary_reviews(plan: dict) -> list[dict]:
    shots = plan.get("shots") or []
    reviews = []
    for index, shot in enumerate(shots[:-1]):
        boundary = shot.get("script_boundary") or {}
        reviews.append({
            "after_shot": shot.get("id"),
            "before_shot": shots[index + 1].get("id"),
            "stitch_safe": boundary.get("stitch_safe") is True,
            "kind": boundary.get("kind") or "unknown",
            "spoken_tail": str(shot.get("spoken_script") or "")[-80:],
        })
    return reviews


def stitch_policy_pass(report: dict, expected_boundaries: int) -> bool:
    if expected_boundaries == 0:
        return True
    if not report:
        return False
    nested = report.get("audio_boundary_policy") if isinstance(report.get("audio_boundary_policy"), dict) else {}
    fades = report.get("per_clip_fades_applied", nested.get("per_clip_fades_applied"))
    crossfade = report.get("crossfade_applied", nested.get("crossfade_applied"))
    one_aac = report.get("single_final_aac_encode", nested.get("single_final_aac_encode"))
    pcm = report.get("intermediate_audio_codec") == "pcm_s16le" or "pcm_intermediates" in str(nested.get("strategy") or "")
    return fades is False and crossfade is False and one_aac is True and pcm


def resolve_local_asset(value: str, project_dir: Path) -> Path | None:
    if not value or value.startswith("data:") or is_url(value):
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = project_dir / path
    path = path.resolve()
    return path if path.is_file() else None


def source_frame_comparisons(plan: dict, project_dir: Path) -> list[dict]:
    """Prepare side-by-side evidence for Codex multimodal business review."""
    output_dir = project_dir / "review_frames" / "source-comparisons"
    output_dir.mkdir(parents=True, exist_ok=True)
    comparisons: list[dict] = []
    for shot in plan.get("shots") or []:
        shot_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(shot.get("id") or "shot"))
        source = resolve_local_asset(asset_value(shot.get("image")), project_dir)
        clip = resolve_local_asset(str(shot.get("clip_file") or ""), project_dir)
        item = {
            "shot_id": shot.get("id"),
            "source_image": str(source) if source else "",
            "clip": str(clip) if clip else "",
            "status": "unavailable",
            "review_instruction": "Compare the approved source image with the generated first frame and reject unrelated product, presenter, scene, or composition.",
        }
        if not source or not clip:
            item["reason"] = "local source image or generated clip is unavailable"
            comparisons.append(item)
            continue
        first_frame = output_dir / f"{shot_id}-video-first-frame.png"
        comparison = output_dir / f"{shot_id}-source-vs-video-first-frame.png"
        try:
            run_ffmpeg([
                "ffmpeg", "-y", "-hide_banner", "-ss", "0.05", "-i", str(clip),
                "-frames:v", "1", str(first_frame),
            ])
            run_ffmpeg([
                "ffmpeg", "-y", "-hide_banner", "-i", str(source), "-i", str(first_frame),
                "-filter_complex",
                "[0:v]scale=540:540:force_original_aspect_ratio=decrease,pad=540:540:(ow-iw)/2:(oh-ih)/2:black[left];"
                "[1:v]scale=540:540:force_original_aspect_ratio=decrease,pad=540:540:(ow-iw)/2:(oh-ih)/2:black[right];"
                "[left][right]hstack=inputs=2[out]",
                "-map", "[out]", "-frames:v", "1", str(comparison),
            ])
            item.update({
                "status": "multimodal_review_required",
                "source_image_sha256": sha256_file(source),
                "video_first_frame": str(first_frame),
                "video_first_frame_sha256": sha256_file(first_frame),
                "comparison_image": str(comparison),
                "source_frame_consistency": None,
            })
        except ScriptError as exc:
            item["reason"] = str(exc)
        comparisons.append(item)
    return comparisons


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--video")
    parser.add_argument("--clean", action="store_true", help="Write final-review.clean.json before optional local captions")
    parser.add_argument("--duration-tolerance", type=float, default=0.15)
    parser.add_argument("--silence-threshold-db", type=float, default=-35.0)
    parser.add_argument("--min-silence", type=float, default=0.4)
    parser.add_argument("--freeze-min-duration", type=float, default=1.5)
    args = parser.parse_args()
    try:
        require_ffmpeg()
        project_dir = Path(args.project_dir).expanduser().resolve()
        plan = load_json(project_dir / "generation-plan.json")
        video = Path(args.video).expanduser().resolve() if args.video else project_dir / "final.mp4"
        media = verify_media_file(video, require_audio=False)
        actual_duration = float(media.get("duration_seconds") or 0)
        hard_max = float(plan.get("delivery_max_seconds") or plan.get("total_duration_seconds") or 0)
        duration_pass = hard_max <= 0 or actual_duration <= hard_max + max(0.0, args.duration_tolerance)
        silences = detect_silence(video, args.silence_threshold_db, args.min_silence) if media.get("has_audio") else []
        freezes = detect_freeze(video, min_duration=args.freeze_min_duration)
        boundaries = script_boundary_reviews(plan)
        stitch_report = read_stitch_report(video)
        stitch_pass = stitch_policy_pass(stitch_report, len(boundaries))
        comparisons = source_frame_comparisons(plan, project_dir)
        issues = expected_clip_errors(plan)
        quality_contract = plan.get("quality_contract") or {}
        shortfall_limit = float(quality_contract.get("max_provider_duration_shortfall_seconds", 1.0))
        clip_duration_reviews = []
        for shot in plan.get("shots") or []:
            clip_path = resolve_local_asset(str(shot.get("clip_file") or ""), project_dir)
            if not clip_path:
                continue
            clip_media = verify_media_file(clip_path, require_audio=False)
            planned_seconds = float(shot.get("duration_seconds") or 0)
            clip_seconds = float(clip_media.get("duration_seconds") or 0)
            shortfall = max(0.0, planned_seconds - clip_seconds)
            clip_duration_reviews.append({
                "shot_id": shot.get("id"),
                "planned_seconds": planned_seconds,
                "provider_clip_seconds": clip_seconds,
                "shortfall_seconds": round(shortfall, 3),
                "pass": shortfall <= shortfall_limit,
            })
        maximum_shortfall = max((float(item["shortfall_seconds"]) for item in clip_duration_reviews), default=0.0)
        provider_shortfall_pass = maximum_shortfall <= shortfall_limit
        issues.extend(
            f"Unsafe script boundary after {item.get('after_shot')}" for item in boundaries if not item.get("stitch_safe")
        )
        if not duration_pass:
            issues.append(f"Delivery duration {actual_duration:.3f}s exceeds hard maximum {hard_max:.3f}s")
        if not provider_shortfall_pass:
            issues.append(
                f"Provider clip is {maximum_shortfall:.3f}s shorter than its approved duration; "
                f"the maximum allowed end hold is {shortfall_limit:.3f}s"
            )
        if not stitch_pass:
            issues.append("Multi-clip stitch report does not prove PCM intermediates, no fades/crossfades, and one final AAC encode")
        technical_status = "pass" if not issues else "blocked"
        signal_screening = sound_signal_screening(plan, silences)
        report = {
            "status": technical_status,
            "review_scope": "technical_media_only",
            "technical_status": technical_status,
            "delivery_status": "pending_business_review" if technical_status == "pass" else "blocked_technical",
            "formal_delivery_approved": False,
            "video": str(video),
            "video_sha256": sha256_file(video),
            "media": media,
            "actual_duration_seconds": actual_duration,
            "delivery_max_seconds": hard_max,
            "delivery_duration_hard_limit_pass": duration_pass,
            "provider_clip_duration_reviews": clip_duration_reviews,
            "max_provider_duration_shortfall_seconds": maximum_shortfall,
            "provider_duration_shortfall_limit_seconds": shortfall_limit,
            "provider_duration_shortfall_pass": provider_shortfall_pass,
            "silences": silences,
            "sound_signal_screening": signal_screening,
            "freezes": freezes,
            "boundary_count": len(boundaries),
            "boundary_reviews": boundaries,
            "stitch_report": str(video.with_suffix(".stitch-report.json")) if stitch_report else "",
            "stitch_audio_policy_pass": stitch_pass,
            "source_frame_comparisons": comparisons,
            "issues": issues,
            "multimodal_visual_review_required": True,
            "visual_review_fields": planned_visual_review_fields(plan),
            "qc_failure_code_catalog": QC_FAILURE_CODES,
            "selected_qc_failure_codes": [],
            "paid_repair_authorized": False,
            "acceptance_note": (
                "Judge speech by intelligibility and approximate selling meaning, not word-for-word script identity. "
                "Separately listen for every required SFX, ambience, and music layer; an AAC stream does not prove them. "
                "Record packaging text, generated text, price, CTA, disclaimer, silence, and freeze observations as notes "
                "unless they make the video incomplete, incoherent, or unusable."
            ),
            "paid_api_call": False,
        }
        subtitles_enabled = bool((plan.get("subtitle_plan") or {}).get("enabled"))
        output = project_dir / ("final-review.clean.json" if args.clean or subtitles_enabled else "final-review.json")
        write_json(output, report)
        print(json.dumps({"ok": not issues, **report, "report_file": str(output)}, ensure_ascii=False, indent=2))
        return 0 if not issues else 1
    except (ScriptError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "status": "blocked", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
