#!/usr/bin/env python3
"""Run the complete no-cost commerce readiness gate and freeze a contract."""

from __future__ import annotations

import argparse
import json
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
from subtitle_policy import enabled_subtitle_contract_errors
from subtitle_runtime import subtitle_runtime_errors
from validate_platform_plan import (
    model_contract_from_config,
    validate_model_and_assets,
    validate_platform_rules,
    validate_production_core,
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
        if "no newly generated written" not in str(shot.get("prompt") or "").lower():
            errors.append(f"{shot.get('id')} prompt is missing the clean Provider frame policy")
        boundary = shot.get("script_boundary") or {}
        if shot.get("spoken_script") and boundary.get("stitch_safe") is not True:
            errors.append(f"{shot.get('id')} does not end on a stitch-safe complete sentence")
    errors.extend(enabled_subtitle_contract_errors(plan.get("subtitle_plan") or {}))
    errors.extend(subtitle_runtime_errors(plan))
    return errors


def platform_errors(plan: dict, config_path: str | None, model_key: str | None) -> list[str]:
    checks: list[dict] = []
    validate_platform_rules(plan, checks)
    contract = model_contract_from_config(plan, config_path, model_key)
    validate_model_and_assets(plan, checks, contract)
    validate_production_core(plan, checks, contract)
    return [str(item.get("evidence") or item.get("text")) for item in checks if item.get("severity") == "error" and not item.get("passed")]


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
            })
        errors = plan_errors(plan, model)
        errors.extend(platform_errors(plan, args.config, args.model_key))
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
            "prompt_summary": prompt_summary,
            "dry_run_request_count": len(records),
            "expected_paid_requests": len(plan.get("shots") or []),
            "paid_generation_allowed": not errors,
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
