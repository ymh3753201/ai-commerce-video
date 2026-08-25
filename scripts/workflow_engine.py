#!/usr/bin/env python3
"""Operate one commerce-video project through its guarded production workflow."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from _common import ScriptError, canonical_digest, load_json
from _workflow import atomic_write_json, load_or_create_jobs, pollable_request_id, transition_job
from finalize_project import CAPTION_VISUAL_FIELDS
from review_render import planned_visual_review_fields


SCRIPT_DIR = Path(__file__).resolve().parent


def run_worker(args: list[str]) -> tuple[int, dict]:
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        data = json.loads(result.stdout) if result.stdout.strip() else {"ok": False, "error": result.stderr.strip()}
    except json.JSONDecodeError:
        data = {"ok": False, "error": result.stderr.strip() or result.stdout.strip()}
    return result.returncode, data


def plan_requires_audio(plan: dict) -> bool:
    creative = plan.get("creative_contract") or {}
    platform = plan.get("platform_contract") or {}
    speaker_mode = str(creative.get("speaker_mode") or "")
    audio_policy = str(platform.get("audio_policy") or "")
    return audio_policy != "no_audio" and speaker_mode in {"digital-human-spoken", "voiceover"}


def project_stage(project_dir: Path) -> dict:
    delivery = project_dir / "delivery-manifest.json"
    finalize = project_dir / "finalize-report.json"
    jobs_path = project_dir / "jobs.json"
    confirmation = project_dir / "video-confirmation.json"
    preflight = project_dir / "preflight-report.json"
    plan = project_dir / "generation-plan.json"
    def reviews_ready() -> bool:
        plan_data = load_json(plan) if plan.exists() else {}
        subtitles_enabled = bool((plan_data.get("subtitle_plan") or {}).get("enabled"))
        technical_path = project_dir / ("final-review.clean.json" if subtitles_enabled else "final-review.json")
        clean_visual_path = project_dir / ("visual-review.clean.json" if subtitles_enabled else "visual-review.json")
        if not technical_path.exists() or not clean_visual_path.exists():
            return False
        technical = load_json(technical_path)
        visual = load_json(clean_visual_path)
        clean_hash = str(technical.get("video_sha256") or "")
        if (
            technical.get("status") != "pass"
            or technical.get("delivery_duration_hard_limit_pass") is not True
            or not clean_hash
            or visual.get("status") not in {"pass", "pass_with_notes"}
            or visual.get("video_sha256") != clean_hash
            or any(visual.get(field) is not True for field in planned_visual_review_fields(plan_data))
        ):
            return False
        if subtitles_enabled:
            caption_path = project_dir / "visual-review.json"
            if not caption_path.exists():
                return False
            caption = load_json(caption_path)
            if (
                caption.get("status") not in {"pass", "pass_with_notes"}
                or not caption.get("video_sha256")
                or any(caption.get(field) is not True for field in CAPTION_VISUAL_FIELDS)
            ):
                return False
        return True
    if delivery.exists() and load_json(delivery).get("status") == "pass":
        stage = "delivered"
    elif finalize.exists() and load_json(finalize).get("status") == "blocked":
        stage = "blocked"
    elif jobs_path.exists():
        states = [item.get("state") for item in (load_json(jobs_path).get("jobs") or {}).values()]
        technically_verified = bool(states and all(item == "verified" for item in states))
        if technically_verified and reviews_ready():
            stage = "ready_to_finalize"
        elif technically_verified:
            stage = "awaiting_business_review"
        else:
            stage = "generating"
    elif confirmation.exists():
        stage = "confirmed"
    elif preflight.exists() and load_json(preflight).get("ok"):
        stage = "preflight_passed"
    elif plan.exists():
        stage = "prepared"
    else:
        stage = "uninitialized"
    return {
        "ok": True,
        "project_dir": str(project_dir),
        "stage": stage,
        "files": {
            "plan": str(plan) if plan.exists() else "",
            "preflight": str(preflight) if preflight.exists() else "",
            "confirmation": str(confirmation) if confirmation.exists() else "",
            "jobs": str(jobs_path) if jobs_path.exists() else "",
            "finalize": str(finalize) if finalize.exists() else "",
            "delivery": str(delivery) if delivery.exists() else "",
        },
    }


def create_confirmation(project_dir: Path, approved_by: str) -> dict:
    plan = load_json(project_dir / "generation-plan.json")
    preflight = load_json(project_dir / "preflight-report.json")
    if not preflight.get("ok") or not preflight.get("paid_generation_allowed"):
        raise ScriptError("Preflight must pass before production confirmation")
    contract = load_json(project_dir / "production-contract.json")
    production = plan.get("production_contract") or {}
    base_count = len(plan.get("shots") or [])
    paid_cap = int(production.get("approved_paid_cap") or 0)
    if paid_cap != base_count or int(contract.get("approved_paid_cap") or 0) != base_count:
        raise ScriptError("Confirmation paid cap must equal the base request count")
    components = {
        "approved_by": approved_by,
        "plan_confirmed": True,
        "image_assets_confirmed": True,
        "video_generation_confirmed": True,
        "paid_video_authorized": True,
        "contract_digest": contract.get("contract_digest"),
        "plan_digest": contract.get("plan_digest"),
        "duration_plan_digest": contract.get("duration_plan_digest"),
        "asset_fingerprints": contract.get("asset_fingerprints") or [],
        "approved_paid_cap": base_count,
        "base_request_count": base_count,
        "repair_reserve": 0,
        "per_shot_repair_limit": 0,
        "authorization_scope": "one_provider_post_per_base_shot_no_paid_repair",
    }
    confirmation = {
        **components,
        "confirmation_digest": canonical_digest(components),
        "approved_at": int(time.time()),
    }
    path = project_dir / "video-confirmation.json"
    if path.exists():
        existing = load_json(path)
        if existing.get("confirmation_digest") != confirmation.get("confirmation_digest"):
            raise ScriptError("A different immutable video confirmation already exists")
        confirmation = existing
    else:
        atomic_write_json(path, confirmation)
    load_or_create_jobs(
        project_dir,
        plan,
        contract_digest=str(contract.get("contract_digest") or ""),
        approved_paid_cap=base_count,
    )
    return {"ok": True, "confirmation_file": str(path), "jobs_file": str(project_dir / "jobs.json"), **confirmation}


def poll_jobs(project_dir: Path, timeout: int, interval: int, require_audio: bool) -> tuple[int, dict]:
    ledger = load_json(project_dir / "jobs.json")
    results = []
    failed = False
    for shot_id, job in (ledger.get("jobs") or {}).items():
        if job.get("state") not in {"submitted", "polling", "blocked"} or not job.get("request_id"):
            continue
        pollable_request_id(ledger, shot_id)
        if job.get("state") in {"submitted", "blocked"}:
            transition_job(project_dir, ledger, shot_id, "polling")
        command = [
            sys.executable,
            str(SCRIPT_DIR / "poll_video.py"),
            "--request-file",
            str(job.get("request_file")),
            "--timeout",
            str(timeout),
            "--interval",
            str(interval),
        ]
        if require_audio:
            command.append("--require-audio")
        code, data = run_worker(command)
        if code == 0:
            transition_job(
                project_dir,
                ledger,
                shot_id,
                "downloaded",
                clip_file=data.get("output") or job.get("clip_file"),
                last_error="",
            )
            transition_job(
                project_dir,
                ledger,
                shot_id,
                "verified",
                verification_scope="technical_media_only",
                business_review_required=True,
            )
        else:
            transition_job(
                project_dir,
                ledger,
                shot_id,
                "blocked",
                clip_file=data.get("output") or job.get("clip_file"),
                last_error=data.get("error") or data,
                failure_code=data.get("error_code") or "provider_poll_failed",
                automatic_paid_retry=False,
            )
            failed = True
        results.append({"shot_id": shot_id, "code": code, "result": data})
    return (1 if failed else 0), {"ok": not failed, "results": results, "automatic_paid_repairs": []}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--config")
    confirm = subparsers.add_parser("confirm")
    confirm.add_argument("--approved-by", required=True)
    submit = subparsers.add_parser("submit")
    submit.add_argument("--config")
    submit.add_argument("--shot-id")
    poll = subparsers.add_parser("poll")
    poll.add_argument("--timeout", type=int, default=900)
    poll.add_argument("--interval", type=int, default=5)
    poll.add_argument("--require-audio", action="store_true")
    resume = subparsers.add_parser("resume")
    resume.add_argument("--timeout", type=int, default=900)
    resume.add_argument("--interval", type=int, default=5)
    resume.add_argument("--require-audio", action="store_true")
    subparsers.add_parser("finalize")
    subparsers.add_parser("status")
    args = parser.parse_args()
    project_dir = Path(args.project_dir).expanduser().resolve()
    plan_path = project_dir / "generation-plan.json"
    try:
        if args.command == "status":
            data = project_stage(project_dir)
            code = 0
        elif args.command == "preflight":
            command = [sys.executable, str(SCRIPT_DIR / "preflight_project.py"), "--plan", str(plan_path)]
            if args.config:
                command.extend(["--config", args.config])
            code, data = run_worker(command)
        elif args.command == "confirm":
            data = create_confirmation(project_dir, args.approved_by)
            code = 0
        elif args.command == "submit":
            plan = load_json(plan_path)
            paid_cap = int((plan.get("production_contract") or {}).get("approved_paid_cap") or 0)
            confirmation_path = project_dir / "video-confirmation.json"
            if not confirmation_path.exists():
                raise ScriptError("Run confirm before submit so the existing user authorization is stored in the project")
            jobs_path = project_dir / "jobs.json"
            jobs = load_json(jobs_path) if jobs_path.exists() else {}
            prior_attempts = int(jobs.get("paid_submission_attempts") or 0)
            readiness = None
            code = 0
            if prior_attempts == 0:
                readiness_command = [
                    sys.executable,
                    str(SCRIPT_DIR / "check_provider_readiness.py"),
                    "--project-dir",
                    str(project_dir),
                    "--model-key",
                    str(plan.get("model_key") or ""),
                ]
                if args.config:
                    readiness_command.extend(["--config", args.config])
                readiness_code, readiness = run_worker(readiness_command)
                if readiness_code != 0:
                    data = {
                        "ok": False,
                        "stage": "provider_readiness",
                        "error": readiness.get("error") or "Provider readiness check failed before paid submission",
                        "error_code": readiness.get("error_code") or "provider_readiness_failed",
                        "paid_api_call": False,
                        "provider_generation_post_attempted": False,
                        "authorization_preserved": True,
                        "reconfirmation_required": False,
                        "provider_readiness": readiness,
                    }
                    code = 1
            if code == 0:
                command = [
                    sys.executable,
                    str(SCRIPT_DIR / "generate_video.py"),
                    "--plan",
                    str(plan_path),
                    "--confirmation-file",
                    str(confirmation_path),
                    "--readiness-file",
                    str(project_dir / "provider-readiness.json"),
                    "--max-paid-submissions",
                    str(paid_cap),
                ]
                if args.config:
                    command.extend(["--config", args.config])
                if args.shot_id:
                    command.extend(["--shot-id", args.shot_id])
                code, data = run_worker(command)
                if readiness is not None:
                    data["provider_readiness"] = readiness
        elif args.command in {"poll", "resume"}:
            plan = load_json(plan_path)
            require_audio = bool(args.require_audio or plan_requires_audio(plan))
            code, data = poll_jobs(project_dir, args.timeout, args.interval, require_audio)
            data["audio_required"] = require_audio
        elif args.command == "finalize":
            code, data = run_worker([sys.executable, str(SCRIPT_DIR / "finalize_project.py"), "--project-dir", str(project_dir)])
        else:
            raise ScriptError(f"Unsupported command: {args.command}")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return code
    except (ScriptError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
