#!/usr/bin/env python3
"""Deterministic legal-slot and semantic script planning for commerce videos."""

from __future__ import annotations

import itertools
import math
import re
from typing import Iterable

from _common import ScriptError, canonical_digest


STRONG_ENDINGS = ("。", "！", "？", ".", "!", "?")
WEAK_ENDINGS = ("，", ",", "、", ";", "；", ":", "：")
OPEN_TAILS = (
    "第一",
    "第二",
    "第三",
    "首先",
    "其次",
    "然后",
    "以及",
    "并且",
    "包括",
    "比如",
    "例如",
    "and",
    "or",
    "including",
    "such as",
)


def normalize_allowed_slots(values: Iterable[int], max_seconds: int | None = None) -> list[int]:
    slots = sorted({int(value) for value in values if int(value) > 0}, reverse=True)
    if max_seconds is not None:
        slots = [value for value in slots if value <= int(max_seconds)]
    if not slots:
        raise ScriptError("Model configuration has no usable allowed duration slots")
    return slots


def _sequence_score(sequence: tuple[int, ...], target_seconds: int) -> tuple:
    total = sum(sequence)
    return (total - target_seconds, tuple(-value for value in sequence))


def plan_duration(
    total_seconds: int,
    allowed_slots: Iterable[int],
    max_seconds: int | None = None,
    forced_count: int | None = None,
) -> list[int]:
    """Return the minimum-count legal request slots covering the delivery target.

    An exact sum wins. Otherwise the smallest overshoot wins, followed by longer
    earlier slots so planned commerce beats remain front-loaded.
    """

    target = int(total_seconds)
    if target <= 0:
        raise ScriptError("Duration must be a positive number of seconds")
    slots = normalize_allowed_slots(allowed_slots, max_seconds=max_seconds)
    max_slot = max(slots)
    minimum_count = max(1, math.ceil(target / max_slot))
    count = int(forced_count) if forced_count is not None else minimum_count
    if count < minimum_count:
        raise ScriptError(
            f"{count} segment(s) cannot cover a {target}s delivery with a {max_slot}s model maximum"
        )
    if count > minimum_count and forced_count is not None:
        raise ScriptError(
            f"{count} segment source images would create extra paid requests; "
            f"the minimum safe request count for {target}s is {minimum_count}. "
            "Reduce the segment sources or explicitly approve a longer delivery plan."
        )

    candidates = [sequence for sequence in itertools.product(slots, repeat=count) if sum(sequence) >= target]
    if not candidates:
        raise ScriptError(
            f"Cannot cover {target}s with {count} request(s) using legal slots {sorted(slots)}"
        )
    return list(min(candidates, key=lambda item: _sequence_score(item, target)))


def estimate_spoken_seconds(text: str, language: str = "zh") -> float:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return 0.0
    if (language or "").lower().startswith(("zh", "ja", "ko")) or re.search(r"[\u3400-\u9fff]", clean):
        visible = len(re.sub(r"\s|[，。！？、；：,.!?;:]", "", clean))
        return round(max(1.0, visible / 4.2), 2)
    words = len(re.findall(r"\b\w+\b", clean))
    return round(max(1.0, words / 2.6), 2)


def split_spoken_units(text: str) -> list[str]:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return []
    units = [item.strip() for item in re.findall(r".+?(?:[。！？.!?]+|$)", clean) if item.strip()]
    return units or [clean]


def _unit_weight(text: str) -> int:
    return max(1, len(re.sub(r"\s+", "", text)))


