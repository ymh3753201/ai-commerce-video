#!/usr/bin/env python3
"""Strict clean-Provider and optional local subtitle policy."""

from __future__ import annotations


REQUIRED_ENABLED_VALUES = {
    "enabled": True,
    "request_source": "user_plan_confirmation",
    "confirmation_status": "confirmed",
    "provider_policy": "never_send",
    "render_policy": "postproduction_burn_only",
    "paid_api_call": False,
}


def subtitle_plan_from(value: dict | None) -> dict:
    raw = dict(value or {})
    enabled = raw.get("enabled") is True
    if not enabled:
        return {
            "enabled": False,
            "request_source": raw.get("request_source") or "default",
            "confirmation_status": raw.get("confirmation_status") or "disabled",
            "provider_policy": "never_send",
            "render_policy": "disabled",
            "paid_api_call": False,
            "subtitle_included_in_payload": False,
        }
    result = dict(REQUIRED_ENABLED_VALUES)
    result.update(raw)
    result["subtitle_included_in_payload"] = False
    return result


def enabled_subtitle_contract_errors(value: dict | None, prefix: str = "Optional subtitles") -> list[str]:
    raw = dict(value or {})
    plan = subtitle_plan_from(value)
    if not plan.get("enabled"):
        return []
    errors: list[str] = []
    for field, expected in REQUIRED_ENABLED_VALUES.items():
        actual = plan.get(field)
        if actual != expected:
            errors.append(f"{prefix}: {field} must be {expected!r}; got {actual!r}")
    if "subtitle_included_in_payload" in raw and raw.get("subtitle_included_in_payload") is not False:
        errors.append(
            f"{prefix}: subtitle_included_in_payload must be False; got "
            f"{raw.get('subtitle_included_in_payload')!r}"
        )
    return errors


def is_confirmed_postproduction_subtitle_plan(value: dict | None) -> bool:
    plan = subtitle_plan_from(value)
    return bool(plan.get("enabled")) and not enabled_subtitle_contract_errors(value)
