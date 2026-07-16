#!/usr/bin/env python3
"""Production contracts and durable paid-job state for commerce videos."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, TextIO

from _common import ScriptError, asset_value, canonical_digest, is_url, load_json, sha256_file


CONTRACT_VERSION = "1.0"
LEDGER_VERSION = "1.0"
JOB_STATES = ("planned", "attempted", "submitted", "polling", "downloaded", "verified", "blocked")
ALLOWED_TRANSITIONS = {
    "planned": {"attempted", "blocked"},
    "attempted": {"submitted", "blocked"},
    "submitted": {"polling", "downloaded", "blocked"},
    "polling": {"polling", "downloaded", "blocked"},
    "downloaded": {"verified", "blocked"},
    "verified": {"verified"},
    "blocked": {"blocked", "polling"},
}
SECRET_KEY_PARTS = ("api_key", "authorization", "bearer", "secret", "access_token")


def atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def acquire_paid_submission_lock(project_dir: Path) -> TextIO:
    lock_path = project_dir / ".paid-submit.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise ScriptError(f"Another paid submission is already running for this project: {lock_path}") from exc
    handle.seek(0)
    handle.truncate()
    handle.write(json.dumps({"pid": os.getpid(), "locked_at": int(time.time())}) + "\n")
    handle.flush()
    os.fsync(handle.fileno())
    return handle


def release_paid_submission_lock(handle: TextIO | None) -> None:
    if handle is None or handle.closed:
        return
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def fingerprint_asset(asset: dict) -> dict:
    value = asset_value(asset)
    result = {
        "id": str(asset.get("id") or ""),
        "role": str(asset.get("role") or ""),
        "kind": str(asset.get("kind") or ("url" if is_url(value) else "file")),
    }
    if not value:
        return {**result, "status": "missing_value", "sha256": ""}
    if value.startswith("data:"):
        encoded = value.encode("utf-8")
        return {**result, "status": "data_uri", "sha256": hashlib.sha256(encoded).hexdigest(), "size_bytes": len(encoded)}
    if is_url(value):
        return {
            **result,
            "status": "remote_url_unbound",
            "sha256": "",
            "url_sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
        }
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        return {**result, "status": "missing_file", "sha256": "", "path": str(path)}
    return {
        **result,
        "status": "local",
        "path": str(path),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def redact_model_snapshot(model: dict) -> dict:
    snapshot = {}
    for key, value in model.items():
        normalized = str(key).lower()
        if any(part in normalized for part in SECRET_KEY_PARTS) and key != "api_key_env_names":
            continue
        snapshot[key] = value
    return snapshot


def collect_asset_fingerprints(plan: dict) -> list[dict]:
    candidates: list[dict] = []
    for field in ("product_asset",):
        item = plan.get(field)
        if isinstance(item, dict):
            candidates.append(item)
    candidates.extend(item for item in (plan.get("references") or []) if isinstance(item, dict))
    contract = plan.get("asset_contract") or {}
    for field in ("video_source_asset",):
        item = contract.get(field)
        if isinstance(item, dict):
            candidates.append(item)
    candidates.extend(item for item in (contract.get("segment_source_assets") or []) if isinstance(item, dict))
    subtitle_input = (plan.get("subtitle_plan") or {}).get("input_subtitle")
    if isinstance(subtitle_input, dict) and asset_value(subtitle_input):
        candidates.append(subtitle_input)
    seen: set[tuple[str, str]] = set()
    result: list[dict] = []
    for item in candidates:
        marker = (str(item.get("role") or ""), asset_value(item))
        if marker in seen:
            continue
        seen.add(marker)
        result.append(fingerprint_asset(item))
    return sorted(result, key=lambda item: (item.get("role", ""), item.get("path", ""), item.get("url_sha256", "")))


def summarize_request(record: dict) -> dict:
    return {
        "shot_id": str(record.get("shot_id") or ""),
        "model_key": str(record.get("model_key") or ""),
        "payload_digest": canonical_digest(record.get("payload") or {}),
        "asset_trace_digest": canonical_digest(record.get("asset_trace") or {}),
        "dry_run": bool(record.get("dry_run")),
    }


def build_contract(plan: dict, model: dict, request_records: list[dict]) -> dict:
    production = plan.get("production_contract") or {}
    base_count = len(plan.get("shots") or [])
    paid_cap = int(production.get("approved_paid_cap") or 0)
    if paid_cap != base_count:
        raise ScriptError(
            f"approved_paid_cap must equal the {base_count} base request(s); got {paid_cap}"
        )
    if int(production.get("repair_reserve") or 0) != 0 or int(production.get("per_shot_repair_limit") or 0) != 0:
        raise ScriptError("Normal commerce production requires repair_reserve=0 and per_shot_repair_limit=0")
    model_snapshot = redact_model_snapshot(model)
    components = {
        "version": CONTRACT_VERSION,
        "plan_digest": canonical_digest(plan),
        "duration_plan_digest": str(plan.get("duration_plan_digest") or ""),
        "model_snapshot": model_snapshot,
        "model_digest": canonical_digest(model_snapshot),
        "asset_fingerprints": collect_asset_fingerprints(plan),
        "dry_run_requests": sorted((summarize_request(item) for item in request_records), key=lambda item: item["shot_id"]),
        "base_request_count": base_count,
        "approved_paid_cap": paid_cap,
        "repair_reserve": 0,
        "per_shot_repair_limit": 0,
        "max_generated_seconds": sum(int(shot.get("duration_seconds") or 0) for shot in (plan.get("shots") or [])),
    }
    return {**components, "contract_digest": canonical_digest(components), "created_at": int(time.time())}


def verify_contract(contract: dict, plan: dict, model: dict, request_records: list[dict]) -> list[str]:
    current = build_contract(plan, model, request_records)
    errors: list[str] = []
    for field in (
        "plan_digest",
        "duration_plan_digest",
        "model_digest",
        "asset_fingerprints",
        "dry_run_requests",
        "base_request_count",
        "approved_paid_cap",
        "contract_digest",
    ):
        if contract.get(field) != current.get(field):
            errors.append(f"Production contract {field} no longer matches the approved project state")
    return errors


def jobs_path(project_dir: Path) -> Path:
    return project_dir / "jobs.json"


def _shots_from(value) -> list[dict]:
    if isinstance(value, dict):
        return list(value.get("shots") or [])
    return list(value or [])


def load_or_create_jobs(
    project_dir: Path,
    plan_or_shots,
    contract_digest: str = "",
    approved_paid_cap: int | None = None,
    max_paid_submissions: int | None = None,
) -> dict:
    project_dir = Path(project_dir).expanduser().resolve()
    shots = _shots_from(plan_or_shots)
    cap = int(approved_paid_cap if approved_paid_cap is not None else max_paid_submissions or 0)
    if cap != len(shots) or cap <= 0:
        raise ScriptError(f"Approved paid cap must equal the {len(shots)} base shot(s); got {cap}")
    path = jobs_path(project_dir)
    if path.exists():
        ledger = load_json(path)
        if contract_digest and ledger.get("contract_digest") != contract_digest:
            raise ScriptError("Existing jobs.json belongs to a different production contract")
        if int(ledger.get("approved_paid_cap") or 0) != cap:
            raise ScriptError("Existing jobs.json has a different approved paid cap")
        return ledger
    jobs = {}
    for shot in shots:
        shot_id = str(shot.get("id") or "")
        if not shot_id:
            raise ScriptError("Every shot needs an id before creating jobs.json")
        jobs[shot_id] = {
            "shot_id": shot_id,
            "state": "planned",
            "idempotency_key": canonical_digest({"contract_digest": contract_digest, "shot_id": shot_id}),
            "submission_attempts": 0,
            "request_id": "",
            "request_file": str(shot.get("request_file") or ""),
            "clip_file": str(shot.get("clip_file") or ""),
            "last_error": "",
            "updated_at": int(time.time()),
        }
    ledger = {
        "version": LEDGER_VERSION,
        "contract_digest": contract_digest,
        "approved_paid_cap": cap,
        "max_paid_submissions": cap,
        "paid_submission_attempts": 0,
        "repair_reserve": 0,
        "per_shot_repair_limit": 0,
        "jobs": jobs,
        "updated_at": int(time.time()),
    }
    atomic_write_json(path, ledger)
    return ledger


def save_jobs(project_dir: Path, ledger: dict) -> None:
    ledger["updated_at"] = int(time.time())
    atomic_write_json(jobs_path(Path(project_dir)), ledger)


def transition_job(project_dir: Path, ledger: dict, shot_id: str, new_state: str, **updates: Any) -> dict:
    if new_state not in JOB_STATES:
        raise ScriptError(f"Unknown job state: {new_state}")
    job = (ledger.get("jobs") or {}).get(shot_id)
    if not job:
        raise ScriptError(f"Job not found: {shot_id}")
    current = str(job.get("state") or "planned")
    if new_state != current and new_state not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ScriptError(f"Illegal job transition for {shot_id}: {current} -> {new_state}")
    job.update(updates)
    job["state"] = new_state
    job["updated_at"] = int(time.time())
    save_jobs(project_dir, ledger)
    return job


def record_submission_attempt(project_dir: Path, ledger: dict, shot_id: str, reason: str = "initial") -> int:
    job = (ledger.get("jobs") or {}).get(shot_id)
    if not job:
        raise ScriptError(f"Job not found: {shot_id}")
    if reason != "initial":
        raise ScriptError("Paid repair or quality regeneration is disabled")
    if int(job.get("submission_attempts") or 0) > 0 or str(job.get("state")) != "planned":
        raise ScriptError(
            f"Refusing a second paid submission for {shot_id}; poll/download the existing request ID instead"
        )
    attempts = int(ledger.get("paid_submission_attempts") or 0)
    maximum = int(ledger.get("approved_paid_cap") or 0)
    if attempts >= maximum:
        raise ScriptError(f"Paid submission budget exhausted: {attempts}/{maximum}")
    ledger["paid_submission_attempts"] = attempts + 1
    job["submission_attempts"] = 1
    job["state"] = "attempted"
    job["last_submission_reason"] = "initial"
    job["updated_at"] = int(time.time())
    save_jobs(project_dir, ledger)
    return attempts + 1


def pollable_request_id(ledger: dict, shot_id: str) -> str:
    job = (ledger.get("jobs") or {}).get(shot_id)
    if not job:
        raise ScriptError(f"Job not found: {shot_id}")
    request_id = str(job.get("request_id") or "")
    if not request_id:
        raise ScriptError(f"Job {shot_id} has no request ID; resubmission is unsafe")
    if str(job.get("state") or "") not in {"submitted", "polling", "downloaded", "verified", "blocked"}:
        raise ScriptError(f"Job {shot_id} is not pollable from state {job.get('state')}")
    return request_id