def split_script_by_duration(script_text: str, request_durations: list[int], language: str = "zh") -> list[str]:
    del language
    count = len(request_durations)
    if count <= 0:
        raise ScriptError("At least one request duration is required")
    units = split_spoken_units(script_text)
    if not units:
        return ["" for _ in request_durations]
    if count == 1:
        return ["".join(units)]
    if len(units) < count:
        raise ScriptError(
            f"Approved spoken script has only {len(units)} complete sentence unit(s) for {count} paid segments. "
            "Rewrite the script with complete segment boundaries before paid generation."
        )

    remaining_units = list(units)
    remaining_capacity = sum(request_durations)
    chunks: list[str] = []
    for index, duration in enumerate(request_durations):
        segments_left = count - index
        if segments_left == 1:
            chunks.append("".join(remaining_units))
            break
        total_weight = sum(_unit_weight(item) for item in remaining_units)
        target_weight = total_weight * duration / max(remaining_capacity, 1)
        take = 0
        weight = 0
        max_take = len(remaining_units) - (segments_left - 1)
        while take < max_take:
            next_weight = _unit_weight(remaining_units[take])
            if take > 0 and weight + next_weight > target_weight:
                break
            weight += next_weight
            take += 1
        take = max(1, take)
        chunks.append("".join(remaining_units[:take]))
        remaining_units = remaining_units[take:]
        remaining_capacity -= duration
    if len(chunks) != count or any(not item.strip() for item in chunks):
        raise ScriptError("Could not create complete non-empty script segments")
    return chunks


def boundary_type(text: str) -> str:
    clean = (text or "").strip()
    if not clean:
        return "empty"
    if clean.endswith(STRONG_ENDINGS):
        return "strong_sentence"
    if clean.endswith(WEAK_ENDINGS):
        return "weak_clause"
    return "open_clause"


def is_stitch_safe_boundary(text: str, is_final: bool) -> bool:
    clean = (text or "").strip()
    if not clean:
        return False
    lowered = clean.lower().rstrip("。！？.!?，,、；;：: ")
    if any(lowered.endswith(tail) for tail in OPEN_TAILS):
        return False
    if is_final:
        return clean.endswith(STRONG_ENDINGS)
    return boundary_type(clean) == "strong_sentence"


def build_script_boundary(text: str, index: int, total: int) -> dict:
    is_final = index == total
    kind = boundary_type(text)
    safe = is_stitch_safe_boundary(text, is_final=is_final)
    return {
        "kind": kind,
        "stitch_safe": safe,
        "is_final": is_final,
        "rule": (
            "Final segment ends on a complete sentence."
            if is_final
            else "End on a complete sentence; no unfinished list, clause, or enumerator."
        ),
    }


def build_duration_plan(
    delivery_max_seconds: int,
    allowed_slots: Iterable[int],
    script_text: str,
    language: str = "zh",
    max_seconds: int | None = None,
    forced_count: int | None = None,
) -> tuple[dict, list[str]]:
    request_durations = plan_duration(
        delivery_max_seconds,
        allowed_slots,
        max_seconds=max_seconds,
        forced_count=forced_count,
    )
    scripts = split_script_by_duration(script_text, request_durations, language=language)
    estimated = estimate_spoken_seconds(script_text, language=language)
    for index, (segment_script, request_seconds) in enumerate(zip(scripts, request_durations), start=1):
        if not segment_script.strip():
            continue
        segment_estimate = estimate_spoken_seconds(segment_script, language=language)
        safe_capacity = max(1.0, float(request_seconds) - 0.8)
        if segment_estimate > safe_capacity:
            raise ScriptError(
                f"shot_{index:02d} exceeds safe speech capacity: estimated {segment_estimate:.2f}s "
                f"for a {request_seconds}s request with {safe_capacity:.2f}s usable speech time. "
                "Shorten or rewrite the confirmed script before paid generation."
            )
    payload = {
        "delivery_max_seconds": int(delivery_max_seconds),
        "request_durations_seconds": request_durations,
        "base_request_count": len(request_durations),
        "max_generated_seconds": sum(request_durations),
        "estimated_spoken_seconds": estimated,
        "target_fill_ratio": round(estimated / max(int(delivery_max_seconds), 1), 4),
        "allowed_duration_seconds": sorted(normalize_allowed_slots(allowed_slots, max_seconds=max_seconds)),
        "tail_trim_policy": "verified_idle_tail_only",
        "speech_capacity_rule": "Plan speech below about 14.2s inside a 15s request; never cut a word.",
    }
    payload["duration_plan_digest"] = canonical_digest(payload)
    return payload, scripts
