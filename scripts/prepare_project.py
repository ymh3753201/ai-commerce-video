#!/usr/bin/env python3
"""Prepare an ai-commerce-video project folder and generation plan."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import time
from pathlib import Path

from _common import ScriptError, get_model_config, is_url, load_config, local_asset_digest, model_supports_reference_images, prompt_limits, sanitize_name, write_json
from duration_planning import build_duration_plan, build_script_boundary, estimate_spoken_seconds
from subtitle_policy import enabled_subtitle_contract_errors, subtitle_plan_from
from subtitle_profiles import resolve_subtitle_profile


SPEAKER_MODES = ("digital-human-spoken", "voiceover", "silent-captions")
PRODUCT_MOTION_POLICIES = ("static-inanimate", "demonstrated-function", "live-subject", "software-screen", "liquid-food")
CREATIVE_VARIANTS = (
    "commerce_direct",
    "story_reversal",
    "hybrid",
    "ugc_review",
    "comparison_test",
    "lifestyle_seed",
    "premium_brand",
    "feature_demo",
    "unboxing",
    "live_shopping_teaser",
    "retargeting_offer",
)
COMMERCE_SCENARIOS = (
    "auto",
    "feature_demo",
    "product_detail_page",
    "ugc_review",
    "unboxing",
    "before_after",
    "comparison_test",
    "pain_solution",
    "lifestyle_seed",
    "premium_brand",
    "live_shopping_teaser",
    "retargeting_offer",
    "new_launch",
)
CLAIM_RISK_LEVELS = ("auto", "low", "medium", "high")
REFERENCE_STRATEGIES = (
    "auto",
    "single_source_frame",
    "storyboard_sheet_reference",
    "per_segment_source_frames",
    "multi_reference_commercial",
    "multi_reference_storyboard",
)
SEGMENT_STRATEGIES = (
    "auto",
    "single_clip",
    "split_by_duration",
    "per_scene_segments",
    "stitch_segments",
)
VIDEO_SOURCE_ROLE_PRIORITY = (
    "video_source",
    "final_source",
    "final_frame",
    "first_frame",
    "hero_frame",
    "presenter_product",
    "product_presenter",
)
PLAN_SCHEMA_VERSION = 3
PROMPT_COMPILER_VERSION = "director-commerce-v8"
PROMPT_ARCHITECTURE = "universal-product-director-v4"
CAMERA_MOVES = (
    "push_in", "pull_back", "pan", "tilt", "orbit", "track", "locked_macro", "static",
    "crane", "pedestal", "handheld_follow", "dolly_zoom", "zoom", "whip_pan",
)
SHOT_MODES = ("commercial_montage", "continuous_sequence")
AD_STYLE_TYPES = ("cinematic_product_hero", "use_demo", "lifestyle", "unboxing_macro", "ugc_spoken", "before_after")
TALENT_PRESENCE_VALUES = ("none", "hands_only", "presenter")
GENDER_VALUES = ("female", "male", "unspecified", "not_applicable")
SOUND_DESIGN_MODES = ("layered_native", "ambience_led", "voice_only")
PRESET_VOICE_PROFILES = {
    "altair": "premium advertising, luxury beauty, fragrance and cinematic brand films",
    "carina": "warm wellness, care and calm explanatory delivery",
    "ara": "natural lifestyle, creator-style and approachable social commerce",
    "rigel": "clear technology, feature demonstration and confident explanation",
    "zenith": "direct-response retail, urgency and concise commerce calls to action",
    "eve": "balanced general commercial narration",
}
FORBIDDEN_UNVERIFIED_MECHANISMS = [
    "dropper", "pump", "sprayer", "button", "port", "hinge", "closure", "opening method", "detachable part",
    "滴管", "泵头", "喷嘴", "按钮", "接口", "铰链", "开合结构", "可拆部件",
]
PRODUCT_IDENTITY_EVIDENCE_ROLES = {
    "product_evidence",
    "product_angle",
    "product_detail",
    "product_packaging",
    "product_worn",
    "product_in_use",
    "sku_detail",
}
PRODUCT_DEPENDENT_GENERATED_ROLES = {
    "product",
    "product_detail",
    "presenter",
    "wardrobe",
    "hand_action",
}


PLATFORM_PROFILES = {
    "marketplace_general": {
        "display_name": "Marketplace general",
        "default_aspect_ratio": "9:16",
        "recommended_aspect_ratios": ["9:16", "16:9", "1:1"],
        "recommended_duration_seconds": [15],
        "min_duration_seconds": 6,
        "max_duration_seconds": 45,
        "audio_policy": "audio_supported_but_do_not_depend_on_it",
        "speaker_policy": "allowed",
        "subtitle_required": True,
        "cta_required": True,
        "safe_zone_profile": "center_80_percent",
        "product_exposure_rule": "Show the product clearly in the first 2 seconds and keep it recognizable in every major beat.",
        "cta_rule": "Use one clear shopping CTA that matches the destination.",
        "common_risks": ["vague product claims", "unclear landing destination", "over-stylized visuals that hide product identity"],
        "recommended_structure": "hook, product reveal, key proof, use case, CTA",
        "suitable_variants": ["commerce_direct", "hybrid", "feature_demo", "lifestyle_seed", "retargeting_offer"],
    },
    "tiktok": {
        "display_name": "TikTok / TikTok Shop",
        "default_aspect_ratio": "9:16",
        "recommended_aspect_ratios": ["9:16", "1:1", "16:9"],
        "recommended_duration_seconds": [9, 15],
        "min_duration_seconds": 5,
        "max_duration_seconds": 60,
        "audio_policy": "recommended_with_captions",
        "speaker_policy": "allowed",
        "subtitle_required": True,
        "cta_required": True,
        "safe_zone_profile": "tiktok_in_feed",
        "product_exposure_rule": "Use a strong hook and visible product proof early; keep text, logo, and CTA away from native UI zones.",
        "cta_rule": "Use one action cue such as shop now, learn more, or comment keyword; avoid unsupported clickable symbols in captions.",
        "common_risks": ["hidden CTA under app UI", "weak first-second hook", "claim too strong for social commerce"],
        "recommended_structure": "0-2s strong hook, 2-7s product proof, 7-12s benefit/demo, final CTA",
        "suitable_variants": ["story_reversal", "hybrid", "ugc_review", "lifestyle_seed", "live_shopping_teaser", "retargeting_offer"],
    },
    "tiktok_in_feed": {
        "alias_of": "tiktok",
        "display_name": "TikTok In-Feed",
    },
    "tiktok_shop": {
        "alias_of": "tiktok",
        "display_name": "TikTok Shop",
    },
    "douyin": {
        "display_name": "Douyin / Douyin Shop",
        "default_aspect_ratio": "9:16",
        "recommended_aspect_ratios": ["9:16", "1:1", "16:9"],
        "recommended_duration_seconds": [15],
        "min_duration_seconds": 5,
        "max_duration_seconds": 60,
        "audio_policy": "recommended_with_captions",
        "speaker_policy": "allowed",
        "subtitle_required": True,
        "cta_required": True,
        "safe_zone_profile": "douyin_in_feed",
        "product_exposure_rule": "Use vertical framing, strong opening hook, visible product and seller credibility, readable subtitles, and safe-zone-aware CTA.",
        "cta_rule": "Use platform-native shopping or live-room action language; keep CTA visible above bottom overlays.",
        "common_risks": ["exaggerated efficacy claims", "unsafe demonstrations", "text hidden by shopping anchors"],
        "recommended_structure": "hook, pain point, product demonstration, trust proof, shopping/live CTA",
        "suitable_variants": ["commerce_direct", "story_reversal", "hybrid", "live_shopping_teaser", "retargeting_offer"],
    },
    "douyin_in_feed": {
        "alias_of": "douyin",
        "display_name": "Douyin In-Feed",
    },
    "douyin_shop": {
        "alias_of": "douyin",
        "display_name": "Douyin Shop",
    },
    "xiaohongshu": {
        "display_name": "Xiaohongshu",
        "default_aspect_ratio": "9:16",
        "recommended_aspect_ratios": ["9:16", "3:4", "1:1"],
        "recommended_duration_seconds": [15, 30],
        "min_duration_seconds": 6,
        "max_duration_seconds": 60,
        "audio_policy": "allowed_with_captions",
        "speaker_policy": "allowed_but_authentic",
        "subtitle_required": True,
        "cta_required": True,
        "safe_zone_profile": "xiaohongshu_note",
        "product_exposure_rule": "Present real-feeling use context and avoid over-filtered or fake experience language.",
        "cta_rule": "Use soft seed-and-save action, such as collect, compare, ask, or go to product page.",
        "common_risks": ["fake personal experience", "over-filtered before/after", "absolute efficacy claims", "low-quality clickbait"],
        "recommended_structure": "real scenario hook, experience detail, product reason, soft CTA and compliance reminder",
        "suitable_variants": ["ugc_review", "lifestyle_seed", "unboxing", "premium_brand", "comparison_test"],
    },
    "amazon_sponsored_brands_video": {
        "display_name": "Amazon Sponsored Brands Video",
        "default_aspect_ratio": "16:9",
        "recommended_aspect_ratios": ["16:9", "9:16"],
        "recommended_duration_seconds": [6, 15, 30, 45],
        "min_duration_seconds": 6,
        "max_duration_seconds": 45,
        "audio_policy": "muted_first",
        "speaker_policy": "allowed_but_do_not_depend_on_audio",
        "subtitle_required": True,
        "cta_required": True,
        "safe_zone_profile": "amazon_desktop_mobile_video",
        "product_exposure_rule": "Lead with product and brand clarity; the ad should still work muted and without click-like fake buttons inside the video.",
        "cta_rule": "Use Amazon-compatible CTA language outside fake button shapes.",
        "common_risks": ["letterboxing", "black frames", "audio-dependent message", "click-like CTA button drawn inside video"],
        "recommended_structure": "product/brand opening, feature proof, use case, offer or brand reason, CTA",
        "suitable_variants": ["commerce_direct", "feature_demo", "premium_brand", "comparison_test"],
    },
    "amazon_sponsored_products_video": {
        "display_name": "Amazon Sponsored Products Video",
        "default_aspect_ratio": "16:9",
        "recommended_aspect_ratios": ["16:9"],
        "recommended_duration_seconds": [7, 15, 30],
        "min_duration_seconds": 7,
        "max_duration_seconds": 45,
        "audio_policy": "no_audio",
        "speaker_policy": "avoid_talking_head",
        "subtitle_required": True,
        "cta_required": False,
        "safe_zone_profile": "amazon_product_feature_video",
        "product_exposure_rule": "Focus on product features, benefits, usage, and human interaction; product should occupy roughly half or more of the frame when useful.",
        "cta_rule": "Do not rely on a spoken CTA; the Amazon shopping context supplies the click path.",
        "common_risks": ["talking-head format", "audio-dependent explanation", "explicit off-product branding", "slideshow feel"],
        "recommended_structure": "feature title, product-in-use, benefit close-up, usage proof",
        "suitable_variants": ["feature_demo", "commerce_direct", "comparison_test"],
    },
    "youtube": {
        "display_name": "YouTube / Shorts",
        "default_aspect_ratio": "9:16",
        "recommended_aspect_ratios": ["9:16", "16:9", "1:1"],
        "recommended_duration_seconds": [6, 15, 30],
        "min_duration_seconds": 6,
        "max_duration_seconds": 60,
        "audio_policy": "recommended_with_text_support",
        "speaker_policy": "allowed",
        "subtitle_required": True,
        "cta_required": True,
        "safe_zone_profile": "youtube_universal_safe_zone",
        "product_exposure_rule": "Apply YouTube ABCD: Attention, Branding, Connection, Direction; keep product/logo/supers inside safe zones.",
        "cta_rule": "End with a clear direction such as shop, learn, compare, or subscribe depending on campaign goal.",
        "common_risks": ["slow opening", "late branding", "unclear direction", "important text outside universal safe zone"],
        "recommended_structure": "Attention, Branding, Connection, Direction",
        "suitable_variants": ["premium_brand", "feature_demo", "lifestyle_seed", "commerce_direct", "retargeting_offer"],
    },
    "youtube_shorts": {
        "alias_of": "youtube",
        "display_name": "YouTube Shorts",
    },
    "meta_reels": {
        "display_name": "Meta / Instagram Reels",
        "default_aspect_ratio": "9:16",
        "recommended_aspect_ratios": ["9:16", "4:5", "1:1"],
        "recommended_duration_seconds": [6, 15, 30],
        "min_duration_seconds": 3,
        "max_duration_seconds": 90,
        "audio_policy": "recommended_with_captions",
        "speaker_policy": "allowed",
        "subtitle_required": True,
        "cta_required": True,
        "safe_zone_profile": "meta_reels",
        "product_exposure_rule": "Design for vertical feed attention and keep text/logo/CTA away from top, bottom, and side UI overlays.",
        "cta_rule": "Use one conversion action aligned to the campaign goal.",
        "common_risks": ["CTA hidden by Reels UI", "text too low", "creative not native to vertical feed"],
        "recommended_structure": "thumb-stopping hook, product proof, social/lifestyle reason, CTA",
        "suitable_variants": ["ugc_review", "lifestyle_seed", "premium_brand", "retargeting_offer", "hybrid"],
    },
    "instagram_reels": {
        "alias_of": "meta_reels",
        "display_name": "Instagram Reels",
    },
    "shopify_product_page": {
        "display_name": "Independent site / Shopify product page video",
        "default_aspect_ratio": "16:9",
        "recommended_aspect_ratios": ["16:9", "1:1", "9:16"],
        "recommended_duration_seconds": [15, 30, 45],
        "min_duration_seconds": 6,
        "max_duration_seconds": 90,
        "audio_policy": "optional_do_not_depend_on_it",
        "speaker_policy": "allowed",
        "subtitle_required": True,
        "cta_required": True,
        "safe_zone_profile": "product_page_safe_margins",
        "product_exposure_rule": "Prioritize product detail, use cases, scale, materials, shipping/trust proof, and compatibility.",
        "cta_rule": "CTA should match the shop destination, such as add to cart, view options, or choose size.",
        "common_risks": ["missing product detail", "unclear variant or size", "too much social-style story for a product page"],
        "recommended_structure": "hero product, feature demo, detail close-up, use case, buying confidence, CTA",
        "suitable_variants": ["feature_demo", "commerce_direct", "unboxing", "premium_brand"],
    },
    "independent_site": {
        "alias_of": "shopify_product_page",
        "display_name": "Independent site",
    },
}


def safe_asset_folder(name: str) -> str:
    cleaned = sanitize_name(name or "reference")
    return cleaned or "reference"


def copy_or_record_asset(product_image: str, assets_dir: Path, folder: str = "product") -> dict:
    if is_url(product_image):
        return {"kind": "url", "value": product_image}
    src = Path(product_image).expanduser().resolve()
    if not src.exists():
        raise ScriptError(f"Product image not found: {src}")
    dest = assets_dir / safe_asset_folder(folder) / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return {"kind": "file", "value": str(dest)}


def parse_reference(value: str) -> tuple[str, str]:
    if "=" in value:
        role, raw = value.split("=", 1)
        return role.strip() or "reference", raw.strip()
    return "reference", value.strip()


def copy_or_record_reference(value: str, assets_dir: Path, index: int) -> dict:
    role, raw = parse_reference(value)
    asset = copy_or_record_asset(raw, assets_dir / "references", folder=role)
    asset["role"] = role
    asset["id"] = f"ref_{index:02d}"
    return asset


def copy_or_record_generated_reference(value: str, assets_dir: Path, index: int) -> dict:
    role, raw = parse_reference(value)
    asset = copy_or_record_asset(raw, assets_dir / "generated_references", folder=role)
    asset["role"] = role
    asset["id"] = f"generated_ref_{index:02d}"
    asset["provenance"] = "generated_from_approved_visual_plan"
    asset["provider_upload_allowed"] = True
    asset["fact_source"] = "approved_stage_1_plan_plus_user_input_evidence"
    asset["mechanism_lock"] = "show_only_product_mechanisms_visible_in_or_explicitly_supported_by_input_evidence"
    asset["forbidden_inventions"] = list(FORBIDDEN_UNVERIFIED_MECHANISMS)
    asset["multimodal_qc"] = {
        "required": False,
        "checks": ["same_sku_identity", "packaging_and_logo_consistency", "no_unsupported_mechanism_or_prop"],
        "status": "advisory_before_stage_2_confirmation",
    }
    asset["multimodal_qc_result"] = {
        "status": "not_required",
        "reviewer": "stage_2_user_confirmation",
        "note": "Optional AI consistency note; the user's Stage 2 review of the actual generated image is the approval gate",
    }
    return asset


def copy_or_record_product_evidence(value: str, assets_dir: Path, index: int) -> dict:
    folder = "product" if index == 1 else f"product-view-{index:02d}"
    asset = copy_or_record_asset(value, assets_dir, folder=folder)
    asset.update({
        "id": "input_evidence_product" if index == 1 else f"input_evidence_product_{index:02d}",
        "role": "product_evidence",
        "evidence_roles": ["product_identity", "primary_view" if index == 1 else "additional_view"],
        "product_evidence_index": index,
        "provenance": "user_supplied_input_evidence",
    })
    return asset


def resolve_product_identity_evidence(input_evidence_assets: list[dict], brief_data: dict) -> list[dict]:
    visual = brief_data.get("visual_design") if isinstance(brief_data.get("visual_design"), dict) else {}
    explicit_ids = visual.get("product_identity_evidence_asset_ids") or brief_data.get(
        "product_identity_evidence_asset_ids"
    ) or []
    lookup = {
        str(asset.get("id")): asset
        for asset in input_evidence_assets
        if str(asset.get("id") or "").strip()
    }
    if explicit_ids:
        ordered_ids = []
        for value in explicit_ids:
            asset_id = str(value).strip()
            if asset_id and asset_id not in ordered_ids:
                ordered_ids.append(asset_id)
        missing = [asset_id for asset_id in ordered_ids if asset_id not in lookup]
        if missing:
            raise ScriptError(
                "visual_design.product_identity_evidence_asset_ids contains unknown input evidence IDs: "
                f"{missing}"
            )
    else:
        ordered_ids = []
        for asset in input_evidence_assets:
            asset_id = str(asset.get("id") or "").strip()
            role = str(asset.get("role") or "").strip().lower().replace("-", "_")
            evidence_roles = {
                str(value).strip().lower().replace("-", "_")
                for value in (asset.get("evidence_roles") or [])
            }
            if asset_id and (
                asset_id.startswith("input_evidence_product")
                or role in PRODUCT_IDENTITY_EVIDENCE_ROLES
                or "product_identity" in evidence_roles
            ):
                ordered_ids.append(asset_id)
    if not ordered_ids:
        raise ScriptError("At least one product identity evidence asset is required")
    resolved = []
    for ordinal, asset_id in enumerate(ordered_ids, start=1):
        item = dict(lookup[asset_id])
        item["identity_evidence_order"] = ordinal
        item["identity_role"] = "same_sku_product_identity"
        item["sha256"] = local_asset_digest(item)
        resolved.append(item)
    return resolved


def generated_reference_requires_product_identity(role: str, planned: dict) -> bool:
    if "product_identity_required" in planned:
        return bool(planned.get("product_identity_required"))
    normalized_role = role.strip().lower().replace("-", "_")
    return normalized_role in PRODUCT_DEPENDENT_GENERATED_ROLES or normalized_role.startswith(
        "beat_keyframe"
    )


def apply_generated_reference_metadata(
    generated_references: list[dict],
    input_evidence_assets: list[dict],
    product_identity_evidence: list[dict],
    brief_data: dict,
) -> None:
    """Bind generated controls to concrete evidence and the actual multimodal review."""
    visual = brief_data.get("visual_design") if isinstance(brief_data.get("visual_design"), dict) else {}
    planned_items = visual.get("reference_plan") or brief_data.get("reference_plan") or []
    planned_by_role = {
        str(item.get("role") or "reference").strip().lower(): item
        for item in planned_items
        if isinstance(item, dict)
    }
    default_fact_ids = [
        str(asset.get("id"))
        for asset in input_evidence_assets
        if str(asset.get("id") or "").strip()
    ]
    evidence_by_id = {
        str(asset.get("id")): asset
        for asset in input_evidence_assets
        if str(asset.get("id") or "").strip()
    }
    product_identity_ids = [str(asset.get("id")) for asset in product_identity_evidence]
    for asset in generated_references:
        role = str(asset.get("role") or "reference").strip().lower()
        planned = planned_by_role.get(role, {})
        product_identity_required = generated_reference_requires_product_identity(role, planned)
        declared_generation_ids = planned.get("generation_input_asset_ids") or planned.get(
            "imagegen_input_asset_ids"
        )
        requested_generation_ids = [
            str(value).strip()
            for value in (declared_generation_ids or [])
            if str(value).strip()
        ]
        unknown_generation_ids = [
            asset_id for asset_id in requested_generation_ids if asset_id not in evidence_by_id
        ]
        if unknown_generation_ids:
            raise ScriptError(
                f"visual_design.reference_plan role {role!r} cites unknown generation input asset IDs: "
                f"{unknown_generation_ids}"
            )
        generation_inputs = [evidence_by_id[asset_id] for asset_id in requested_generation_ids]
        fact_ids = [
            str(value).strip()
            for value in (
                planned.get("fact_source_asset_ids")
                or requested_generation_ids
                or default_fact_ids
            )
            if str(value).strip()
        ]
        observed = [
            str(value).strip()
            for value in (planned.get("observed_mechanisms") or planned.get("supported_mechanisms") or [])
            if str(value).strip()
        ]
        asset["fact_source"] = planned.get("fact_source") or "input_evidence_assets"
        asset["fact_source_asset_ids"] = fact_ids
        asset["product_identity_required"] = product_identity_required
        asset["product_identity_evidence_asset_ids"] = list(product_identity_ids)
        asset["generation_input_policy"] = (
            "all_relevant_product_identity_evidence"
            if product_identity_required
            else planned.get("generation_input_policy") or "role_relevant_evidence_only"
        )
        asset["generation_input_asset_ids"] = requested_generation_ids
        asset["generation_input_paths"] = [asset_identity(item) for item in generation_inputs]
        asset["generation_input_sha256"] = [local_asset_digest(item) for item in generation_inputs]
        asset["generation_input_records"] = [
            {
                "asset_id": item.get("id"),
                "role": item.get("role"),
                "value": asset_identity(item),
                "sha256": local_asset_digest(item),
            }
            for item in generation_inputs
        ]
        asset["generation_input_record_status"] = (
            "recorded"
            if requested_generation_ids
            else (
                "missing_multi_product_input_record"
                if product_identity_required and len(product_identity_ids) > 1
                else "no_reference_input_recorded"
            )
        )
        asset["mechanism_lock"] = planned.get("mechanism_lock") or asset["mechanism_lock"]
        asset["mechanism_contract"] = {
            "observed": observed,
            "allow_only_observed_or_explicit": True,
            "unsupported_inventions_forbidden": True,
        }
        asset["forbidden_inventions"] = list(
            planned.get("forbidden_inventions") or asset["forbidden_inventions"]
        )
        if isinstance(planned.get("multimodal_qc"), dict):
            asset["multimodal_qc"] = dict(planned["multimodal_qc"])
        if isinstance(planned.get("multimodal_qc_result"), dict):
            asset["multimodal_qc_result"] = dict(planned["multimodal_qc_result"])


def parse_segment_source(value: str, default_index: int) -> tuple[int, str]:
    if "=" not in value:
        return default_index, value.strip()
    key, raw = value.split("=", 1)
    key = key.strip().lower()
    raw = raw.strip()
    match = re.search(r"(\d+)$", key)
    if not match:
        raise ScriptError(f"Invalid segment source key: {key!r}. Use shot_01=<path> or 1=<path>.")
    return int(match.group(1)), raw


def copy_or_record_segment_source(value: str, assets_dir: Path, default_index: int) -> dict:
    index, raw = parse_segment_source(value, default_index)
    asset = copy_or_record_asset(raw, assets_dir / "segment_sources", folder=f"shot_{index:02d}")
    asset["role"] = "segment_source"
    asset["id"] = f"segment_source_{index:02d}"
    asset["shot_id"] = f"shot_{index:02d}"
    asset["segment_index"] = index
    asset["selected_as"] = "video_source"
    return asset


def coerce_choice(value: str, choices: tuple[str, ...], field: str) -> str:
    normalized = (value or "").strip()
    if normalized not in choices:
        raise ScriptError(f"Invalid {field}: {value!r}. Expected one of: {', '.join(choices)}")
    return normalized


def normalize_brief(raw: dict) -> dict:
    """Adapt the public brief template to the flat internal planning contract."""
    if not isinstance(raw, dict):
        raise ScriptError("Project brief must be a JSON object")
    brief = dict(raw)
    product = raw.get("product") if isinstance(raw.get("product"), dict) else {}
    brief["product_category"] = brief.get("product_category") or product.get("category") or ""
    brief["product_name"] = brief.get("product_name") or product.get("name") or ""
    brief["product_price"] = brief.get("product_price") or product.get("price") or ""
    selling_points = brief.get("selling_points") or product.get("selling_points") or []
    brief["selling_points"] = [selling_points] if isinstance(selling_points, str) else list(selling_points)
    brief["cta_text"] = brief.get("cta_text") or brief.get("cta") or ""
    brief["visual_direction"] = brief.get("visual_direction") or brief.get("prompt") or ""
    brief["spoken_script"] = brief.get("spoken_script") or brief.get("presenter_script") or brief.get("script") or ""
    return brief


def normalize_key(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def platform_profile(platform: str | None, placement: str | None) -> tuple[str, dict]:
    platform_key = normalize_key(platform) or "marketplace_general"
    placement_key = normalize_key(placement)
    candidates = []
    if platform_key and placement_key:
        candidates.append(f"{platform_key}_{placement_key}")
    if placement_key:
        candidates.append(placement_key)
    candidates.append(platform_key)
    candidates.append("marketplace_general")
    for key in candidates:
        profile = PLATFORM_PROFILES.get(key)
        if profile:
            alias = profile.get("alias_of")
            if alias:
                base = dict(PLATFORM_PROFILES[alias])
                base.update({k: v for k, v in profile.items() if k != "alias_of"})
                return key, base
            return key, dict(profile)
    return "marketplace_general", dict(PLATFORM_PROFILES["marketplace_general"])


def scenario_from_variant(creative_variant: str) -> str:
    mapping = {
        "ugc_review": "ugc_review",
        "comparison_test": "comparison_test",
        "lifestyle_seed": "lifestyle_seed",
        "premium_brand": "premium_brand",
        "feature_demo": "feature_demo",
        "unboxing": "unboxing",
        "live_shopping_teaser": "live_shopping_teaser",
        "retargeting_offer": "retargeting_offer",
        "story_reversal": "pain_solution",
        "hybrid": "pain_solution",
    }
    return mapping.get(creative_variant, "feature_demo")


def build_platform_contract(
    platform: str,
    placement: str,
    profile_key: str,
    profile: dict,
    duration: int,
    aspect_ratio: str,
    cta_type: str,
    safe_zone_profile: str,
    subtitle_style: str,
) -> dict:
    return {
        "rules_version": "2026-07-15",
        "verified_at": "2026-07-15",
        "source_reference": "references/platform-requirements.md",
        "platform": platform,
        "placement": placement,
        "profile_key": profile_key,
        "display_name": profile.get("display_name", platform),
        "recommended_aspect_ratios": profile.get("recommended_aspect_ratios", []),
        "default_aspect_ratio": profile.get("default_aspect_ratio"),
        "actual_aspect_ratio": aspect_ratio,
        "recommended_duration_seconds": profile.get("recommended_duration_seconds", []),
        "min_duration_seconds": profile.get("min_duration_seconds"),
        "max_duration_seconds": profile.get("max_duration_seconds"),
        "actual_duration_seconds": duration,
        "audio_policy": profile.get("audio_policy"),
        "speaker_policy": profile.get("speaker_policy"),
        "subtitle_required": bool(profile.get("subtitle_required")),
        "subtitle_style": subtitle_style,
        "cta_required": bool(profile.get("cta_required")),
        "cta_type": cta_type,
        "cta_rule": profile.get("cta_rule"),
        "safe_zone_profile": safe_zone_profile,
        "product_exposure_rule": profile.get("product_exposure_rule"),
        "common_risks": profile.get("common_risks", []),
        "recommended_structure": profile.get("recommended_structure"),
        "suitable_variants": profile.get("suitable_variants", []),
        "source_note": "Platform rules are a planning snapshot. Recheck the live ad manager or platform policy before publishing.",
    }


def build_scenario_contract(commerce_scenario: str, creative_variant: str, platform_contract: dict) -> dict:
    scenario = commerce_scenario if commerce_scenario != "auto" else scenario_from_variant(creative_variant)
    rules = {
        "feature_demo": {
            "structure": "problem or need, feature demonstration, close-up proof, result, CTA",
            "image_needs": ["product hero", "hands/use close-up", "detail reference", "final video source"],
            "risk_control": "Show real product operation only; do not exaggerate functions beyond proof.",
        },
        "product_detail_page": {
            "structure": "hero, scale/material detail, usage, variant or package proof, buying confidence",
            "image_needs": ["clean hero", "detail macro", "usage scene", "size/scale reference"],
            "risk_control": "Avoid social-only jokes that distract from product-page information.",
        },
        "ugc_review": {
            "structure": "buyer-style hook, real-feeling use experience, one or two proof details, honest limitation if useful, CTA",
            "image_needs": ["buyer/presenter reference", "usage scene", "product detail", "caption-safe source frame"],
            "risk_control": "Do not fake medical results, fake personal identity, or unsupported testimonial claims.",
        },
        "unboxing": {
            "structure": "package reveal, first impression, product detail, setup/use, CTA",
            "image_needs": ["package", "unboxing hand scene", "product hero", "detail close-up"],
            "risk_control": "Keep packaging and included accessories accurate.",
        },
        "before_after": {
            "structure": "before state, product use, after state, proof or caveat, CTA",
            "image_needs": ["before scene", "use scene", "after scene", "disclaimer-safe caption"],
            "risk_control": "Do not imply guaranteed results; use realistic, evidence-backed comparison.",
        },
        "comparison_test": {
            "structure": "neutral test setup, objective feature comparison, product advantage, fair CTA",
            "image_needs": ["side-by-side setup", "test detail", "product hero", "result caption"],
            "risk_control": "Avoid naming or attacking competitors unless the user provides substantiated legal-safe evidence.",
        },
        "pain_solution": {
            "structure": "pain point, tension or failed workaround, product solution, relief, CTA",
            "image_needs": ["pain scene", "product solution scene", "presenter/product source", "storyboard if multi-scene"],
            "risk_control": "Keep the pain point common and safe; do not shame users.",
        },
        "lifestyle_seed": {
            "structure": "aspirational daily scene, product naturally present, benefit detail, soft CTA",
            "image_needs": ["lifestyle scene", "product-in-scene", "style reference", "caption-safe source frame"],
            "risk_control": "Do not hide the product inside mood shots; keep seeded experience plausible.",
        },
        "premium_brand": {
            "structure": "brand texture, design/material detail, controlled product motion, concise value line, elegant CTA",
            "image_needs": ["premium hero", "material macro", "brand scene", "clean typography-safe frame"],
            "risk_control": "Avoid cheap discount language, noisy stickers, and overpromising luxury claims.",
        },
        "live_shopping_teaser": {
            "structure": "live-room reason, hero product, limited offer or demo preview, time/action CTA",
            "image_needs": ["presenter/live-room frame", "product hero", "offer-safe caption", "CTA-safe source"],
            "risk_control": "Offers must be accurate; avoid false scarcity.",
        },
        "retargeting_offer": {
            "structure": "remind viewed benefit, handle objection, offer or guarantee, urgent but honest CTA",
            "image_needs": ["product hero", "offer caption", "trust proof", "checkout/landing context"],
            "risk_control": "Do not use misleading countdowns, fake discounts, or unsupported guarantees.",
        },
        "new_launch": {
            "structure": "newness hook, differentiator, early proof, launch offer or sign-up CTA",
            "image_needs": ["launch hero", "feature reveal", "brand/product detail", "CTA-safe frame"],
            "risk_control": "Do not claim first/best/new unless supported.",
        },
    }
    rule = rules.get(scenario, rules["feature_demo"])
    return {
        "commerce_scenario": scenario,
        "creative_variant": creative_variant,
        "fit_platforms": [platform_contract.get("display_name")],
        "typical_structure": rule["structure"],
        "storyboard_logic": rule["structure"],
        "copy_style": "Match platform tone while keeping claims evidence-safe and CTA visible.",
        "image_needs": rule["image_needs"],
        "reference_needs": rule["image_needs"],
        "risk_control": rule["risk_control"],
    }


def infer_claim_risk(value: str, product_category: str) -> str:
    requested = (value or "auto").strip().lower()
    if requested in {"low", "medium", "high"}:
        return requested
    category = (product_category or "").lower()
    high_terms = ("medical", "health", "supplement", "medicine", "drug", "baby", "infant", "pregnancy", "skincare", "cosmetic", "weight loss")
    medium_terms = ("food", "pet", "fitness", "electronics", "home appliance", "beauty", "母婴", "保健", "美妆", "食品", "宠物", "健身", "医疗")
    if any(term in category for term in high_terms):
        return "high"
    if any(term in category for term in medium_terms):
        return "medium"
    return "low"


def build_compliance_contract(claim_risk: str, product_category: str, marketplace_locale: str) -> dict:
    risk = infer_claim_risk(claim_risk, product_category)
    guardrails = {
        "low": ["Avoid impossible claims.", "Keep discounts, materials, and dimensions consistent with supplied product information."],
        "medium": ["Use evidence-backed feature language.", "Avoid guaranteed results and unfair before/after exaggeration."],
        "high": [
            "Avoid diagnosis, treatment, cure, permanent result, guaranteed safety, and medical-grade claims unless the user supplies approved evidence.",
            "Use soft benefit wording and add disclaimers when the category or platform requires them.",
            "Before/after claims need realistic context, evidence, and no manipulated visuals.",
        ],
    }
    return {
        "claim_risk": risk,
        "product_category": product_category,
        "marketplace_locale": marketplace_locale,
        "restricted_claims": guardrails[risk],
        "evidence_required_for": ["efficacy", "health or safety", "before/after", "professional or certification", "price/discount/availability"],
        "disclaimer_rule": "Add a short disclaimer when product category, claim strength, or platform policy requires it; do not bury it outside the safe zone.",
        "authenticity_rule": "UGC and review-style ads must sound like a real experience, but must not invent unverifiable personal results or fake authority.",
    }


def build_model_capability_contract(model: dict) -> dict:
    payload_defaults = model.get("payload_defaults") if isinstance(model.get("payload_defaults"), dict) else {}
    supports_audio = model.get("supports_audio")
    if supports_audio is None:
        supports_audio = bool(payload_defaults.get("generate_audio")) or model.get("provider") in {"mikuapi.org", "119337", "fal_queue"}
    return {
        "model_key": model.get("key"),
        "model": model.get("model"),
        "official_model_family": model.get("official_model_family") or model.get("model"),
        "provider_model_alias": model.get("provider_model_alias") or model.get("model"),
        "provider_contract_version": model.get("provider_contract_version") or "",
        "provider": model.get("provider"),
        "input_mode": model.get("input_mode") or model.get("mode"),
        "supports_text_to_video": bool(model.get("supports_text_to_video")),
        "requires_image": bool(model.get("requires_image", False)),
        "supports_multiple_references": model_supports_reference_images(model),
        "max_reference_images": int(model.get("max_reference_images") or 0),
        "reference_index_base": int(model.get("reference_index_base", 1)),
        "reference_mode_exclusive_with_source": bool(model.get("reference_mode_exclusive_with_source")),
        "reference_asset_policy": model.get("reference_asset_policy") or "provider_specific",
        "require_generated_video_references": bool(model.get("require_generated_video_references")),
        "require_generated_product_reference": bool(model.get("require_generated_product_reference")),
        "require_product_anchor_reference": bool(model.get("require_product_anchor_reference")),
        "product_anchor_first": bool(model.get("product_anchor_first")),
        "product_anchor_source": model.get("product_anchor_source") or "provider_specific",
        "require_local_generated_references": bool(model.get("require_local_generated_references")),
        "allow_storyboard_reference_upload": bool(model.get("allow_storyboard_reference_upload", True)),
        "raw_product_assets_are_provider_inputs": bool(model.get("raw_product_assets_are_provider_inputs", True)),
        "raw_non_product_assets_are_provider_inputs": bool(model.get("raw_non_product_assets_are_provider_inputs", True)),
        "source_image_field": model.get("source_image_field", "image"),
        "reference_field": model.get("reference_field", "reference_images"),
        "reference_payload_format": model.get("reference_payload_format", "url_objects"),
        "min_duration_seconds": int(model.get("min_duration_seconds", 1)),
        "max_duration_seconds": int(model.get("max_duration_seconds", 15)),
        "official_max_duration_seconds": int(
            (model.get("official_capabilities") or {}).get("max_duration_seconds")
            or model.get("max_duration_seconds", 15)
        ),
        "planning_max_duration_seconds": int(
            model.get("planning_max_duration_seconds") or model.get("max_duration_seconds", 15)
        ),
        "duration_reliability_status": model.get("duration_reliability_status") or "provider_specific",
        "max_duration_multi_reference_seconds": model.get("max_duration_multi_reference_seconds"),
        "allowed_duration_seconds": [int(value) for value in (model.get("allowed_duration_seconds") or [])],
        "allowed_multi_reference_duration_seconds": [
            int(value) for value in (model.get("allowed_multi_reference_duration_seconds") or [])
        ],
        "billing_unit": model.get("billing_unit") or "provider_defined",
        "cost_guard_unit": model.get("cost_guard_unit") or "provider_submission",
        "max_paid_submissions_per_shot": int(model.get("max_paid_submissions_per_shot") or 1),
        "max_prompt_chars": model.get("max_prompt_chars"),
        "prompt_budget_chars": model.get("prompt_budget_chars"),
        "provider_documented_max_prompt_chars": model.get("provider_documented_max_prompt_chars"),
        "adapter_max_prompt_chars": model.get("adapter_max_prompt_chars", model.get("max_prompt_chars")),
        "workflow_prompt_budget_chars": model.get("workflow_prompt_budget_chars", model.get("prompt_budget_chars")),
        "prompt_limit_source": model.get("prompt_limit_source") or "workflow_and_adapter_configuration",
        "prompt_compiler": PROMPT_COMPILER_VERSION,
        "reference_index_contract_source": model.get("reference_index_contract_source") or "provider_route_configuration",
        "supports_video_extension": bool(model.get("supports_video_extension", False)),
        "video_extension_status": model.get("video_extension_status") or "not_configured",
        "supports_audio": bool(supports_audio),
        "supports_native_speech_output": bool(
            model.get("supports_native_speech_output", model.get("supports_lip_sync", supports_audio))
        ),
        "native_sound_design_prompting": model.get("native_sound_design_prompting") or "provider_specific",
        "native_sound_layers_guaranteed": bool(model.get("native_sound_layers_guaranteed", False)),
        "native_sound_delivery_strategy": model.get("native_sound_delivery_strategy") or "prompt_directed_best_effort",
        "native_cross_clip_audio_state_shared": bool(model.get("native_cross_clip_audio_state_shared", False)),
        "exact_score_continuity_requires_local_post_mix": bool(
            model.get("exact_score_continuity_requires_local_post_mix", True)
        ),
        "reference_audio_field": model.get("reference_audio_field"),
        "supports_preset_voice_references": bool(model.get("supports_preset_voice_references")),
        "max_reference_audios": int(model.get("max_reference_audios") or 0),
        "approved_preset_voice_ids": list(
            model.get("approved_preset_voice_ids") or model.get("known_preset_voice_ids") or []
        ),
        "voices_path": model.get("voices_path"),
        "voice_roster_policy": model.get("voice_roster_policy") or "provider_specific",
        "default_voice_policy": model.get("default_voice_policy") or "provider_specific",
        "supports_custom_voice_file_reference": bool(model.get("supports_custom_voice_file_reference")),
        "supports_voice_conditioned_speech": bool(
            model.get("supports_voice_conditioned_speech", False)
        ),
        "frame_exact_lip_sync_guaranteed": bool(model.get("frame_exact_lip_sync_guaranteed", False)),
        "supports_timecoded_story_beats": bool(
            model.get("supports_timecoded_story_beats", model.get("supports_multi_segment_generation", True))
        ),
        "official_capabilities": model.get("official_capabilities") or {},
        "route_verified_capabilities": model.get("route_verified_capabilities") or {},
        "capability_source": "model config with official capability and route-verification layers",
    }


def sanitize_prompt_text(prompt: str, speaker_mode: str, product_motion_policy: str) -> str:
    text = (prompt or "").strip()
    if speaker_mode == "digital-human-spoken":
        replacements = [
            (r"\bChinese voiceover and captions\b", "Chinese on-camera presenter speech"),
            (r"\bvoiceover and captions\b", "on-camera presenter speech"),
            (r"\bvoiceover/captions\b", "on-camera presenter speech"),
            (r"\boff-screen voiceover\b", "on-camera presenter speech"),
            (r"\bvoiceover\b", "on-camera presenter speech"),
            (r"\bnarrator\b", "presenter"),
        ]
        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(
        r"\b(?:add|include|show|display|use|with)?\s*(?:subtitles?|captions?|lower[- ]thirds?|text overlays?)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\b(?:srt|vtt)\b|中英双语字幕|中文字幕|英文字幕|字幕", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text).strip(" ,;/")
    if product_motion_policy == "static-inanimate":
        replacements = [
            (r"\bsoft product motion\b", "soft camera movement around the product"),
            (r"\bsubtle product motion\b", "subtle camera movement around the product"),
            (r"\bthe product moves\b", "the presenter moves the product by hand"),
        ]
        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(
        r"\bClean full-screen commercial footage only\s*:\s*[^.]*\.",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text


def strip_provider_caption_terms(text: str) -> str:
    """Keep all subtitle concepts out of the Provider-facing prompt, even as negative instructions."""
    cleaned = re.sub(
        r"\b(?:subtitles?|captions?|srt|vtt|lower[- ]thirds?|text overlays?)\b|中英双语字幕|中文字幕|英文字幕|字幕",
        "",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\b(no|without)\s*(?:,\s*)+", r"\1 ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:,\s*){2,}", ", ", cleaned)
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def reference_strategy_contract(reference_strategy: str, model: dict) -> str:
    """Keep the detailed reference workflow in the plan, outside the Provider prompt."""
    model_name = model.get("model", "configured video model")
    rules = {
        "per_segment_source_frames": (
            "Each segment uses its own approved first frame and is generated once for later stitching. "
            "Do not upload a storyboard grid as the source image."
        ),
        "storyboard_sheet_reference": (
            "The storyboard controls shot order and rhythm only. Render full-screen video, never the grid itself."
        ),
        "multi_reference_storyboard": (
            "Product, presenter, scene and storyboard references work together. Identity comes from mapped references; "
            "the storyboard controls sequence only."
        ),
        "multi_reference_commercial": (
            "Use a compact, non-conflicting reference set to lock product, presenter, wardrobe, scene and finish by role. "
            "References guide identity and style without forcing the first frame."
        ),
        "single_source_frame": "Use one approved first frame for one continuous segment.",
    }
    rule = rules.get(reference_strategy, rules["single_source_frame"])
    return f"Reference strategy: {reference_strategy} for {model_name}. {rule}"


def creative_variant_contract(creative_variant: str, commerce_platform: str) -> str:
    if creative_variant == "story_reversal":
        return (
            f"Creative variant: story_reversal for {commerce_platform}; use a first-3-second story hook, one conflict or pain point, "
            "a concise reversal, the product as the solution, and a direct CTA. Keep the product visible."
        )
    if creative_variant == "hybrid":
        return (
            f"Creative variant: hybrid for {commerce_platform}; open with a lifestyle/story hook, then direct product proof, "
            "selling points and CTA; product clarity wins over plot complexity."
        )
    if creative_variant == "ugc_review":
        return (
            f"Creative variant: ugc_review buyer-perspective ad for {commerce_platform}; use real-feeling handling, "
            "one or two honest selling points and a clear CTA; invent no testimonial results."
        )
    if creative_variant == "comparison_test":
        return (
            f"Creative variant: comparison_test for {commerce_platform}; use a fair side-by-side of objective features, then product advantage and CTA. "
            "Avoid malicious competitor attacks or unsupported claims."
        )
    if creative_variant == "lifestyle_seed":
        return (
            f"Creative variant: lifestyle_seed for {commerce_platform}; place the visible product in an aspirational but believable daily scenario, "
            "show real experience and lifestyle value, then end with a soft CTA."
        )
    if creative_variant == "premium_brand":
        return (
            f"Creative variant: premium_brand high-end brand ad for {commerce_platform}; emphasize design, material and craftsmanship with clean premium pacing; "
            "do not turn the ad into low-price shouting."
        )
    if creative_variant == "feature_demo":
        return (
            f"Creative variant: feature_demo functional product demonstration for {commerce_platform}; show real use, close-up proof and a concise CTA."
        )
    if creative_variant == "unboxing":
        return (
            f"Creative variant: unboxing first-impression ad for {commerce_platform}; show package reveal, details, first use and a buying reason; invent no included accessories."
        )
    if creative_variant == "live_shopping_teaser":
        return (
            f"Creative variant: live_shopping_teaser for {commerce_platform}; show live-room value, hero product and any verified limited offer, then drive to the live/shop destination."
        )
    if creative_variant == "retargeting_offer":
        return (
            f"Creative variant: retargeting_offer remarketing ad for {commerce_platform}; restate one benefit, answer one likely objection, show verified proof and CTA without fake scarcity."
        )
    return (
        f"Creative variant: commerce_direct conversion-focused product ad for {commerce_platform}; prioritize product exposure, real function, supplied offer, proof and CTA."
    )


def creative_intent_contract(creative_variant: str) -> str:
    recipes = {
        "story_reversal": "hook > conflict > reversal > product solution > CTA",
        "hybrid": "story hook > product proof > CTA",
        "ugc_review": "authentic use > proof > CTA",
        "comparison_test": "fair comparison > proof > CTA",
        "lifestyle_seed": "lifestyle fit > benefit > soft CTA",
        "premium_brand": "design > material > craftsmanship",
        "feature_demo": "feature > real use > close-up proof > CTA",
        "unboxing": "package reveal > detail > first use",
        "live_shopping_teaser": "hero product > verified live value > destination",
        "retargeting_offer": "benefit > objection answer > verified offer > CTA",
        "commerce_direct": "product > proof > buying reason > CTA",
    }
    recipe = recipes.get(creative_variant, "product > proof > CTA")
    return f"Creative intent: {creative_variant}; {recipe}."


def factual_guardrail_contract() -> str:
    return "Facts: use approved facts only; invent no claim/price/result/mechanism."


def select_prompt_voice_description(
    product_category: str,
    creative_variant: str,
    commerce_scenario: str,
    style_type: str,
) -> str:
    """Choose a concise natural-language delivery direction, not a Provider voice ID."""
    context = " ".join((product_category, creative_variant, commerce_scenario, style_type)).lower()
    if any(term in context for term in (
        "premium", "luxury", "skincare", "skin care", "beauty", "cosmetic", "fragrance", "护肤", "美妆", "香水", "高端",
    )):
        return "calm refined Mandarin luxury-ad voice"
    if any(term in context for term in ("wellness", "care", "health", "personal care", "个护", "健康", "护理")):
        return "warm reassuring Mandarin care voice"
    if any(term in context for term in ("ugc", "lifestyle", "creator", "种草", "生活方式")):
        return "natural conversational Mandarin creator voice"
    if any(term in context for term in ("technology", "digital", "software", "appliance", "feature_demo", "数码", "软件", "家电")):
        return "clear concise Mandarin product-demo voice"
    if any(term in context for term in ("retargeting", "commerce_direct", "live_shopping", "促销", "直播")):
        return "confident energetic Mandarin commerce voice"
    return "clear natural Mandarin commercial voice"


def infer_gender(value: str, *, allow_not_applicable: bool = False) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "unspecified"
    female = bool(re.search(r"\b(female|woman|women|girl)\b|女性|女生|女声|女人|女士", text))
    male = bool(re.search(r"\b(male|man|men|boy)\b|男性|男生|男声|男人|男士", text))
    if female and male:
        raise ScriptError("Talent or voice description contains conflicting female and male directions")
    if female:
        return "female"
    if male:
        return "male"
    if allow_not_applicable and text in {"none", "not_applicable", "n/a"}:
        return "not_applicable"
    return "unspecified"


def build_talent_contract(
    brief_data: dict,
    speaker_mode: str,
    seller_persona: str,
    generated_references: list[dict],
) -> dict:
    visual = brief_data.get("visual_design") if isinstance(brief_data.get("visual_design"), dict) else {}
    explicit_presence = str(visual.get("talent_presence") or brief_data.get("talent_presence") or "").strip().lower()
    talent_role = str(visual.get("talent_role") or brief_data.get("talent_role") or "").strip()
    explicit_description = str(
        visual.get("talent_description") or brief_data.get("talent_description") or ""
    ).strip()
    role_text = " ".join([talent_role, explicit_description]).lower()
    reference_roles = {
        str(item.get("role") or "").strip().lower()
        for item in generated_references
        if str(item.get("role") or "").strip()
    }
    if explicit_presence:
        if explicit_presence not in TALENT_PRESENCE_VALUES:
            raise ScriptError(f"talent_presence must be one of: {', '.join(TALENT_PRESENCE_VALUES)}")
        presence = explicit_presence
        source = "approved_visual_plan"
    elif speaker_mode == "digital-human-spoken" or reference_roles.intersection({"presenter", "wardrobe"}):
        presence = "presenter"
        source = "speaker_mode_or_reference_role"
    elif re.search(r"\b(no talent|no person|no people|product[- ]only|without people)\b|不使用人物|人物不出镜|无人|无人物|纯产品", role_text):
        presence = "none"
        source = "approved_talent_role"
    elif "hand_action" in reference_roles or re.search(r"\b(hands? only|hand model)\b|仅手部|只用手|手部", role_text):
        presence = "hands_only"
        source = "approved_talent_role_or_reference"
    elif re.search(r"\b(presenter|model|person|woman|female|man|male)\b|模特|人物|女性|女生|男性|男生", role_text):
        presence = "presenter"
        source = "approved_talent_role"
    else:
        presence = "none"
        source = "safe_product_only_default"

    explicit_gender = str(visual.get("talent_gender") or brief_data.get("talent_gender") or "").strip().lower()
    if explicit_gender and explicit_gender not in GENDER_VALUES:
        raise ScriptError(f"talent_gender must be one of: {', '.join(GENDER_VALUES)}")
    gender = explicit_gender or infer_gender(" ".join([talent_role, explicit_description]))
    if presence != "presenter":
        gender = "not_applicable"
    elif gender == "not_applicable":
        raise ScriptError("A visible presenter cannot use talent_gender=not_applicable")
    return {
        "presence": presence,
        "gender": gender,
        "description": (explicit_description or seller_persona) if presence == "presenter" else talent_role,
        "decision_source": source,
        "presenter_reference_required": presence == "presenter",
        "allowed_visible_human": "none" if presence == "none" else ("hands_only" if presence == "hands_only" else "approved_presenter_only"),
    }


def talent_prompt_instruction(talent_contract: dict, speaker_mode: str, seller_persona: str, has_dialogue: bool) -> str:
    presence = str(talent_contract.get("presence") or "none")
    gender = str(talent_contract.get("gender") or "unspecified")
    if presence == "none":
        speech = "Use off-screen voiceover." if speaker_mode == "voiceover" else ""
        return f"{speech} No person, face, body, hand, or human silhouette appears.".strip()
    if presence == "hands_only":
        speech = "Use off-screen voiceover." if speaker_mode == "voiceover" else ""
        return f"{speech} Show only the approved hands; no face, body, presenter, or human silhouette appears.".strip()
    gender_label = {"female": "adult female", "male": "adult male"}.get(gender, "")
    subject = " ".join(value for value in ["approved", gender_label, seller_persona] if value).strip()
    exclusion = " Do not substitute a presenter of another gender." if gender in {"female", "male"} else ""
    if speaker_mode == "digital-human-spoken" and has_dialogue:
        return f"Only the {subject} may appear and speaks to camera with natural lip sync.{exclusion}".strip()
    if speaker_mode == "digital-human-spoken":
        return f"Only the {subject} may appear and demonstrates silently; use no unscripted dialogue.{exclusion}".strip()
    return f"Use off-screen voiceover. Only the {subject} may appear and demonstrates silently.{exclusion}".strip()


def validate_talent_references(
    talent_contract: dict,
    video_reference_assets: list[dict],
    require_presenter_reference: bool,
) -> None:
    roles = {str(item.get("role") or "").strip().lower() for item in video_reference_assets}
    presence = talent_contract.get("presence")
    if require_presenter_reference and presence == "presenter" and "presenter" not in roles:
        raise ScriptError(
            "The approved visual plan uses a visible presenter, so the Provider Reference Pack must include "
            "one generated presenter control image before Stage 2."
        )
    if presence == "none" and roles.intersection({"presenter", "wardrobe", "hand_action"}):
        raise ScriptError("talent_presence=none conflicts with presenter, wardrobe, or hand_action Provider references")
    if presence == "hands_only" and roles.intersection({"presenter", "wardrobe"}):
        raise ScriptError("talent_presence=hands_only conflicts with presenter or wardrobe Provider references")


def remove_manual_structural_blocks(text: str) -> tuple[str, dict]:
    """Remove user-authored compiler sections so each Provider block is rendered once."""
    cleaned = text or ""
    removed = {"cuts": 0, "sequence": 0, "reference_image_map": 0, "audio": 0}
    patterns = (
        ("audio", r"\bAUDIO\s*:[\s\S]*?(?=\s+(?:Cuts|Sequence|Reference image map|Creative intent|Facts|Clean frame)\s*:|$)"),
        ("reference_image_map", r"\bReference image map\s*:[\s\S]*?(?=\s+(?:Cuts|Sequence|AUDIO|Creative intent|Facts|Clean frame)\s*:|$)"),
        ("sequence", r"\bSequence\s*:[^.。]*(?:[.。]|$)"),
        ("cuts", r"\bCuts\s*:[^.。]*(?:[.。]|$)"),
    )
    for key, pattern in patterns:
        cleaned, count = re.subn(pattern, " ", cleaned, flags=re.IGNORECASE)
        removed[key] += count
    cleaned = re.sub(r"(?:,\s*){2,}", ", ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,;:：。")
    return cleaned, removed


def remove_spoken_script_from_visual(text: str, spoken_script: str) -> tuple[str, int]:
    """Remove exact dialogue copied into visual direction; it is added once by the compiler."""
    speech = spoken_script.strip()
    if not speech:
        return text, 0
    count = text.count(speech)
    cleaned = text.replace(speech, " ")
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"(?:speaks?|says?|dialogue|口播|台词)\s*(?:naturally)?\s*[:：]\s*(?=$|[.;。])", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" ,;:：。"), count


def build_commercial_strategy_contract(brief_data: dict, creative_variant: str, audience: str) -> dict:
    visual = brief_data.get("visual_design") if isinstance(brief_data.get("visual_design"), dict) else {}
    provider_summary_parts = []
    if visual.get("big_idea") or brief_data.get("big_idea"):
        provider_summary_parts.append(f"Big idea={visual.get('big_idea') or brief_data.get('big_idea')}")
    if visual.get("visual_proof") or brief_data.get("visual_proof"):
        provider_summary_parts.append(f"Proof={visual.get('visual_proof') or brief_data.get('visual_proof')}")
    return {
        "single_minded_proposition": visual.get("single_minded_proposition") or brief_data.get("single_minded_proposition") or "make the approved product desirable through one clear truthful reason",
        "audience_tension": visual.get("audience_tension") or brief_data.get("audience_tension") or audience or "the audience wants a clear buying reason without exaggerated selling",
        "visual_proof": visual.get("visual_proof") or brief_data.get("visual_proof") or "recognizable product identity plus one truthful use, material or scale proof",
        "big_idea": visual.get("big_idea") or brief_data.get("big_idea") or creative_variant,
        "emotional_arc": visual.get("emotional_arc") or brief_data.get("emotional_arc") or "attention to belief to desire",
        "talent_role": visual.get("talent_role") or brief_data.get("talent_role") or "appear only when a person improves desire, trust, scale, use proof or emotion",
        "sound_intent": visual.get("sound_intent") or brief_data.get("sound_intent") or "clear commercial voice with restrained product sound",
        "beat_rule": "Use two to four motivated beats; one dominant camera move per beat, with supporting light, liquid, talent and product-handling motion allowed.",
        "commercial_quality_gate": [
            "one memorable big idea organizes the whole ad",
            "the product becomes recognizable before attention decays",
            "each beat changes what the audience sees, believes, or desires",
            "reference images control identity, composition, action, or proof rather than only color",
            "every mechanism, prop, claim, and offer traces to evidence",
            "speech and sound reinforce the final selling payoff",
        ],
        "provider_prompt_summary": "; ".join(provider_summary_parts),
    }


def build_product_director_profile(
    brief_data: dict,
    product_motion_policy: str,
    talent_contract: dict,
    commercial_strategy: dict,
) -> dict:
    """Describe any sellable product through one evidence-led director contract."""
    visual = brief_data.get("visual_design") if isinstance(brief_data.get("visual_design"), dict) else {}
    explicit_form = str(visual.get("product_form") or brief_data.get("product_form") or "").strip().lower()
    explicit_interaction = str(
        visual.get("interaction_mode") or brief_data.get("interaction_mode") or ""
    ).strip().lower()
    explicit_proof = str(visual.get("proof_mode") or brief_data.get("proof_mode") or "").strip().lower()
    explicit_talent_value = str(
        visual.get("talent_value") or brief_data.get("talent_value") or ""
    ).strip().lower()
    form_by_motion = {
        "static-inanimate": "physical_product",
        "demonstrated-function": "functional_physical_product",
        "liquid-food": "fluid_or_consumable_product",
        "software-screen": "digital_interface_or_service",
        "live-subject": "live_subject_product",
    }
    interaction_by_motion = {
        "static-inanimate": "passive_or_handled",
        "demonstrated-function": "demonstrated_real_function",
        "liquid-food": "served_or_used_naturally",
        "software-screen": "human_interface_interaction",
        "live-subject": "natural_live_behavior",
    }
    presence = str(talent_contract.get("presence") or "none")
    if explicit_talent_value:
        talent_value = explicit_talent_value
    elif presence == "presenter":
        talent_value = "desire_trust_scale_or_use_proof"
    elif presence == "hands_only":
        talent_value = "scale_or_use_proof"
    else:
        talent_value = "none_product_led"
    return {
        "architecture": "evidence_driven_category_agnostic",
        "product_form": explicit_form or form_by_motion.get(product_motion_policy, "sellable_product"),
        "interaction_mode": explicit_interaction or interaction_by_motion.get(product_motion_policy, "evidence_defined"),
        "proof_mode": explicit_proof or str(commercial_strategy.get("visual_proof") or "identity_plus_one_truthful_visible_proof"),
        "talent_value": talent_value,
        "fact_scope": "visible_or_user_supplied_facts_only",
        "category_branching_allowed": False,
    }


def compact_render_guardrails(
    speaker_mode: str,
    product_motion_policy: str,
    seller_persona: str,
    has_dialogue: bool,
    talent_contract: dict,
) -> str:
    """Return one small, product-agnostic rendering policy component."""
    parts = ["Clean: no newly generated written or typographic elements; preserve marks."]
    parts.append(talent_prompt_instruction(talent_contract, speaker_mode, seller_persona, has_dialogue))
    if product_motion_policy == "static-inanimate":
        parts.append("The inanimate product never acts alive or self-moves.")
    elif product_motion_policy == "demonstrated-function":
        parts.append("Show only real product function or mechanism.")
    elif product_motion_policy == "live-subject":
        parts.append("Keep live-subject motion natural, safe and realistic.")
    elif product_motion_policy == "software-screen":
        parts.append("Show clear UI interaction; avoid unrelated physical animation.")
    else:
        parts.append("Keep food or liquid motion natural and realistic.")
    return " ".join(parts)


def storyboard_reference_present(references: list[dict]) -> bool:
    return any(str(ref.get("role", "")).lower() in {"storyboard", "storyboard_sheet", "shot_plan"} for ref in references)


def resolve_reference_strategy(value: str | None, model: dict, references: list[dict], segment_sources: list[dict]) -> tuple[str, list[str]]:
    warnings: list[str] = []
    requested = (value or "auto").strip()
    if requested not in REFERENCE_STRATEGIES:
        raise ScriptError(f"Invalid reference_strategy: {value!r}. Expected one of: {', '.join(REFERENCE_STRATEGIES)}")

    if requested == "auto":
        if segment_sources:
            strategy = "per_segment_source_frames"
        elif model_supports_reference_images(model) and storyboard_reference_present(references):
            strategy = "multi_reference_storyboard"
        elif model_supports_reference_images(model):
            strategy = "multi_reference_commercial"
        else:
            strategy = "single_source_frame"
    else:
        strategy = requested

    if strategy == "per_segment_source_frames" and not segment_sources:
        raise ScriptError("reference_strategy per_segment_source_frames requires at least one --segment-source-image.")
    if segment_sources and strategy != "per_segment_source_frames":
        raise ScriptError("--segment-source-image can only be used with reference_strategy per_segment_source_frames or auto.")
    if strategy in {"storyboard_sheet_reference", "multi_reference_storyboard"}:
        if not model_supports_reference_images(model):
            raise ScriptError(
                f"reference_strategy {strategy} requires a model with supports_multiple_references=true. "
                "For a single-image route such as the preserved MikuAPI adapter, use per_segment_source_frames."
            )
        if not storyboard_reference_present(references):
            warnings.append(f"reference_strategy {strategy} selected but no reference role=storyboard was provided.")
        if not bool(model.get("allow_storyboard_reference_upload", True)):
            raise ScriptError(
                "The selected model route treats storyboard/contact sheets as review-only planning assets. "
                "Do not upload them to reference-to-video; use generated element control plates, or switch to "
                "per-segment image-to-video when exact shot starts are required."
            )
    return strategy, warnings


def reference_token(index: int, style: str | None, index_base: int = 1) -> str:
    display_index = index + index_base
    normalized = (style or "angle").strip().lower()
    if normalized in {"seedance_at", "at", "paren_at", "img_at"}:
        return f"@(img{display_index})"
    if normalized in {"at_image", "seedance_image"}:
        return f"@Image{display_index}"
    return f"<IMAGE_{display_index}>"


def reference_role_instruction(role: str) -> str:
    normalized = (role or "reference").strip().lower()
    if normalized == "beat_keyframe" or normalized.startswith("beat_keyframe_"):
        return (
            "guide one approved full-frame beat composition and action only; do not reproduce it as a grid, "
            "caption, or guaranteed exact first frame"
        )
    rules = {
        "product": "lock the approved generated product master derived from user evidence: preserve silhouette, proportions, color, material, packaging, logo and existing marks; never redesign or substitute the SKU",
        "product_detail": "lock the demonstrated product detail; use it for macro proof without changing the SKU",
        "model": "lock presenter identity, face, age range and body proportions",
        "presenter": "lock presenter identity, face, age range and body proportions",
        "wardrobe": "lock the approved clothing, fit, fabric and accessories",
        "scene": "lock location, set design, palette, lighting direction and spatial mood",
        "style": "guide color science, lens language and finish only; never replace product identity",
        "storyboard": "review-only planning asset; do not upload as an element reference unless the selected model contract explicitly supports it",
        "storyboard_sheet": "review-only planning asset; do not upload as an element reference unless the selected model contract explicitly supports it",
        "campaign_preview": "guide the approved campaign composition and commercial finish without forcing a first frame",
    }
    return rules.get(normalized, f"preserve the approved {normalized} identity and use it only for its assigned role")


def asset_identity(asset: dict) -> str:
    return str(asset.get("value") or asset.get("path") or asset.get("url") or "")


def with_role(asset: dict, role: str, asset_id: str) -> dict:
    result = dict(asset)
    result["role"] = role
    result.setdefault("id", asset_id)
    return result


def select_video_source_asset(
    product_asset: dict,
    references: list[dict],
    model: dict,
    generated_references: list[dict] | None = None,
) -> tuple[dict, list[str], str]:
    warnings: list[str] = []
    generated_references = generated_references or []
    if model.get("input_mode") == "reference-to-video":
        result = with_role(product_asset, "product", "product")
        result["selected_as"] = "input_evidence_bookkeeping_only"
        result["provider_upload_allowed"] = False
        return result, warnings, "recorded the user product image as evidence only; it is not a Provider reference"
    ranked_roles = {role: index for index, role in enumerate(VIDEO_SOURCE_ROLE_PRIORITY)}
    candidates = [ref for ref in references if ref.get("role") in ranked_roles]
    if candidates:
        selected = sorted(candidates, key=lambda item: ranked_roles[item.get("role", "")])[0]
        result = dict(selected)
        result["selected_as"] = "video_source"
        reason = f"selected confirmed reference role '{selected.get('role')}' as video source"
        return result, warnings, reason
    result = dict(product_asset)
    result["role"] = "product"
    result["selected_as"] = "video_source"
    reason = "selected product image as video source"
    if references and not model_supports_reference_images(model):
        warnings.append(
            "The selected model accepts only one source image. Extra reference images cannot affect the video unless a final video source image is supplied with role video_source/final_frame/presenter_product."
        )
    return result, warnings, reason


def build_video_reference_assets(
    product_asset: dict,
    references: list[dict],
    model: dict,
    generated_references: list[dict] | None = None,
) -> tuple[list[dict], list[dict], list[str]]:
    warnings: list[str] = []
    if not model_supports_reference_images(model):
        return [], [], warnings

    generated_references = generated_references or []
    require_generated = bool(model.get("require_generated_video_references"))
    include_product = bool(model.get("include_product_as_reference"))
    max_references = int(model.get("max_reference_images") or len(references) or 1)
    candidates: list[dict] = []
    if require_generated:
        if not generated_references:
            raise ScriptError(
                "This professional reference-to-video route requires a complete generated Reference Pack, beginning "
                "with role=product. User-uploaded product images are evidence only. After Stage 1 approval, pass every generated control with "
                "--generated-reference role=<local-file>."
            )
        if include_product:
            candidates.append(with_role(product_asset, "product", "product"))
        candidates.extend(dict(ref) for ref in generated_references)
    elif include_product:
        candidates.append(with_role(product_asset, "product", "product"))
        candidates.extend(dict(ref) for ref in references)
    else:
        candidates.extend(dict(ref) for ref in references)

    if require_generated:
        roles = [str(asset.get("role") or "reference").lower() for asset in candidates]
        if model.get("require_product_anchor_reference") and (not roles or roles[0] != "product"):
            raise ScriptError(
                "The first generated reference must use role=product and be the professional product master."
            )
        if any(role == "product" for role in roles[1:]):
            raise ScriptError("The generated Reference Pack must contain exactly one role=product in the first slot.")
        forbidden_storyboards = [role for role in roles if role in {"storyboard", "storyboard_sheet", "shot_plan"}]
        if forbidden_storyboards and not bool(model.get("allow_storyboard_reference_upload", True)):
            raise ScriptError(
                "Storyboard/contact-sheet images are review-only for this reference-to-video route and cannot be "
                "uploaded as element controls. Use --storyboard-preview-image for review, or use per-segment "
                "image-to-video for exact keyframe control."
            )
        generated_candidates = candidates[1:] if include_product else candidates
        if model.get("require_local_generated_references"):
            non_local = [asset_identity(asset) for asset in generated_candidates if asset.get("kind") != "file"]
            if non_local:
                raise ScriptError(
                    "Generated video references must be saved as local files before Stage 2 confirmation. "
                    f"Non-local references: {non_local}"
                )
        evidence_digests = {
            digest
            for digest in [local_asset_digest(product_asset), *(local_asset_digest(asset) for asset in references)]
            if digest
        }
        reused_raw = [
            asset_identity(asset)
            for asset in generated_candidates
            if local_asset_digest(asset) and local_asset_digest(asset) in evidence_digests
        ]
        if reused_raw:
            raise ScriptError(
                "A generated Provider reference is byte-identical to user-supplied evidence. Cropping, copying, "
                "renaming, or directly reusing an uploaded product image is forbidden; regenerate every video reference after Stage 1 approval. "
                f"Reused files: {reused_raw}"
            )

    deduped: list[dict] = []
    seen: set[str] = set()
    for candidate in candidates:
        identity = asset_identity(candidate)
        if not identity or identity in seen:
            continue
        seen.add(identity)
        deduped.append(candidate)

    if len(deduped) > max_references:
        roles = ", ".join(asset.get("role", "reference") for asset in deduped)
        raise ScriptError(
            f"Selected model accepts at most {max_references} reference image(s), but {len(deduped)} were prepared: {roles}. "
            "Reduce references or generate one composite video_source image."
        )

    style = model.get("reference_prompt_style", "angle")
    mapped: list[dict] = []
    prompt_map: list[dict] = []
    index_base = int(model.get("reference_index_base", 1))
    for ordinal, asset in enumerate(deduped):
        display_index = ordinal + index_base
        token = reference_token(ordinal, style, index_base=index_base)
        item = dict(asset)
        item["ref_index"] = display_index
        item["prompt_token"] = token
        item["role_instruction"] = reference_role_instruction(str(item.get("role") or "reference"))
        if require_generated:
            item["provenance"] = "generated_from_approved_visual_plan"
            item["provider_upload_allowed"] = True
        mapped.append(item)
        prompt_map.append({
            "token": token,
            "role": item.get("role", "reference"),
            "value": asset_identity(item),
            "instruction": item["role_instruction"],
        })
    return mapped, prompt_map, warnings


def build_visual_design_contract(
    brief_data: dict,
    visual_direction: str,
    reference_strategy: str,
    reference_prompt_map: list[dict],
    model: dict,
    product_identity_evidence: list[dict],
    storyboard_preview_asset: dict | None = None,
) -> dict:
    """Freeze the ad-design reasoning and every actual reference-image assignment."""
    raw = brief_data.get("visual_design") or {}
    if not isinstance(raw, dict):
        raise ScriptError("visual_design in the project brief must be a JSON object")
    raw_reference_plan = raw.get("reference_plan") or brief_data.get("reference_plan") or []
    if not isinstance(raw_reference_plan, list):
        raise ScriptError("visual_design.reference_plan must be a JSON list")
    planned_by_role = {
        str(item.get("role") or "reference"): item
        for item in raw_reference_plan
        if isinstance(item, dict)
    }
    resolved_reference_plan = []
    require_generated = bool(model.get("require_generated_video_references"))
    product_identity_ids = [
        str(asset.get("id"))
        for asset in product_identity_evidence
        if str(asset.get("id") or "").strip()
    ]
    for item in reference_prompt_map:
        role = str(item.get("role") or "reference")
        planned = planned_by_role.get(role, {})
        image_prompt = str(planned.get("image_prompt") or "").strip()
        mechanism_sensitive_role = role in {"product_detail", "hand_action", "prop"} or role.startswith("beat_keyframe")
        if mechanism_sensitive_role and image_prompt:
            supported_mechanisms = {str(value).strip().lower() for value in (planned.get("supported_mechanisms") or [])}
            prompt_lower = image_prompt.lower()
            unsupported = []
            for mechanism in FORBIDDEN_UNVERIFIED_MECHANISMS:
                term = mechanism.lower()
                if term not in prompt_lower or term in supported_mechanisms:
                    continue
                negative_pattern = rf"(?:no|without|exclude|forbid|never|禁止|不得|不要|排除)[^.;。；]{{0,60}}{re.escape(term)}"
                if not re.search(negative_pattern, prompt_lower, flags=re.IGNORECASE):
                    unsupported.append(mechanism)
            if unsupported:
                raise ScriptError(
                    f"visual_design.reference_plan role {role!r} requests unsupported product mechanism(s) {unsupported}. "
                    "Add evidence-backed supported_mechanisms or remove the invented mechanism/prop before generating the reference."
                )
        if require_generated:
            if not planned:
                raise ScriptError(
                    f"visual_design.reference_plan is missing the generated video-reference role {role!r}. "
                    "Stage 1 must design every image before it is generated."
                )
            if not image_prompt:
                raise ScriptError(
                    f"visual_design.reference_plan role {role!r} is missing image_prompt. "
                    "Every generated video reference needs a complete approved generation prompt."
                )
            source = str(planned.get("source") or "").lower()
            if source not in {"generated", "generate_after_stage_1", "generated_from_approved_visual_plan"}:
                raise ScriptError(
                    f"visual_design.reference_plan role {role!r} must be generated after Stage 1; got source={source!r}."
                )
            if planned.get("upload_to_video_model") is False:
                raise ScriptError(
                    f"visual_design.reference_plan role {role!r} is marked review-only but was supplied as a video reference."
                )
            if role == "product":
                generation_mode = str(planned.get("generation_mode") or "professional_product_master").lower()
                if generation_mode not in {
                    "professional_product_master",
                    "reference_image_regeneration",
                    "regenerated_product_master",
                }:
                    raise ScriptError(
                        "visual_design.reference_plan role 'product' must use a generative product-master mode; "
                        f"got generation_mode={generation_mode!r}. Cropping, copying, background removal, or direct reuse is forbidden."
                    )
        resolved_reference_plan.append({
            "token": item.get("token"),
            "role": role,
            "purpose": item.get("instruction") or reference_role_instruction(role),
            "source": (
                "generated_from_approved_visual_plan"
                if require_generated
                else planned.get("source") or ("user_supplied" if role == "product" else "prepared_asset")
            ),
            "generation_mode": planned.get("generation_mode") or ("professional_product_master" if require_generated and role == "product" else "campaign_control_plate" if require_generated else "provider_specific"),
            "upload_to_video_model": True,
            "image_prompt": image_prompt,
            "asset_value": item.get("value"),
            "fact_source": planned.get("fact_source") or "approved_stage_1_plan_plus_user_input_evidence",
            "fact_source_asset_ids": list(
                item.get("fact_source_asset_ids")
                or planned.get("fact_source_asset_ids")
                or product_identity_ids
            ),
            "product_identity_required": bool(item.get("product_identity_required")),
            "product_identity_evidence_asset_ids": list(product_identity_ids),
            "generation_input_policy": item.get("generation_input_policy") or "role_relevant_evidence_only",
            "generation_input_asset_ids": list(item.get("generation_input_asset_ids") or []),
            "generation_input_paths": list(item.get("generation_input_paths") or []),
            "generation_input_sha256": list(item.get("generation_input_sha256") or []),
            "generation_input_record_status": item.get("generation_input_record_status") or "missing",
            "mechanism_lock": planned.get("mechanism_lock") or "show_only_product_mechanisms_visible_in_or_explicitly_supported_by_input_evidence",
            "mechanism_contract": {
                "observed": list(planned.get("observed_mechanisms") or planned.get("supported_mechanisms") or []),
                "allow_only_observed_or_explicit": True,
                "unsupported_inventions_forbidden": True,
            },
            "forbidden_inventions": planned.get("forbidden_inventions") or list(FORBIDDEN_UNVERIFIED_MECHANISMS),
            "multimodal_qc": planned.get("multimodal_qc") or {
                "required": False,
                "checks": ["same_sku_identity", "packaging_and_logo_consistency", "no_unsupported_mechanism_or_prop"],
                "status": "advisory_before_stage_2_confirmation",
            },
            "multimodal_qc_result": planned.get("multimodal_qc_result") or {
                "status": "not_required",
                "reviewer": "stage_2_user_confirmation",
            },
        })
    storyboard_raw = raw.get("storyboard_preview") or {}
    product_master_qc = {
        "required": False,
        "checks": [
            "same_sku_silhouette_and_proportions",
            "same_colors_materials_and_finish",
            "same_packaging_layout_and_cap_or_closure",
            "same_logo_position_and_existing_marks",
            "no_invented_removed_or_reworded_product_details",
            "single_clean_product_no_ui_no_watermark_no_added_copy",
        ],
        "failure_action": "regenerate_only_when_stage_2_user_rejects_the_image",
        "raw_fallback_allowed": False,
    }
    return {
        "schema_version": "professional-director-visual-v6",
        "creative_thesis": raw.get("creative_thesis") or brief_data.get("style") or "professional product-first social-commerce ad",
        "selling_objective": raw.get("selling_objective") or brief_data.get("campaign_goal") or "conversion",
        "visual_system": raw.get("visual_system") or {},
        "storyboard": raw.get("storyboard") or [],
        "transition_design": raw.get("transition_design") or [],
        "audio_design": raw.get("audio_design") or {},
        "reference_strategy": reference_strategy,
        "product_identity_evidence_policy": "Use every trustworthy same-SKU product view together for each product-dependent imagegen call. Add person, scene, or style evidence only when that generated control needs it.",
        "product_identity_evidence_asset_ids": product_identity_ids,
        "input_evidence_policy": "Treat every user-uploaded product, detail, person, and scene image as evidence only. Never upload raw, cropped, copied, renamed, or merely background-removed user evidence to the default R2V route.",
        "reference_selection_rule": "After Stage 1, generate a faithful product master first, then prefer full-screen Hook and Proof/Payoff campaign keyframes. Add presenter, scene or action controls only when they solve a specific identity or action problem. Never upload storyboard grids or fill all seven slots without a clear role.",
        "reference_plan": resolved_reference_plan,
        "product_master_qc": product_master_qc,
        "storyboard_preview": {
            "usage": storyboard_raw.get("usage") or "review_only",
            "upload_to_reference_to_video": False,
            "image_prompt": storyboard_raw.get("image_prompt") or "",
            "asset_value": asset_identity(storyboard_preview_asset or {}),
            "route_decision": "A storyboard/contact sheet reviews shot logic but is not an element reference. For exact shot starts, generate per-shot keyframes and use segmented image-to-video with a separately approved paid count.",
        },
        "video_prompt_blueprint": raw.get("video_prompt") or visual_direction,
        "approval_flow": [
            "stage_1_creative_plan_approval_before_reference_generation",
            "stage_2_actual_reference_set_and_paid_request_approval",
        ],
        "mode_rule": "Reference-to-video receives only generated references. The first slot is a faithful professional product master derived from user evidence; later slots are generated controls or clean beat keyframes. Storyboards are review-only; exact keyframes require segmented image-to-video. Never mix reference_images with image.",
    }


def reference_prompt_contract(
    model: dict,
    video_source_asset: dict,
    video_reference_assets: list[dict],
    reference_strategy: str,
) -> str:
    """Describe only Provider-visible reference bindings, independent of product category."""
    source_token = model.get("source_prompt_token")
    source_is_uploaded = not video_reference_assets or bool(model.get("include_source_image_with_references", True))
    if video_reference_assets:
        def compact_role(role: str) -> str:
            normalized = role.strip().lower()
            if normalized == "product":
                return "product identity"
            if normalized == "product_detail":
                return "approved product detail"
            if normalized in {"presenter", "model"}:
                return "presenter identity"
            if normalized == "wardrobe":
                return "approved wardrobe"
            if normalized == "scene":
                return "scene and lighting"
            if normalized == "hand_action":
                return "approved hand action"
            if normalized.startswith("beat_keyframe"):
                return "beat composition"
            if normalized == "style":
                return "visual finish"
            return normalized.replace("_", " ") or "approved control"

        mapping = "; ".join(
            f"{asset.get('prompt_token')}={compact_role(str(asset.get('role') or 'reference'))}"
            for asset in video_reference_assets
        )
        if reference_strategy in {"multi_reference_storyboard", "storyboard_sheet_reference"}:
            return (
                f"Reference image map: {mapping}. Product identity has priority; use each image only for its named role; "
                "render full-screen rather than a grid."
            )
        return (
            f"Reference image map: {mapping}. Priority: product identity first; each other image controls only its named role; "
            "references do not define the first frame."
        )
    if reference_strategy == "per_segment_source_frames":
        token = source_token or "the uploaded image"
        return (
            f"Reference strategy: per_segment_source_frames; {token} is this segment's approved first frame. "
            "Preserve identities and render one stitchable segment."
        )
    if source_token and source_is_uploaded and video_source_asset:
        return f"Reference: {source_token} is the approved first frame; preserve identity and composition."
    return "Reference: use the uploaded approved product/source image and preserve its identity."


def build_director_clip_contracts(
    brief_data: dict,
    segments: list[int],
    visual_direction: str,
    enable_timecoded_beats: bool = False,
) -> list[dict]:
    del visual_direction
    visual = brief_data.get("visual_design") if isinstance(brief_data.get("visual_design"), dict) else {}
    sound_design = visual.get("sound_design") if isinstance(visual.get("sound_design"), dict) else {}
    if not sound_design and isinstance(brief_data.get("sound_design"), dict):
        sound_design = brief_data.get("sound_design")
    sound_mode = str(sound_design.get("mode") or "").strip().lower()
    if sound_mode and sound_mode not in SOUND_DESIGN_MODES:
        raise ScriptError(
            f"sound_design.mode={sound_mode!r} is invalid; use one of {', '.join(SOUND_DESIGN_MODES)}"
        )
    shot_mode = str(visual.get("shot_mode") or brief_data.get("shot_mode") or "commercial_montage").strip().lower()
    if shot_mode not in SHOT_MODES:
        raise ScriptError(f"shot_mode must be one of: {', '.join(SHOT_MODES)}")
    if shot_mode == "continuous_sequence" and len(segments) > 1:
        raise ScriptError(
            "continuous_sequence cannot span independent Provider generations. Use commercial_montage, "
            "or shorten the delivery to one verified route slot."
        )

    supplied = visual.get("clip_plan") or brief_data.get("clip_plan") or []
    storyboard = visual.get("storyboard") or brief_data.get("storyboard") or []
    if storyboard and not isinstance(storyboard, list):
        raise ScriptError("visual_design.storyboard must be a JSON array")
    total_seconds = sum(segments)
    if enable_timecoded_beats and storyboard:
        minimum_beats = 1 if total_seconds <= 4 else 2
        if not minimum_beats <= len(storyboard) <= 4:
            raise ScriptError(
                f"A {total_seconds}-second reference-to-video commercial requires {minimum_beats} to four semantic beats; "
                f"got {len(storyboard)}. Combine redundant actions or provide a clip plan for a longer campaign."
            )
        if len(segments) > 1 and len(storyboard) < len(segments):
            raise ScriptError(
                "A multi-request reference-to-video plan needs at least one complete semantic beat per paid clip."
            )
    if supplied and (not isinstance(supplied, list) or len(supplied) != len(segments)):
        raise ScriptError("visual_design.clip_plan must contain exactly one director contract per paid clip")
    defaults = [
        ("hook_reveal", "Reveal the product immediately", "push_in", "motivated_cut"),
        ("proof_payoff", "Demonstrate one truthful material or use proof in a clean close view", "track", "match_action_cut"),
        ("packshot_cta", "Settle into a clean product packshot and hold the final frame for one second", "pull_back", "end_hold_1s"),
    ]
    contracts: list[dict] = []
    for index, seconds in enumerate(segments):
        raw = supplied[index] if supplied else {}
        if not isinstance(raw, dict):
            raise ScriptError(f"clip_plan[{index}] must be a JSON object")
        default = defaults[min(index, len(defaults) - 1)]
        camera_move = str(raw.get("camera_move") or default[2]).strip().lower().replace(" ", "_")
        if camera_move not in CAMERA_MOVES:
            raise ScriptError(
                f"clip_plan[{index}].camera_move={camera_move!r} is invalid; use exactly one of {', '.join(CAMERA_MOVES)}"
            )
        if sound_mode == "voice_only":
            default_sfx = "none"
            default_ambience = "none"
            default_music = "no music"
        else:
            default_sfx = sound_design.get("signature_sfx") or "distinct product-action and transition sound"
            default_ambience = sound_design.get("ambience") or "scene-appropriate commercial ambience"
            default_music = sound_design.get("music") or "restrained original instrumental underscore, no vocals or lyrics"
        contract = {
            "clip_id": f"shot_{index + 1:02d}",
            "duration_seconds": seconds,
            "shot_mode": shot_mode,
            "beat": raw.get("beat") or default[0],
            "action": raw.get("action") or default[1],
            "camera_move": camera_move,
            "entry_state": raw.get("entry_state") or ("approved_opening_state" if index == 0 else "approved_continuity_state"),
            "exit_state": raw.get("exit_state") or ("stable_final_hold" if index == len(segments) - 1 else "stable_edit_safe_state"),
            "transition_out": raw.get("transition_out") or default[3],
            "stitch_motivation": raw.get("stitch_motivation") or ("final_resolution" if index == len(segments) - 1 else "action_complete_match_cut"),
            "audio_bridge": raw.get("audio_bridge") or ("final_sound_resolution" if index == len(segments) - 1 else "restate_full_sonic_fingerprint_after_complete_sentence"),
            "sfx": raw.get("sfx") or default_sfx,
            "ambience": raw.get("ambience") or default_ambience,
            "music": raw.get("music") or default_music,
        }
        contracts.append(contract)

    def parse_time(value: object) -> tuple[float, float] | None:
        match = re.search(
            r"([0-9]+(?:\.[0-9]+)?)\s*[-–]\s*([0-9]+(?:\.[0-9]+)?)\s*s?",
            str(value or ""),
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        start, end = float(match.group(1)), float(match.group(2))
        return (start, end) if end > start else None

    def format_time(start: float, end: float) -> str:
        return f"{start:g}-{end:g}s"

    def normalize_beat(raw: dict, beat_index: int, original_time: str) -> dict:
        if not isinstance(raw, dict):
            raise ScriptError(f"visual_design.storyboard[{beat_index}] must be a JSON object")
        camera_defaults = ("push_in", "locked_macro", "track", "pull_back")
        camera_move = str(
            raw.get("camera_move") or camera_defaults[min(beat_index, len(camera_defaults) - 1)]
        ).strip().lower().replace(" ", "_")
        if camera_move not in CAMERA_MOVES:
            raise ScriptError(
                f"visual_design.storyboard[{beat_index}].camera_move={camera_move!r} is invalid; "
                f"use exactly one of {', '.join(CAMERA_MOVES)}"
            )
        return {
            "beat_id": str(raw.get("beat_id") or raw.get("id") or f"beat_{beat_index + 1:02d}"),
            "time": original_time,
            "original_time": str(raw.get("time") or original_time),
            "timing_adjustment": "none",
            "commercial_job": raw.get("commercial_job") or raw.get("purpose") or "advance recognition, belief or desire",
            "purpose": raw.get("purpose") or raw.get("commercial_job") or "commercial beat",
            "entry_state": raw.get("entry_state") or "approved composition ready for the visible action",
            "action": raw.get("action") or raw.get("picture") or raw.get("purpose") or "Show the approved commercial beat",
            "framing": raw.get("framing") or raw.get("shot_size") or "full-screen commercial composition with clear product hierarchy",
            "camera_move": camera_move,
            "camera_pace": raw.get("camera_pace") or "controlled and motivated by the visible action",
            "focus_behavior": raw.get("focus_behavior") or "hold product identity readable at the selling moment",
            "lighting_motion": raw.get("lighting_motion") or "light changes only to reveal form, material or emotion",
            "physical_response": raw.get("physical_response") or "approved subjects respond naturally to the action",
            "exit_state": raw.get("exit_state") or "complete the action in a stable edit-ready state",
            "transition_out": raw.get("transition_out") or ("end_hold_1s" if beat_index == len(source_beats) - 1 else "motivated_cut"),
            "sound_cue": raw.get("sound_cue") or raw.get("sfx") or "synchronize one scene-appropriate sound accent to the visible action",
        }

    def default_storyboard(seconds: int) -> list[dict]:
        if seconds <= 4:
            return [{
                "time": format_time(0, seconds),
                "commercial_job": "immediate recognition and desire",
                "action": "Reveal the approved product and resolve on a readable hero",
                "camera_move": "push_in",
                "transition_out": "end_hold_1s",
                "sound_cue": "one product-signature reveal accent",
            }]
        if seconds <= 7:
            split = round(seconds * 0.43, 1)
            return [
                {"time": format_time(0, split), "commercial_job": "hook and recognition", "action": "Reveal the product immediately", "camera_move": "push_in", "sound_cue": "tight reveal accent"},
                {"time": format_time(split, seconds), "commercial_job": "proof and memory", "action": "Show one truthful proof and resolve on the product hero", "camera_move": "pull_back", "transition_out": "end_hold_1s", "sound_cue": "proof accent resolving into the sonic signature"},
            ]
        first = round(seconds * 0.27, 1)
        second = round(seconds * 0.73, 1)
        return [
            {"time": format_time(0, first), "commercial_job": "hook and product recognition", "action": "Reveal the product immediately", "camera_move": "push_in", "sound_cue": "recognition accent"},
            {"time": format_time(first, second), "commercial_job": "truthful proof and payoff", "action": "Show one truthful material, use, scale or function proof", "camera_move": "locked_macro", "sound_cue": "tactile proof sound synchronized to the visible action"},
            {"time": format_time(second, seconds), "commercial_job": "desire and memory anchor", "action": "Return to a stable product hero and hold the final frame for one second", "camera_move": "pull_back", "transition_out": "end_hold_1s", "sound_cue": "music and product signature resolve together"},
        ]

    if not enable_timecoded_beats:
        return contracts

    source_beats = storyboard or default_storyboard(total_seconds)
    normalized: list[tuple[float, float, dict]] = []
    fallback_duration = total_seconds / max(1, len(source_beats))
    for beat_index, raw in enumerate(source_beats):
        parsed = parse_time(raw.get("time") if isinstance(raw, dict) else "")
        if parsed is None:
            parsed = (beat_index * fallback_duration, (beat_index + 1) * fallback_duration)
        normalized.append((parsed[0], parsed[1], normalize_beat(raw, beat_index, format_time(*parsed))))

    if len(segments) == 1:
        timeline = [beat for _, _, beat in normalized]
        contracts[0].update({
            "beat": "single_generation_storyboard",
            "action": "Execute the approved commercial storyboard",
            "camera_move": "timecoded_per_beat",
            "transition_out": "end_hold_1s",
            "beat_timeline": timeline,
        })
        return contracts

    boundaries: list[float] = []
    cursor = 0.0
    for seconds in segments:
        cursor += seconds
        boundaries.append(cursor)
    assignments: list[int] = []
    for start, end, _ in normalized:
        midpoint = (start + end) / 2
        clip_index = next((index for index, boundary in enumerate(boundaries) if midpoint <= boundary), len(segments) - 1)
        assignments.append(clip_index)
    grouped: list[list[tuple[int, float, float, dict]]] = [[] for _ in segments]
    for beat_index, ((start, end, beat), clip_index) in enumerate(zip(normalized, assignments)):
        grouped[clip_index].append((beat_index, start, end, beat))
    for empty_index, group in enumerate(grouped):
        if group:
            continue
        donors = [index for index, candidate in enumerate(grouped) if len(candidate) > 1]
        if not donors:
            raise ScriptError("Each paid reference-to-video clip needs one complete semantic beat")
        donor = min(donors, key=lambda index: abs(index - empty_index))
        moved = grouped[donor].pop(-1 if donor < empty_index else 0)
        grouped[empty_index].append(moved)

    for clip_index, (seconds, assigned) in enumerate(zip(segments, grouped)):
        assigned.sort(key=lambda item: item[0])
        weights = [max(0.1, end - start) for _, start, end, _ in assigned]
        weight_total = sum(weights)
        local_cursor = 0.0
        local_beats: list[dict] = []
        for local_index, ((_, _, _, beat), weight) in enumerate(zip(assigned, weights)):
            local_end = float(seconds) if local_index == len(assigned) - 1 else local_cursor + seconds * weight / weight_total
            local_beat = dict(beat)
            local_beat["time"] = format_time(local_cursor, local_end)
            local_beat["timing_adjustment"] = "route_boundary_reflow"
            if local_index == 0 and clip_index > 0 and "entry_state" not in source_beats[assigned[local_index][0]]:
                local_beat["entry_state"] = "enter from the approved continuity state after the planned edit"
            if local_index == len(assigned) - 1 and clip_index < len(segments) - 1:
                local_beat["exit_state"] = "complete the visible action in a stable edit-safe state"
                local_beat["transition_out"] = "planned_edit_safe_cut"
            elif clip_index == len(segments) - 1 and local_index == len(assigned) - 1:
                local_beat["transition_out"] = "end_hold_1s"
            local_beats.append(local_beat)
            local_cursor = local_end
        contracts[clip_index].update({
            "beat": "route_split_storyboard",
            "action": "Execute complete assigned commercial beats; do not split an action across requests",
            "camera_move": "timecoded_per_beat",
            "transition_out": "end_hold_1s" if clip_index == len(segments) - 1 else "planned_edit_safe_cut",
            "beat_timeline": local_beats,
        })
    return contracts


SOUND_CROSS_CLIP_PATTERNS = (
    r"\bsame\s+as\s+(?:the\s+)?(?:previous|prior|last)(?:\s+(?:clip|shot|segment))?\b",
    r"\bthe\s+same\b",
    r"(?:沿用|延续|承接|继续)(?:上一段|前一段|上一个镜头|前一个镜头|上一镜|前一镜)?",
    r"(?:上一段|前一段|上一个镜头|前一个镜头|上一镜|前一镜)",
)


def self_contained_sound_direction(value: object, canonical: object, layer_name: str) -> tuple[str, int]:
    """Replace cross-request shorthand with a complete per-request sound description."""
    raw = str(value or "").strip()
    anchor = str(canonical or "").strip()
    cleaned = raw
    removed = 0
    for pattern in SOUND_CROSS_CLIP_PATTERNS:
        cleaned, count = re.subn(pattern, "", cleaned, flags=re.IGNORECASE)
        removed += count
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;，；。.-")
    if not removed:
        return raw or anchor, 0
    if not anchor:
        return cleaned, removed
    if not cleaned or cleaned.casefold() in anchor.casefold():
        return anchor, removed
    return f"{anchor}; local {layer_name} development: {cleaned}", removed


def contains_cross_clip_sound_dependency(value: object) -> bool:
    text = str(value or "")
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in SOUND_CROSS_CLIP_PATTERNS)


def build_sound_design_contract(
    brief_data: dict,
    director_clips: list[dict],
    native_provider_sound: bool,
) -> dict:
    """Build a compact commercial sound plan without requiring a preset voice."""
    visual = brief_data.get("visual_design") if isinstance(brief_data.get("visual_design"), dict) else {}
    supplied = visual.get("sound_design") if isinstance(visual.get("sound_design"), dict) else {}
    if not supplied and isinstance(brief_data.get("sound_design"), dict):
        supplied = brief_data.get("sound_design")
    requested_mode = str(supplied.get("mode") or "").strip().lower()
    if requested_mode and requested_mode not in SOUND_DESIGN_MODES:
        raise ScriptError(
            f"sound_design.mode={requested_mode!r} is invalid; use one of {', '.join(SOUND_DESIGN_MODES)}"
        )

    def is_none(value: object) -> bool:
        return str(value or "").strip().lower() in {"", "none", "no", "off", "silent", "no music"}

    if requested_mode:
        mode = requested_mode
    elif director_clips and all(is_none(clip.get("music")) for clip in director_clips):
        mode = "ambience_led"
    else:
        mode = "layered_native"
    non_speech_required = mode != "voice_only"
    required_layers = {
        "sfx": non_speech_required,
        "ambience": non_speech_required,
        "music": mode == "layered_native",
    }
    if mode == "voice_only":
        music_policy = "none_explicit"
    elif mode == "ambience_led":
        music_policy = "ambience_led_no_music"
    else:
        music_policy = "original_instrumental"
    sonic_idea = str(
        supplied.get("sonic_idea")
        or visual.get("sound_intent")
        or brief_data.get("sound_intent")
        or "make the product action recognizable through one repeatable sonic signature"
    ).strip()
    signature_sfx = str(
        supplied.get("signature_sfx") or "precise product-action accents synchronized to visible actions"
    ).strip()
    ambience_bed = str(supplied.get("ambience") or "scene-appropriate commercial ambience").strip()
    score_palette = str(
        supplied.get("music") or "restrained original instrumental score shaped to the visual energy curve"
    ).strip()
    energy_curve = str(supplied.get("energy_curve") or "hook lift, proof focus, payoff resolution").strip()
    clip_sound_map = []
    beat_cue_map = []
    for clip in director_clips:
        sfx_prompt, sfx_removed = self_contained_sound_direction(clip.get("sfx"), signature_sfx, "SFX")
        ambience_prompt, ambience_removed = self_contained_sound_direction(
            clip.get("ambience"), ambience_bed, "ambience"
        )
        music_prompt, music_removed = self_contained_sound_direction(
            clip.get("music"), score_palette, "music"
        )
        clip_removed = sfx_removed + ambience_removed + music_removed
        clip_sound_map.append({
            "clip_id": clip.get("clip_id"),
            "sfx": clip.get("sfx"),
            "ambience": clip.get("ambience"),
            "music": clip.get("music"),
            "sfx_prompt": sfx_prompt,
            "ambience_prompt": ambience_prompt,
            "music_prompt": music_prompt,
            "audio_bridge": clip.get("audio_bridge"),
            "cue_sync": "match each signature sound to its visible action or motivated edit",
            "cross_clip_dependency_terms_removed": clip_removed,
        })
        for beat in clip.get("beat_timeline") or []:
            prompt_sound_cue, cue_removed = self_contained_sound_direction(
                beat.get("sound_cue"),
                sonic_idea,
                "cue",
            )
            clip_removed += cue_removed
            beat_cue_map.append({
                "clip_id": clip.get("clip_id"),
                "beat_id": beat.get("beat_id"),
                "time": beat.get("time"),
                "visible_action": beat.get("action"),
                "sound_cue": beat.get("sound_cue"),
                "prompt_sound_cue": prompt_sound_cue,
                "cross_clip_dependency_terms_removed": cue_removed,
            })
        clip_sound_map[-1]["cross_clip_dependency_terms_removed"] = clip_removed
    return {
        "mode": mode,
        "native_provider_sound": native_provider_sound,
        "non_speech_required": non_speech_required,
        "music_policy": music_policy,
        "required_layers": required_layers,
        "sonic_idea": sonic_idea,
        "signature_sfx": signature_sfx,
        "ambience_bed": ambience_bed,
        "score_palette": score_palette,
        "energy_curve": energy_curve,
        "clip_sound_map": clip_sound_map,
        "beat_cue_map": beat_cue_map,
        "delivery_strategy": "native_prompt_best_effort",
        "continuity_strategy": "self_contained_restatement_per_paid_clip",
        "native_cross_clip_audio_state_shared": False,
        "exact_score_continuity_requires_local_post_mix": True,
        "mix_direction": (
            "voice clear; SFX audible on action; continuous ambience and score audible under speech"
            if non_speech_required else
            "Voice-only was explicitly selected; music, ambience and effects remain absent."
        ),
        "verification_required": non_speech_required,
        "verification_method": "human or multimodal listening; an AAC track alone is not proof of planned sound layers",
        "failure_policy": "block formal delivery and do not automatically submit another paid generation",
    }


def build_talent_effects_contract(product_category: str) -> dict:
    return {
        "decision": "director_judgment",
        "product_category": product_category or "unknown",
        "visible_talent": "use full body, partial body, hands or no person according to the approved big idea",
        "human_value_criteria": ["desire", "trust", "scale", "use proof", "emotion"],
        "allowed_effects": ["truthful material response", "light", "liquid", "steam", "particles", "real product function"],
        "rule": "A person may appear when they strengthen desire, trust, scale, use proof or emotion. Do not invent a product function, mechanism, efficacy claim or self-moving inanimate product.",
    }


def compile_model_prompt(
    base_prompt: str,
    seconds: int,
    project_name: str,
    speaker_mode: str,
    product_motion_policy: str,
    commerce_platform: str,
    seller_persona: str,
    creative_variant: str,
    reference_strategy: str,
    model: dict,
    video_source_asset: dict,
    video_reference_assets: list[dict],
    platform_contract: dict,
    scenario_contract: dict,
    compliance_contract: dict,
    spoken_script: str = "",
    segment_index: int = 1,
    segment_total: int = 1,
    director_clip: dict | None = None,
    voice_reference_tokens: list[str] | None = None,
    voice_description: str = "",
    commercial_strategy: dict | None = None,
    talent_contract: dict | None = None,
    sound_design_contract: dict | None = None,
) -> dict:
    del commerce_platform, platform_contract, scenario_contract, compliance_contract
    if model.get("require_generated_video_references") and video_reference_assets:
        manual_tokens = re.findall(r"<IMAGE_\d+>|@Image\d+|@\(img\d+\)", base_prompt or "", flags=re.IGNORECASE)
        if manual_tokens:
            raise ScriptError(
                "The visual direction contains manual reference tokens that can contradict the final upload order: "
                f"{sorted(set(manual_tokens))}. Describe product/presenter/scene roles in plain language; "
                "the prompt compiler appends the canonical <IMAGE_n> mapping automatically."
            )
    if base_prompt:
        prompt = sanitize_prompt_text(base_prompt, speaker_mode, product_motion_policy)
    else:
        performance = (
            "natural approved presenter performance"
            if speaker_mode == "digital-human-spoken"
            else "product-led visual storytelling"
        )
        prompt = (
            f"{seconds}-second vertical e-commerce product ad segment for {project_name}. "
            "Show the hero product clearly, preserve product appearance, use clean commercial lighting, "
            f"smooth camera motion, {performance}, and a clear selling moment."
        )
    original_speech_occurrences = prompt.count(spoken_script.strip()) if spoken_script.strip() else 0
    prompt, removed_structural_blocks = remove_manual_structural_blocks(prompt)
    prompt, removed_speech_occurrences = remove_spoken_script_from_visual(prompt, spoken_script)
    removed_speech_occurrences = max(removed_speech_occurrences, original_speech_occurrences)
    if not prompt:
        prompt = (
            f"Create a {seconds}-second commercial for {project_name}; show the approved product clearly, "
            "build desire with professional lighting and one truthful visual proof."
        )
    if segment_total <= 1:
        segment_focus = "complete hook > proof > CTA"
    elif segment_index == 1:
        segment_focus = "opening hook > reveal > proof; planned cut"
    elif segment_index == segment_total:
        segment_focus = "final proof > buying reason > CTA"
    else:
        segment_focus = "demonstration > trust proof; planned cut"
    director_clip = director_clip or {}
    sound_design_contract = sound_design_contract or {}
    sound_clip = next(
        (
            item for item in (sound_design_contract.get("clip_sound_map") or [])
            if str(item.get("clip_id") or "") == str(director_clip.get("clip_id") or "")
        ),
        {},
    )
    sound_beats = {
        str(item.get("beat_id") or ""): item
        for item in (sound_design_contract.get("beat_cue_map") or [])
        if str(item.get("clip_id") or "") == str(director_clip.get("clip_id") or "")
    }
    camera_move = str(director_clip.get("camera_move") or "push_in")
    action = str(director_clip.get("action") or "Reveal and demonstrate the product clearly")
    shot_mode = str(director_clip.get("shot_mode") or "commercial_montage")
    beat_timeline = director_clip.get("beat_timeline") or []
    if beat_timeline:
        beat_lines = []
        for beat in beat_timeline:
            move = str(beat.get("camera_move") or "")
            if move not in CAMERA_MOVES:
                raise ScriptError(f"Each storyboard beat must declare exactly one approved camera move; got {move!r}")
            commercial_job = str(beat.get("commercial_job") or beat.get("purpose") or "commercial beat")
            framing = str(beat.get("framing") or "clear commercial composition")
            entry_state = str(beat.get("entry_state") or "approved opening state")
            concise_action = str(beat.get("action") or "Show the approved beat").replace("the product", "product")
            pace = str(beat.get("camera_pace") or "controlled pace")
            focus = str(beat.get("focus_behavior") or "product remains readable")
            lighting = str(beat.get("lighting_motion") or "light reveals form and material")
            physical = str(beat.get("physical_response") or "approved subjects respond naturally")
            exit_state = str(beat.get("exit_state") or "stable edit-ready state")
            transition = str(beat.get("transition_out") or "motivated_cut").replace("_", " ")
            sound_cue = str(
                (sound_beats.get(str(beat.get("beat_id") or "")) or {}).get("prompt_sound_cue")
                or beat.get("sound_cue")
                or ""
            ).strip()
            beat_lines.append(
                f'{beat.get("time")} {commercial_job}: {framing}; {entry_state} -> {concise_action}; '
                f'camera {move.replace("_", " ")} at {pace}, {focus}; {lighting}; {physical}; '
                f'end in {exit_state}; {transition}'
                f'{f"; sound on action: {sound_cue}" if sound_cue else ""}.'
            )
        timeline_heading = "Sequence" if shot_mode == "continuous_sequence" else "Cuts"
        director_action = f"{timeline_heading}: " + " ".join(beat_lines)
        camera_moves_by_beat = [beat.get("camera_move") for beat in beat_timeline]
    elif camera_move not in CAMERA_MOVES:
        raise ScriptError(f"Each clip must declare exactly one approved main camera move; got {camera_move!r}")
    else:
        director_action = f"Cuts: {action}; one {camera_move}. Segment {segment_index} of {segment_total}: {segment_focus}."
        camera_moves_by_beat = []
    speech = spoken_script.strip()
    quoted_speech = f'“{speech}”' if speech else "none"
    voice_direction = (voice_description.strip() or "natural commercial voice") if speech else "none"
    voice_reference = "; VoiceReference=" + ",".join(voice_reference_tokens or []) if voice_reference_tokens else ""
    non_speech_required = bool(sound_design_contract.get("non_speech_required"))
    required_layers = sound_design_contract.get("required_layers") or {}
    mix_direction = str(
        sound_design_contract.get("mix_direction")
        or ("voice clear; effects audible; ambience continuous; score ducks under speech" if non_speech_required else "voice only")
    )
    prompt_sfx = str(sound_clip.get("sfx_prompt") or director_clip.get("sfx") or "subtle product sound")
    prompt_ambience = str(sound_clip.get("ambience_prompt") or director_clip.get("ambience") or "clean room tone")
    prompt_music = str(sound_clip.get("music_prompt") or director_clip.get("music") or "restrained original instrumental underscore, no vocals or lyrics")
    if prompt_sfx == "distinct product-action and transition sound":
        prompt_sfx = "action accents"
    if prompt_ambience == "scene-appropriate commercial ambience":
        prompt_ambience = "scene bed"
    if prompt_music == "restrained original instrumental underscore, no vocals or lyrics":
        prompt_music = "original, no vocals"
    if non_speech_required and required_layers.get("ambience") and "continuous" not in prompt_ambience.casefold():
        prompt_ambience = f"continuous {prompt_ambience}"
    if non_speech_required and required_layers.get("music") and "audib" not in prompt_music.casefold():
        prompt_music = f"audible under speech: {prompt_music}"
    beat_prompt_cues = []
    for beat in beat_timeline:
        mapped = sound_beats.get(str(beat.get("beat_id") or "")) or {}
        cue = str(mapped.get("prompt_sound_cue") or beat.get("sound_cue") or "").strip()
        if cue:
            beat_prompt_cues.append((str(beat.get("time") or ""), cue))
    if beat_prompt_cues and non_speech_required:
        cue_summary = f"timed sound-on-action cues above | SFX {prompt_sfx}"
    else:
        cue_summary = prompt_sfx
    sonic_idea = str(sound_design_contract.get("sonic_idea") or "product action becomes a sonic signature")
    audio_line = (
        f'AUDIO: {"Dialogue" if speaker_mode == "digital-human-spoken" else "VO"}={quoted_speech}; '
        f'Voice={voice_direction}{voice_reference}; '
        f'SonicIdea={sonic_idea}; '
        f'Cues={cue_summary}; '
        f'Ambience={prompt_ambience}; '
        f'Music={prompt_music}; '
        f'Mix={mix_direction}.'
    )
    rendered_timeline_cues = [cue for _, cue in beat_prompt_cues if cue in director_action]
    audio_block_links_timecoded_cues = not beat_prompt_cues or "timed sound-on-action cues above" in audio_line
    clip_sfx_rendered = (
        not non_speech_required
        or not required_layers.get("sfx")
        or (bool(prompt_sfx.strip()) and prompt_sfx in audio_line)
    )
    self_contained_audio = not contains_cross_clip_sound_dependency(audio_line)
    sound_cue_coverage = {
        "planned_beat_cue_count": len(beat_prompt_cues),
        "timeline_beat_cue_count": len(rendered_timeline_cues),
        "clip_sfx_rendered": clip_sfx_rendered,
        "all_beat_cues_rendered_in_timeline": len(rendered_timeline_cues) == len(beat_prompt_cues),
        "audio_block_links_timecoded_cues": audio_block_links_timecoded_cues,
        "self_contained": self_contained_audio,
        "cross_clip_dependency_terms_removed": int(sound_clip.get("cross_clip_dependency_terms_removed") or 0),
        "continuity_strategy": sound_design_contract.get("continuity_strategy") or "",
    }
    commercial_strategy = commercial_strategy or {}
    strategy_line = creative_intent_contract(creative_variant)
    if commercial_strategy.get("provider_prompt_summary"):
        strategy_line = f"{strategy_line} {commercial_strategy['provider_prompt_summary']}."
    fixed_components = [
        {
            "name": "director_action",
            "text": director_action,
            "planning_only": False,
        },
        {"name": "creative_intent", "text": strategy_line, "planning_only": False},
        {"name": "factual_guardrail", "text": factual_guardrail_contract(), "planning_only": False},
        {
            "name": "reference_identity",
            "text": reference_prompt_contract(model, video_source_asset, video_reference_assets, reference_strategy),
            "planning_only": False,
        },
        {
            "name": "render_guardrails",
            "text": compact_render_guardrails(
                speaker_mode,
                product_motion_policy,
                seller_persona,
                bool(spoken_script.strip()),
                talent_contract or {"presence": "none", "gender": "not_applicable"},
            ),
            "planning_only": False,
        },
        {"name": "audio", "text": audio_line, "planning_only": False},
    ]
    for component in fixed_components:
        component["text"] = strip_provider_caption_terms(component["text"])
    fixed_components = [component for component in fixed_components if component["text"]]
    budget_chars, max_chars = prompt_limits(model)
    if budget_chars is not None and max_chars is not None and budget_chars > max_chars:
        raise ScriptError(
            f"Invalid model prompt limits: prompt_budget_chars={budget_chars} exceeds max_prompt_chars={max_chars}"
        )

    def render(items: list[dict]) -> str:
        return " ".join(item["text"] for item in items).strip()

    fixed_text = render(fixed_components)
    reserved_instruction_chars = len(fixed_text)
    policy_component_names = {"factual_guardrail", "reference_identity", "render_guardrails"}
    policy_text = render([item for item in fixed_components if item["name"] in policy_component_names])
    commercial_text = render([item for item in fixed_components if item["name"] not in policy_component_names])
    fixed_instruction_chars = len(policy_text)
    separator_chars = 1 if prompt and fixed_text else 0
    available_visual_chars = None if budget_chars is None else budget_chars - reserved_instruction_chars - separator_chars
    if available_visual_chars is not None and available_visual_chars < 1:
        raise ScriptError(
            f"Reserved Provider instruction length {reserved_instruction_chars} leaves available_visual_chars={available_visual_chars}. "
            "Use a larger prompt budget or a model adapter with smaller fixed contracts."
        )
    if available_visual_chars is not None and len(prompt) > available_visual_chars:
        raise ScriptError(
            f"Provider visual direction length {len(prompt)} exceeds available_visual_chars={available_visual_chars} "
            f"inside prompt_budget_chars={budget_chars}. Ask Codex to rewrite only the visual direction more concisely; "
            "approved dialogue and fixed safety contracts are not truncated."
        )
    active = [fixed_components[0], {"name": "visual_direction", "text": prompt.strip(), "planning_only": False}, *fixed_components[1:]]
    compiled = render(active)
    omitted: list[str] = ["platform", "scenario"]
    if budget_chars is not None and len(compiled) > budget_chars:
        raise ScriptError(
            f"Required Provider prompt length {len(compiled)} exceeds prompt_budget_chars={budget_chars}. "
            "Shorten the shot description or spoken script; the prompt compiler does not truncate approved content."
        )
    if max_chars is not None and len(compiled) > max_chars:
        raise ScriptError(
            f"Provider prompt length {len(compiled)} exceeds max_prompt_chars={max_chars}. "
            "Recompile before paid generation."
        )
    structural_block_counts = {
        "cuts": len(re.findall(r"\bCuts\s*:", compiled, flags=re.IGNORECASE)),
        "sequence": len(re.findall(r"\bSequence\s*:", compiled, flags=re.IGNORECASE)),
        "reference_image_map": len(re.findall(r"\bReference image map\s*:", compiled, flags=re.IGNORECASE)),
        "audio": len(re.findall(r"\bAUDIO\s*:", compiled, flags=re.IGNORECASE)),
    }
    structural_block_counts["director_timeline"] = (
        structural_block_counts["cuts"] + structural_block_counts["sequence"]
    )
    if structural_block_counts["audio"] != 1:
        raise ScriptError(f"Provider prompt must contain exactly one AUDIO block; got {structural_block_counts['audio']}")
    expected_reference_maps = 1 if video_reference_assets else 0
    if structural_block_counts["reference_image_map"] != expected_reference_maps:
        raise ScriptError(
            "Provider prompt reference map count does not match the actual reference payload: "
            f"expected={expected_reference_maps}, actual={structural_block_counts['reference_image_map']}"
        )
    if structural_block_counts["director_timeline"] != 1:
        raise ScriptError(
            "Provider prompt must contain exactly one director timeline block (Cuts or Sequence); "
            f"got {structural_block_counts['director_timeline']}"
        )
    if re.search(r",\s*,", compiled):
        raise ScriptError("Provider prompt contains an empty comma-delimited instruction")
    component_char_counts = {item["name"]: len(item["text"]) for item in active}
    creative_component_names = {"director_action", "visual_direction", "creative_intent", "audio"}
    creative_execution_chars = sum(
        component_char_counts.get(name, 0) for name in creative_component_names
    )
    reference_map_chars = component_char_counts.get("reference_identity", 0) if video_reference_assets else 0
    audio_chars = component_char_counts.get("audio", 0)
    creative_execution_ratio = creative_execution_chars / len(compiled) if compiled else 0.0
    reference_map_ratio = reference_map_chars / len(compiled) if compiled else 0.0
    guardrail_ratio = fixed_instruction_chars / len(compiled) if compiled else 0.0
    audio_ratio = audio_chars / len(compiled) if compiled else 0.0
    main_action_count = len(beat_timeline) if beat_timeline else 1
    actions_per_second = main_action_count / max(1, seconds)
    if seconds <= 4:
        recommended_prompt_range = [600, 1100]
    elif seconds <= 7:
        recommended_prompt_range = [800, 1400]
    elif seconds <= 10:
        recommended_prompt_range = [1000, 1800]
    else:
        recommended_prompt_range = [1300, 2400]
    density_warnings = []
    if video_reference_assets and reference_map_ratio > 0.25:
        density_warnings.append("reference_map_uses_more_than_25_percent_of_prompt")
    if video_reference_assets and creative_execution_ratio < 0.50:
        density_warnings.append("creative_execution_uses_less_than_50_percent_of_prompt")
    if actions_per_second > 0.45:
        density_warnings.append("too_many_main_actions_for_duration")
    negative_instruction_count = len(re.findall(
        r"\b(?:no|not|never|without|forbid(?:den)?|avoid|do not|cannot)\b",
        compiled,
        flags=re.IGNORECASE,
    ))
    return {
        "prompt": compiled,
        "contract": {
            "compiler": PROMPT_COMPILER_VERSION,
            "architecture": PROMPT_ARCHITECTURE,
            "char_count": len(compiled),
            "utf8_bytes": len(compiled.encode("utf-8")),
            "budget_chars": budget_chars,
            "max_chars": max_chars,
            "visual_direction_char_count": len(prompt),
            "fixed_instruction_char_count": fixed_instruction_chars,
            "commercial_execution_char_count": len(commercial_text),
            "creative_execution_char_count": creative_execution_chars,
            "creative_execution_ratio": creative_execution_ratio,
            "reference_map_ratio": reference_map_ratio,
            "guardrail_ratio": guardrail_ratio,
            "audio_ratio": audio_ratio,
            "negative_instruction_count": negative_instruction_count,
            "main_action_count": main_action_count,
            "actions_per_second": actions_per_second,
            "recommended_prompt_range_chars": recommended_prompt_range,
            "prompt_density_warnings": density_warnings,
            "reserved_non_visual_char_count": reserved_instruction_chars,
            "available_visual_chars": available_visual_chars,
            "included_components": [item["name"] for item in active],
            "omitted_planning_components": omitted,
            "component_char_counts": component_char_counts,
            "spoken_script_occurrences": compiled.count(spoken_script.strip()) if spoken_script.strip() else 0,
            "removed_spoken_script_duplicates": removed_speech_occurrences,
            "removed_structural_blocks": removed_structural_blocks,
            "structural_block_counts": structural_block_counts,
            "camera_move": camera_move,
            "camera_moves_by_beat": camera_moves_by_beat,
            "audio_language": "zh" if re.search(r"[\u3400-\u9fff]", speech) else "configured",
            "sound_cue_coverage": sound_cue_coverage,
            "truncated": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Project name")
    parser.add_argument("--project-root", default="projects", help="Root folder for generated projects")
    parser.add_argument("--product-image", action="append", required=True, help="User-supplied same-SKU product evidence for analysis and reference generation. Repeat for front, back, side, detail, or real-use views. These files are never uploaded to the default R2V route.")
    parser.add_argument("--reference-image", action="append", default=[], help="Optional user evidence as path/url or role=path/url. Non-product raw evidence is not uploaded on the default R2V route.")
    parser.add_argument("--generated-reference", action="append", default=[], help="Locally saved reference generated after Stage 1, as role=path. Default R2V requires role=product first, followed by other generated controls in final upload order.")
    parser.add_argument("--storyboard-preview-image", help="Generated storyboard/contact sheet for user review only. It is never uploaded to reference-to-video.")
    parser.add_argument("--video-source-image", help="Final confirmed source/first-frame image to send to image-to-video models")
    parser.add_argument("--segment-source-image", action="append", default=[], help="Confirmed source/first-frame image for one segment, as shot_01=path or path. Repeat for multi-scene single-image routes.")
    parser.add_argument("--model-image", help="Shortcut for --reference-image model=<path-or-url>")
    parser.add_argument("--scene-image", help="Shortcut for --reference-image scene=<path-or-url>")
    parser.add_argument("--storyboard-image", help="Shortcut for --reference-image storyboard=<path-or-url>")
    parser.add_argument("--duration", type=int, default=None, help="Total video duration in seconds; default comes from model config")
    parser.add_argument("--aspect-ratio", default=None, help="Output aspect ratio, e.g. 9:16")
    parser.add_argument("--resolution", default=None, help="Output resolution, e.g. 720p")
    parser.add_argument("--model-key", default=None, help="Configured model key")
    parser.add_argument("--prompt", default="", help="Final model-ready prompt or campaign prompt")
    parser.add_argument("--spoken-script", default="", help="Approved complete spoken commerce script. Required for reliable multi-segment spoken ads.")
    parser.add_argument("--voice-id", action="append", default=[], help="Advanced opt-in preset voice_id. Ordinary speech uses the prompt voice description and sends no reference_audios.")
    parser.add_argument("--voice-description", default=None, help="Natural-language voice and delivery direction placed in the AUDIO prompt block")
    parser.add_argument("--language", default="zh", help="Spoken language used for pacing estimates and semantic segmentation")
    parser.add_argument("--brief", help="Optional project brief JSON")
    parser.add_argument("--config", help="Path to model config JSON")
    parser.add_argument("--speaker-mode", choices=SPEAKER_MODES, default=None, help="Presenter/speech mode. Default: voiceover, or silent-captions for no-audio placements")
    parser.add_argument("--product-motion-policy", choices=PRODUCT_MOTION_POLICIES, default=None, help="How the product is allowed to move. Default: static-inanimate")
    parser.add_argument("--creative-variant", choices=CREATIVE_VARIANTS, default=None, help="Approved creative variant. Default: commerce_direct")
    parser.add_argument("--reference-strategy", choices=REFERENCE_STRATEGIES, default=None, help="Approved image/reference strategy. Default: auto")
    parser.add_argument("--platform", default=None, help="Target platform, e.g. tiktok, douyin, xiaohongshu, amazon, youtube, meta_reels, shopify")
    parser.add_argument("--placement", default=None, help="Ad placement, e.g. in_feed, sponsored_products_video, sponsored_brands_video, reels, product_page")
    parser.add_argument("--commerce-platform", default=None, help="Legacy alias for --platform, e.g. taobao, amazon, cross-border, marketplace-general")
    parser.add_argument("--campaign-goal", default=None, help="Campaign goal, e.g. conversion, awareness, live_room_traffic")
    parser.add_argument("--funnel-stage", default=None, help="Funnel stage, e.g. prospecting, consideration, retargeting")
    parser.add_argument("--commerce-scenario", choices=COMMERCE_SCENARIOS, default=None, help="Commerce scenario. Default: inferred from creative variant")
    parser.add_argument("--cta-type", default=None, help="CTA type, e.g. shop_now, learn_more, add_to_cart, watch_live")
    parser.add_argument("--offer", default=None, help="Offer text, discount, bundle, or urgency note")
    parser.add_argument("--sku", default=None, help="SKU or internal product identifier")
    parser.add_argument("--asin", default=None, help="Amazon ASIN when relevant")
    parser.add_argument("--product-url", default=None, help="Product or landing page URL")
    parser.add_argument("--shop-destination", default=None, help="Shop destination, e.g. product_page, live_room, amazon_listing")
    parser.add_argument("--marketplace-locale", default=None, help="Marketplace locale, e.g. US, CN, JP, DE")
    parser.add_argument("--claim-risk", choices=CLAIM_RISK_LEVELS, default=None, help="Claim risk level. Default: auto from product category")
    parser.add_argument("--safe-zone-profile", default=None, help="Safe-zone profile override")
    parser.add_argument("--subtitle-style", default=None, help="Subtitle style, e.g. high_contrast_short_captions")
    parser.add_argument("--subtitle-choice", choices=("pending", "enabled", "disabled"), default="disabled", help="Default disabled. Enable only when the user confirms local postproduction captions in Confirmation 1.")
    parser.add_argument("--subtitle-request-source", choices=("default", "user_plan_confirmation"), default="default", help="Must be user_plan_confirmation when subtitles are enabled.")
    parser.add_argument("--subtitle-file", help="Optional user-approved local SRT. Copied into the project and used only in local postproduction.")
    parser.add_argument("--subtitle-whisper-model", default="", help="Optional local whisper.cpp model; never sent to the video Provider")
    parser.add_argument("--subtitle-whisper-cli", default="", help="Optional local whisper.cpp executable; never sent to the video Provider")
    parser.add_argument("--segment-strategy", choices=SEGMENT_STRATEGIES, default=None, help="Segment planning strategy. Default: auto")
    parser.add_argument("--product-category", default=None, help="Product category from Codex material analysis")
    parser.add_argument("--seller-persona", default=None, help="Visible presenter persona, e.g. synthetic e-commerce presenter")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        model = get_model_config(config, args.model_key)
        brief_data = {}
        if args.brief:
            brief_data = normalize_brief(json.loads(Path(args.brief).expanduser().read_text(encoding="utf-8")))
        platform = args.platform or args.commerce_platform or brief_data.get("platform") or brief_data.get("commerce_platform") or "marketplace-general"
        placement = args.placement or brief_data.get("placement") or "general"
        profile_key, selected_platform_profile = platform_profile(platform, placement)
        duration = args.duration or brief_data.get("duration_seconds") or brief_data.get("duration") or int(model.get("default_duration_seconds", 15))
        duration = int(duration)
        aspect_ratio = args.aspect_ratio or brief_data.get("aspect_ratio") or selected_platform_profile.get("default_aspect_ratio") or model.get("default_aspect_ratio", "9:16")
        resolution = args.resolution or brief_data.get("resolution") or model.get("default_resolution", "720p")
        max_duration = int(model.get("max_duration_seconds", 15))
        min_duration = int(model.get("min_duration_seconds", 1))

        project_name = sanitize_name(args.name)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        project_dir = Path(args.project_root).expanduser().resolve() / f"{stamp}-{project_name}"
        assets_dir = project_dir / "assets"
        requests_dir = project_dir / "requests"
        clips_dir = project_dir / "clips"
        for folder in (assets_dir, requests_dir, clips_dir, project_dir / "references"):
            folder.mkdir(parents=True, exist_ok=True)

        subtitle_input_asset: dict = {}
        if args.subtitle_file:
            if args.subtitle_choice != "enabled":
                raise ScriptError("--subtitle-file requires --subtitle-choice enabled and explicit subtitle confirmation")
            subtitle_source = Path(args.subtitle_file).expanduser().resolve()
            if not subtitle_source.is_file() or subtitle_source.suffix.lower() != ".srt":
                raise ScriptError(f"Approved subtitle file must be a readable .srt file: {subtitle_source}")
            subtitle_dest = assets_dir / "subtitles" / subtitle_source.name
            subtitle_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(subtitle_source, subtitle_dest)
            subtitle_input_asset = {"kind": "file", "value": str(subtitle_dest), "role": "approved_subtitle"}

        product_assets = [
            copy_or_record_product_evidence(value, assets_dir, index)
            for index, value in enumerate(args.product_image, start=1)
        ]
        for asset in product_assets:
            asset["provider_upload_allowed"] = not bool(model.get("require_generated_video_references"))
        product_asset = product_assets[0]
        reference_inputs = []
        if args.video_source_image:
            reference_inputs.append(f"video_source={args.video_source_image}")
        if args.model_image:
            reference_inputs.append(f"model={args.model_image}")
        if args.scene_image:
            reference_inputs.append(f"scene={args.scene_image}")
        if args.storyboard_image:
            reference_inputs.append(f"storyboard={args.storyboard_image}")
        reference_inputs.extend(args.reference_image)
        references = [*product_assets[1:], *[
            copy_or_record_reference(item, assets_dir, i)
            for i, item in enumerate(reference_inputs, start=1)
        ]]
        for asset in references:
            asset["provenance"] = "user_supplied_input_evidence"
            asset["provider_upload_allowed"] = not bool(model.get("require_generated_video_references"))
        input_evidence_assets = [product_asset, *references]
        product_identity_evidence = resolve_product_identity_evidence(
            input_evidence_assets,
            brief_data,
        )
        generated_references = [
            copy_or_record_generated_reference(item, assets_dir, i)
            for i, item in enumerate(args.generated_reference, start=1)
        ]
        apply_generated_reference_metadata(
            generated_references,
            input_evidence_assets,
            product_identity_evidence,
            brief_data,
        )
        storyboard_preview_asset: dict = {}
        if args.storyboard_preview_image:
            storyboard_preview_asset = copy_or_record_asset(
                args.storyboard_preview_image,
                assets_dir / "approval_previews",
                folder="storyboard",
            )
            storyboard_preview_asset.update({
                "role": "storyboard_preview",
                "provenance": "generated_from_approved_visual_plan",
                "provider_upload_allowed": False,
                "review_only": True,
            })
        segment_sources = [copy_or_record_segment_source(item, assets_dir, i) for i, item in enumerate(args.segment_source_image, start=1)]
        segment_sources = sorted(segment_sources, key=lambda item: int(item.get("segment_index", 0)))
        expected_indices = list(range(1, len(segment_sources) + 1))
        actual_indices = [int(item.get("segment_index", 0)) for item in segment_sources]
        if actual_indices != expected_indices:
            raise ScriptError(f"Segment source images must be contiguous from shot_01. Got indices: {actual_indices}")
        product_category = args.product_category or brief_data.get("product_category") or "unknown"
        talent_effects_contract = build_talent_effects_contract(product_category)
        if selected_platform_profile.get("audio_policy") == "no_audio":
            default_speaker_mode = "silent-captions"
        else:
            default_speaker_mode = "voiceover"
        speaker_mode = coerce_choice(args.speaker_mode or brief_data.get("speaker_mode") or default_speaker_mode, SPEAKER_MODES, "speaker_mode")
        product_motion_policy = coerce_choice(args.product_motion_policy or brief_data.get("product_motion_policy") or "static-inanimate", PRODUCT_MOTION_POLICIES, "product_motion_policy")
        creative_variant = coerce_choice(args.creative_variant or brief_data.get("creative_variant") or "commerce_direct", CREATIVE_VARIANTS, "creative_variant")
        commerce_scenario = coerce_choice(args.commerce_scenario or brief_data.get("commerce_scenario") or "auto", COMMERCE_SCENARIOS, "commerce_scenario")
        segment_strategy = coerce_choice(args.segment_strategy or brief_data.get("segment_strategy") or "auto", SEGMENT_STRATEGIES, "segment_strategy")
        strategy_inputs = generated_references if model.get("require_generated_video_references") else references
        reference_strategy, strategy_warnings = resolve_reference_strategy(
            args.reference_strategy or brief_data.get("reference_strategy"),
            model,
            strategy_inputs,
            segment_sources,
        )
        product_name = brief_data.get("product_name") or project_name
        product_price = brief_data.get("product_price") or ""
        selling_points = brief_data.get("selling_points") or []
        audience = brief_data.get("audience") or ""
        cta_text = brief_data.get("cta_text") or ""
        visual_direction = args.prompt or brief_data.get("visual_direction") or ""
        visual_raw = brief_data.get("visual_design") if isinstance(brief_data.get("visual_design"), dict) else {}
        style_type = str(visual_raw.get("style_type") or brief_data.get("style_type") or "cinematic_product_hero")
        if style_type not in AD_STYLE_TYPES:
            raise ScriptError(f"style_type must choose exactly one of: {', '.join(AD_STYLE_TYPES)}")
        seller_persona = args.seller_persona or brief_data.get("seller_persona") or "synthetic e-commerce presenter"
        talent_contract = build_talent_contract(
            brief_data,
            speaker_mode,
            seller_persona,
            generated_references,
        )
        cta_type = args.cta_type or brief_data.get("cta_type") or ("shop_now" if selected_platform_profile.get("cta_required", True) else "contextual")
        offer = args.offer or brief_data.get("offer") or ""
        sku = args.sku or brief_data.get("sku") or ""
        asin = args.asin or brief_data.get("asin") or ""
        product_url = args.product_url or brief_data.get("product_url") or ""
        shop_destination = args.shop_destination or brief_data.get("shop_destination") or "product_page"
        marketplace_locale = args.marketplace_locale or brief_data.get("marketplace_locale") or "unspecified"
        safe_zone_profile = args.safe_zone_profile or brief_data.get("safe_zone_profile") or selected_platform_profile.get("safe_zone_profile") or "center_80_percent"
        subtitle_style = args.subtitle_style or brief_data.get("subtitle_style") or "short high-contrast captions inside safe zone"
        spoken_script = args.spoken_script or brief_data.get("spoken_script") or brief_data.get("script") or ""
        brief_preset_voice_ids = brief_data.get("preset_voice_ids") or []
        preset_voice_ids = args.voice_id or brief_preset_voice_ids
        preset_voice_source = (
            "cli_user_explicit"
            if args.voice_id
            else ("brief_user_explicit" if brief_preset_voice_ids else "")
        )
        if isinstance(preset_voice_ids, str):
            preset_voice_ids = [preset_voice_ids]
        preset_voice_ids = [str(value).strip() for value in preset_voice_ids if str(value).strip()]
        voice_description = str(
            args.voice_description
            or brief_data.get("voice_description")
            or visual_raw.get("sound_intent")
            or select_prompt_voice_description(
                product_category,
                creative_variant,
                commerce_scenario,
                style_type,
            )
        ).strip()
        voice_policy = "explicit_preset" if preset_voice_ids else ("prompt_native" if spoken_script.strip() else "none")
        requested_voice_gender = str(
            brief_data.get("voice_gender") or visual_raw.get("voice_gender") or ""
        ).strip().lower()
        if requested_voice_gender and requested_voice_gender not in GENDER_VALUES:
            raise ScriptError(f"voice_gender must be one of: {', '.join(GENDER_VALUES)}")
        inferred_voice_gender = infer_gender(voice_description) if spoken_script.strip() else "not_applicable"
        if spoken_script.strip() and requested_voice_gender in {"female", "male"}:
            if inferred_voice_gender in {"female", "male"} and inferred_voice_gender != requested_voice_gender:
                raise ScriptError("voice_gender conflicts with the natural-language voice_description")
            if inferred_voice_gender == "unspecified":
                voice_description = f"{voice_description}; {requested_voice_gender} voice"
            voice_gender = requested_voice_gender
        else:
            voice_gender = inferred_voice_gender
        voice_selection_reason = (
            "user or approved brief explicitly selected the optional preset voice"
            if preset_voice_ids
            else "voice and delivery are described directly in the Provider prompt"
        )
        if preset_voice_ids and not model.get("supports_preset_voice_references"):
            raise ScriptError("The selected model route does not support preset voice references")
        max_reference_audios = int(model.get("max_reference_audios") or 0)
        if max_reference_audios and len(preset_voice_ids) > max_reference_audios:
            raise ScriptError(f"The selected model accepts at most {max_reference_audios} preset voices")
        language = args.language or brief_data.get("language") or "zh"
        campaign_goal = args.campaign_goal or brief_data.get("campaign_goal") or "conversion"
        funnel_stage = args.funnel_stage or brief_data.get("funnel_stage") or ("retargeting" if creative_variant == "retargeting_offer" else "consideration")
        claim_risk = args.claim_risk or brief_data.get("claim_risk") or "auto"
        platform_contract = build_platform_contract(
            platform=platform,
            placement=placement,
            profile_key=profile_key,
            profile=selected_platform_profile,
            duration=duration,
            aspect_ratio=aspect_ratio,
            cta_type=cta_type,
            safe_zone_profile=safe_zone_profile,
            subtitle_style=subtitle_style,
        )
        scenario_contract = build_scenario_contract(commerce_scenario, creative_variant, platform_contract)
        compliance_contract = build_compliance_contract(claim_risk, product_category, marketplace_locale)
        model_capability_contract = build_model_capability_contract(model)
        commercial_strategy_contract = build_commercial_strategy_contract(brief_data, creative_variant, audience)
        product_director_profile = build_product_director_profile(
            brief_data,
            product_motion_policy,
            talent_contract,
            commercial_strategy_contract,
        )
        subtitle_plan = subtitle_plan_from({
            "enabled": args.subtitle_choice == "enabled",
            "request_source": args.subtitle_request_source,
            "confirmation_status": "confirmed" if args.subtitle_choice == "enabled" else args.subtitle_choice,
            "provider_policy": "never_send",
            "render_policy": "postproduction_burn_only" if args.subtitle_choice == "enabled" else "disabled",
            "paid_api_call": False,
            "style": subtitle_style,
            "safe_zone_profile": safe_zone_profile,
            "whisper_model": args.subtitle_whisper_model,
            "whisper_executable": args.subtitle_whisper_cli,
            "lexical_source": "provided_srt" if subtitle_input_asset else "final_audio_transcript",
            "timing_source": "provided_srt" if subtitle_input_asset else "local_whisper_cpp",
            "input_subtitle": subtitle_input_asset,
            "profile": resolve_subtitle_profile(platform, aspect_ratio) if args.subtitle_choice == "enabled" else {},
            "srt_output": str(project_dir / "subtitles" / "final.srt") if args.subtitle_choice == "enabled" else "",
            "raw_asr_output": str(project_dir / "subtitles" / "final.raw-asr.srt") if args.subtitle_choice == "enabled" else "",
            "subtitle_audit_output": str(project_dir / "subtitles" / "final.audit.json") if args.subtitle_choice == "enabled" else "",
            "burn_audit_output": str(project_dir / "subtitles" / "burn.audit.json") if args.subtitle_choice == "enabled" else "",
        })
        subtitle_errors = enabled_subtitle_contract_errors(subtitle_plan)
        if subtitle_errors:
            raise ScriptError("; ".join(subtitle_errors))

        video_source_asset, asset_warnings, video_source_reason = select_video_source_asset(
            product_asset,
            references,
            model,
            generated_references,
        )
        video_reference_assets, reference_prompt_map, reference_warnings = build_video_reference_assets(
            product_asset,
            references,
            model,
            generated_references,
        )
        validate_talent_references(
            talent_contract,
            video_reference_assets,
            require_presenter_reference=bool(model.get("require_generated_video_references")),
        )
        visual_design_contract = build_visual_design_contract(
            brief_data,
            visual_direction,
            reference_strategy,
            reference_prompt_map,
            model,
            product_identity_evidence,
            storyboard_preview_asset,
        )
        require_generated_references = bool(model.get("require_generated_video_references"))
        confirmed_reference_assets = video_reference_assets if require_generated_references else references
        generated_product_reference = next(
            (asset for asset in video_reference_assets if str(asset.get("role") or "").lower() == "product"),
            {},
        )
        visual_bible = {
            "product_evidence": product_asset,
            "product_identity_evidence": product_identity_evidence,
            "product_reference": generated_product_reference or product_asset,
            "style": brief_data.get("style", "premium social-commerce ad"),
            "palette": brief_data.get("palette", "clean commercial lighting, product colors preserved"),
            "camera": brief_data.get("camera", "smooth push-in, macro details, stable hero shot"),
            "provider_text_policy": "clean_frames_no_newly_generated_written_elements",
            "local_subtitle_style": subtitle_style if subtitle_plan.get("enabled") else "disabled",
            "consistency_rule": (
                "Use the same approved generated campaign controls, aspect ratio, resolution, style suffix, and campaign promise for every segment. "
                "Raw user evidence remains factual input and is never uploaded to the generated-controls-only reference route."
                if require_generated_references
                else "Reuse the same product reference, aspect ratio, resolution, style suffix, and campaign promise for every segment."
            ),
            "speaker_mode": speaker_mode,
            "talent_contract": talent_contract,
            "product_motion_policy": product_motion_policy,
            "commerce_platform": platform,
            "platform": platform,
            "placement": placement,
            "creative_variant": creative_variant,
            "commerce_scenario": scenario_contract["commerce_scenario"],
            "reference_strategy": reference_strategy,
            "safe_zone_profile": safe_zone_profile,
        }
        asset_warnings.extend(reference_warnings)
        asset_warnings.extend(strategy_warnings)
        if len(video_reference_assets) > 1 and model.get("max_duration_multi_reference_seconds"):
            max_duration = min(max_duration, int(model.get("max_duration_multi_reference_seconds")))
        elif video_reference_assets and model.get("max_duration_with_references_seconds"):
            max_duration = min(max_duration, int(model.get("max_duration_with_references_seconds")))
        if video_reference_assets and model.get("allowed_multi_reference_duration_seconds"):
            allowed_slots = model.get("allowed_multi_reference_duration_seconds") or []
        else:
            allowed_slots = model.get("allowed_duration_seconds") or list(range(min_duration, max_duration + 1))
        max_duration = min(max_duration, int(model.get("planning_max_duration_seconds") or max_duration))
        if (
            segment_strategy == "auto"
            and duration <= 15
            and model.get("key") in {"grok_video_15_reference", "grok_video_15_reference_xai"}
        ):
            segment_strategy = "single_clip"
        forced_count = len(segment_sources) if reference_strategy == "per_segment_source_frames" else None
        preferred_sequence = None
        allow_extra_count = False
        duration_plan, segment_scripts = build_duration_plan(
            delivery_max_seconds=duration,
            allowed_slots=allowed_slots,
            script_text=spoken_script,
            language=language,
            max_seconds=max_duration,
            forced_count=forced_count,
            allow_extra_count=allow_extra_count,
            preferred_sequence=preferred_sequence,
        )
        segments = duration_plan["request_durations_seconds"]
        director_clip_contracts = build_director_clip_contracts(
            brief_data,
            segments,
            visual_direction,
            enable_timecoded_beats=model.get("input_mode") == "reference-to-video",
        )
        sound_design_contract = build_sound_design_contract(
            brief_data,
            director_clip_contracts,
            native_provider_sound=bool(model.get("supports_audio")),
        )
        creative_contract = {
            "speaker_mode": speaker_mode,
            "product_motion_policy": product_motion_policy,
            "creative_variant": creative_variant,
            "creative_variant_rule": creative_variant_contract(creative_variant, platform),
            "reference_strategy": reference_strategy,
            "reference_strategy_rule": reference_strategy_contract(reference_strategy, model),
            "commerce_platform": platform,
            "platform": platform,
            "placement": placement,
            "campaign_goal": campaign_goal,
            "funnel_stage": funnel_stage,
            "commerce_scenario": scenario_contract["commerce_scenario"],
            "cta_type": cta_type,
            "offer": offer,
            "sku": sku,
            "asin": asin,
            "product_url": product_url,
            "shop_destination": shop_destination,
            "marketplace_locale": marketplace_locale,
            "segment_strategy": segment_strategy,
            "product_category": product_category,
            "product_name": product_name,
            "product_price": product_price,
            "selling_points": selling_points,
            "audience": audience,
            "cta_text": cta_text,
            "seller_persona": seller_persona,
            "style_type": style_type,
            "talent_effects_contract": talent_effects_contract,
            "talent_contract": talent_contract,
            "commercial_strategy": commercial_strategy_contract,
            "product_director_profile": product_director_profile,
            "default_speaker_rule": "The director chooses visible talent only when it strengthens desire, trust, scale, use proof or emotion; speech uses the approved sound strategy.",
            "default_motion_rule": "Ordinary physical products are inanimate/passive unless the user or product analysis identifies a real live subject or demonstrated mechanism.",
        }
        asset_contract = {
            "product_asset": product_asset,
            "product_assets": product_assets,
            "input_evidence_assets": input_evidence_assets,
            "product_identity_evidence": product_identity_evidence,
            "product_identity_evidence_asset_ids": [
                str(asset.get("id")) for asset in product_identity_evidence
            ],
            "product_identity_evidence_policy": "all_trustworthy_same_sku_views_ordered_once_then_reused_for_every_product_dependent_imagegen_call",
            "imagegen_input_record_policy": "record_ordered_asset_ids_paths_and_sha256_for_each_generated_reference_before_stage_2",
            "raw_inputs_provider_upload_allowed": False,
            "raw_product_inputs_provider_upload_allowed": bool(model.get("raw_product_assets_are_provider_inputs")),
            "raw_non_product_inputs_provider_upload_allowed": bool(model.get("raw_non_product_assets_are_provider_inputs", not require_generated_references)),
            "video_source_asset": video_source_asset,
            "video_source_reason": video_source_reason,
            "segment_source_assets": segment_sources,
            "confirmed_references": confirmed_reference_assets,
            "generated_reference_assets": generated_references,
            "approval_preview_assets": [storyboard_preview_asset] if storyboard_preview_asset else [],
            "video_reference_assets": video_reference_assets,
            "reference_prompt_map": reference_prompt_map,
            "reference_asset_policy": model.get("reference_asset_policy", "provider_specific"),
            "generated_reference_rule": (
                "Every Provider reference is generated from the approved visual plan. The first reference is a faithful professional product master; no raw or merely cropped user image may enter the payload."
                if require_generated_references
                else "Provider-specific reference selection applies."
            ),
            "storyboard_rule": (
                "Storyboard/contact sheet is a review-only approval preview and is never uploaded to reference-to-video."
                if require_generated_references
                else "Provider-specific storyboard support applies."
            ),
            "model_supports_multiple_references": model_supports_reference_images(model),
            "model_input_mode": model.get("input_mode") or model.get("mode"),
            "source_image_field": model.get("source_image_field", "image"),
            "reference_field": model.get("reference_field", "reference_images"),
            "reference_payload_format": model.get("reference_payload_format", "url_objects"),
            "reference_prompt_style": model.get("reference_prompt_style", "angle"),
            "reference_index_base": int(model.get("reference_index_base", 1)),
            "mode_exclusivity_rule": (
                "reference_images and image are mutually exclusive"
                if model.get("reference_mode_exclusive_with_source")
                else "provider-specific"
            ),
            "single_image_model_rule": (
                "For single-image image-to-video models, the video_source_asset must be the same confirmed visual the user approved. "
                "If the proposal used generated presenter/storyboard references, generate or choose one final source image containing the product, presenter, and scene, then pass it with --video-source-image or role=video_source."
            ),
            "warnings": asset_warnings,
        }

        edit_boundaries = [
            {
                "after_clip": director_clip_contracts[index]["clip_id"],
                "before_clip": director_clip_contracts[index + 1]["clip_id"],
                "outgoing_exit_state": director_clip_contracts[index]["exit_state"],
                "incoming_entry_state": director_clip_contracts[index + 1]["entry_state"],
                "stitch_motivation": director_clip_contracts[index]["stitch_motivation"],
                "audio_bridge": director_clip_contracts[index]["audio_bridge"],
                "complete_action_boundary_required": True,
            }
            for index in range(max(0, len(director_clip_contracts) - 1))
        ]
        continuity_plan = {
            "mode": "planned_cut",
            "reason": "Commerce ads use intentional hook/demo/proof/CTA cuts instead of promising a seamless generated one-take.",
            "shared_visual_bible": True,
            "source_strategy": reference_strategy,
            "last_frame_relay": False,
            "semantic_beat_split_allowed": False,
            "edit_boundaries": edit_boundaries,
        }
        production_contract = {
            "base_request_count": len(segments),
            "approved_paid_cap": len(segments),
            "repair_reserve": 0,
            "per_shot_repair_limit": 0,
            "max_generated_seconds": sum(segments),
            "one_provider_post_per_shot": True,
            "ambiguous_submission_policy": "stop_without_resubmit",
            "no_cost_postproduction_allowed": True,
        }
        audio_contract = {
            "language": language,
            "native_provider_audio": bool(model.get("supports_audio")),
            "speech_mode": speaker_mode,
            "speech_required": bool(spoken_script.strip()),
            "voice_policy": voice_policy,
            "voice_id": preset_voice_ids[0] if len(preset_voice_ids) == 1 else "",
            "voice_selection_reason": voice_selection_reason,
            "voice_description": voice_description if spoken_script.strip() else "",
            "voice_gender": voice_gender,
            "voice_prompt_token": "<AUDIO_0>" if preset_voice_ids else "",
            "speech_verification_required": bool(spoken_script.strip()),
            "dialogue_prompt_contains_approved_script": True,
            "provider_output_word_for_word_guaranteed": False,
            "delivery_acceptance": "speech_intelligible_and_main_selling_meaning_preserved",
            "preset_voice_ids": preset_voice_ids,
            "preset_voice_source": preset_voice_source,
            "reference_audio_field": model.get("reference_audio_field") or "",
            "reference_audio_optional": True,
            "voice_roster_required": False,
            "custom_voice_file_upload_allowed": bool(model.get("supports_custom_voice_file_reference")),
            "custom_voice_file_rule": (
                "allowed only when the selected Provider contract explicitly enables trusted-partner custom voice files"
                if model.get("supports_custom_voice_file_reference")
                else "blocked; use prompt-directed native speech or an explicitly selected preset voice_id"
            ),
        }
        stitching_plan = {
            "required": len(segments) > 1,
            "audio_boundary_policy": "pcm_intermediates_no_fades_or_crossfades_single_final_aac_encode",
            "editorial_boundary_policy": "cut_only_after_complete_visible_action_in_a_stable_exit_state",
            "edit_boundaries": edit_boundaries,
            "sound_continuity_policy": "restate_full_sonic_fingerprint_per_clip_and_preserve_complete_voice_sentences",
            "native_cross_clip_audio_state_shared": False,
            "exact_score_continuity_requires_local_post_mix": True,
            "loudness_consistency_review_required": len(segments) > 1,
            "per_clip_fades_applied": False,
            "crossfade_applied": False,
            "intermediate_audio_codec": "pcm_s16le",
            "single_final_aac_encode": True,
            "tail_trim_policy": "verified_idle_tail_only",
        }
        quality_contract = {
            "delivery_review_policy": "technical_ready",
            "stage_2_actual_images_are_primary_visual_approval": True,
            "post_generation_business_review_required": False,
            "post_generation_business_review_available": True,
            "sound_review_blocking": False,
            "speech_verification_required": bool(spoken_script.strip()),
            "audio_track_is_not_speech_proof": True,
            "audio_track_is_not_sound_design_proof": True,
            "planned_non_speech_sound_verification_required": sound_design_contract["verification_required"],
            "max_provider_duration_shortfall_seconds": 1.0,
            "max_final_end_hold_seconds": 1.0,
            "long_static_padding_allowed": False,
            "missing_or_unintelligible_speech_blocks_delivery": bool(spoken_script.strip()),
        }

        shots = []
        cursor = 0
        for index, seconds in enumerate(segments, start=1):
            shot_id = f"shot_{index:02d}"
            shot_source_asset = segment_sources[index - 1] if reference_strategy == "per_segment_source_frames" else video_source_asset
            segment_script = segment_scripts[index - 1]
            script_boundary = build_script_boundary(segment_script, index, len(segments))
            if segment_script and not script_boundary["stitch_safe"]:
                raise ScriptError(
                    f"{shot_id} spoken script does not end on a stitch-safe complete sentence: {segment_script!r}"
                )
            compiled_prompt = compile_model_prompt(
                visual_direction,
                seconds,
                project_name,
                speaker_mode,
                product_motion_policy,
                platform,
                seller_persona,
                creative_variant,
                reference_strategy,
                model,
                shot_source_asset,
                video_reference_assets,
                platform_contract,
                scenario_contract,
                compliance_contract,
                spoken_script=segment_script,
                segment_index=index,
                segment_total=len(segments),
                director_clip=director_clip_contracts[index - 1],
                voice_reference_tokens=[f"<AUDIO_{i}>" for i in range(len(preset_voice_ids))],
                voice_description=voice_description,
                commercial_strategy=commercial_strategy_contract,
                talent_contract=talent_contract,
                sound_design_contract=sound_design_contract,
            )
            shots.append({
                "id": shot_id,
                "duration_seconds": seconds,
                "start_second": cursor,
                "end_second": cursor + seconds,
                "reference_strategy": reference_strategy,
                "spoken_script": segment_script,
                "script_estimated_seconds": estimate_spoken_seconds(segment_script, language=language),
                "script_boundary": script_boundary,
                "continuity_mode": (
                    "single_generation_continuous_sequence"
                    if len(segments) == 1 and director_clip_contracts[index - 1].get("shot_mode") == "continuous_sequence"
                    else (
                        "single_generation_timecoded_beats"
                        if len(segments) == 1 and director_clip_contracts[index - 1].get("beat_timeline")
                        else "planned_cut"
                    )
                ),
                "director_clip": director_clip_contracts[index - 1],
                "prompt": compiled_prompt["prompt"],
                "prompt_contract": compiled_prompt["contract"],
                "image": shot_source_asset,
                "references": confirmed_reference_assets,
                "video_references": video_reference_assets,
                "reference_prompt_map": reference_prompt_map,
                "request_file": str(requests_dir / f"{shot_id}_request.json"),
                "clip_file": str(clips_dir / f"{shot_id}.mp4"),
            })
            cursor += seconds

        manifest = {
            "plan_schema_version": PLAN_SCHEMA_VERSION,
            "project_name": project_name,
            "created_at": stamp,
            "project_dir": str(project_dir),
            "model_key": model["key"],
            "model": model.get("model"),
            "mode": model.get("mode"),
            "total_duration_seconds": duration,
            "delivery_max_seconds": duration,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "product_asset": product_asset,
            "references": confirmed_reference_assets,
            "input_evidence_assets": input_evidence_assets,
            "generated_reference_assets": generated_references,
            "approval_preview_assets": [storyboard_preview_asset] if storyboard_preview_asset else [],
            "brief": brief_data,
            "language": language,
            "spoken_script": spoken_script,
            "visual_bible": visual_bible,
            "continuity_plan": continuity_plan,
            "duration_plan": duration_plan,
            "duration_plan_digest": duration_plan["duration_plan_digest"],
            "subtitle_plan": subtitle_plan,
            "production_contract": production_contract,
            "audio_contract": audio_contract,
            "sound_design_contract": sound_design_contract,
            "quality_contract": quality_contract,
            "stitching_plan": stitching_plan,
            "creative_contract": creative_contract,
            "product_director_profile": product_director_profile,
            "platform_contract": platform_contract,
            "scenario_contract": scenario_contract,
            "compliance_contract": compliance_contract,
            "asset_contract": asset_contract,
            "reference_asset_contract": asset_contract,
            "visual_design_contract": visual_design_contract,
            "model_capability_contract": model_capability_contract,
            "shots": shots,
        }
        write_json(project_dir / "manifest.json", manifest)
        write_json(project_dir / "generation-plan.json", manifest)
        print(json.dumps({"ok": True, "project_dir": str(project_dir), "segments": segments, "plan": str(project_dir / "generation-plan.json")}, ensure_ascii=False, indent=2))
        return 0
    except (ScriptError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
