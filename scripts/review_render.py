#!/usr/bin/env python3
"""Review a rendered commerce MP4 and its multi-clip boundaries without spending API credits."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from _common import ScriptError, load_json, require_ffmpeg, sha256_file, verify_media_file, write_json


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
        issues = expected_clip_errors(plan)
        issues.extend(
            f"Unsafe script boundary after {item.get('after_shot')}" for item in boundaries if not item.get("stitch_safe")
        )
        if not duration_pass:
            issues.append(f"Delivery duration {actual_duration:.3f}s exceeds hard maximum {hard_max:.3f}s")
        if not stitch_pass:
            issues.append("Multi-clip stitch report does not prove PCM intermediates, no fades/crossfades, and one final AAC encode")
        report = {
            "status": "pass" if not issues else "blocked",
            "video": str(video),
            "video_sha256": sha256_file(video),
            "media": media,
            "actual_duration_seconds": actual_duration,
            "delivery_max_seconds": hard_max,
            "delivery_duration_hard_limit_pass": duration_pass,
            "silences": silences,
            "freezes": freezes,
            "boundary_count": len(boundaries),
            "boundary_reviews": boundaries,
            "stitch_report": str(video.with_suffix(".stitch-report.json")) if stitch_report else "",
            "stitch_audio_policy_pass": stitch_pass,
            "issues": issues,
            "multimodal_visual_review_required": True,
            "visual_review_fields": [
                "approved_product_identity",
                "approved_product_text_integrity",
                "presenter_identity",
                "scene_and_framing",
                "mouth_visibility",
                "no_generated_text",
                "no_unapproved_visual_insert",
                "spoken_content_complete",
                "critical_facts_exact",
            ],
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
