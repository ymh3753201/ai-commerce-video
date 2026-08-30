#!/usr/bin/env python3
"""Record the narrow voice-contract review for a rendered commerce video."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _common import ScriptError, load_json, sha256_file, verify_media_file, write_json
from _workflow import (
    required_voice_review_fields,
    speech_presentation,
    voice_contract_review_required,
    voice_review_path,
)


def yes_no(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized not in {"yes", "no"}:
        raise argparse.ArgumentTypeError("expected yes or no")
    return normalized == "yes"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--video", help="Clean MP4 reviewed; default: <project>/final.mp4")
    parser.add_argument(
        "--review-method",
        required=True,
        choices=("codex_multimodal", "local_asr_plus_visual", "human_listening"),
    )
    parser.add_argument("--speech-present", type=yes_no)
    parser.add_argument("--speech-intelligible", type=yes_no)
    parser.add_argument("--speech-meaning-preserved", type=yes_no)
    parser.add_argument("--presenter-speaks-on-camera", type=yes_no)
    parser.add_argument("--visible-mouth-movement", type=yes_no)
    parser.add_argument("--unexpected-speech-absent", type=yes_no)
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    try:
        plan = load_json(project_dir / "generation-plan.json")
        if not voice_contract_review_required(plan):
            raise ScriptError("This plan does not require the streamlined voice-contract review")
        video = Path(args.video).expanduser().resolve() if args.video else project_dir / "final.mp4"
        audio = plan.get("audio_contract") or {}
        sound = plan.get("sound_design_contract") or {}
        require_audio = bool(audio.get("speech_required") or sound.get("non_speech_required"))
        verify_media_file(video, require_audio=require_audio)
        presentation = speech_presentation(plan)
        report = {
            "status": "blocked",
            "review_scope": "required_voice_presence_and_presentation_only",
            "video": str(video),
            "video_sha256": sha256_file(video),
            "review_method": args.review_method,
            "speech_presentation": presentation,
            "speech_present": args.speech_present,
            "speech_intelligible": args.speech_intelligible,
            "speech_meaning_preserved": args.speech_meaning_preserved,
            "presenter_speaks_on_camera": args.presenter_speaks_on_camera,
            "visible_mouth_movement": args.visible_mouth_movement,
            "unexpected_speech_absent": args.unexpected_speech_absent,
            "required_fields": required_voice_review_fields(plan),
            "note": args.note,
            "paid_api_call": False,
            "automatic_paid_retry_authorized": False,
        }
        missing = [field for field in report["required_fields"] if report.get(field) is None]
        if missing:
            raise ScriptError(f"Voice contract review is missing required answers: {missing}")
        all_required_pass = all(report.get(field) is True for field in report["required_fields"])
        report["status"] = ("pass_with_notes" if args.note else "pass") if all_required_pass else "blocked"
        output = voice_review_path(project_dir, plan)
        write_json(output, report)
        print(json.dumps({"ok": all_required_pass, **report, "report_file": str(output)}, ensure_ascii=False, indent=2))
        return 0 if all_required_pass else 1
    except (ScriptError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "status": "blocked", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
