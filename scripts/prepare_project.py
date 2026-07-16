#!/usr/bin/env python3
"""Prepare an ai-commerce-video project folder and generation plan."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import time
from pathlib import Path

from _common import ScriptError, get_model_config, is_url, load_config, model_supports_reference_images, prompt_limits, sanitize_name, write_json
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
REFERENCE_STRATEGIES = ("auto", "single_source_frame", "storyboard_sheet_reference", "per_segment_source_frames", "multi_reference_storyboard")
SEGMENT_STRATEGIES = ("auto", "single_clip", "split_by_duration", "per_scene_segments", "stitch_segments")
VIDEO_SOURCE_ROLE_PRIORITY = (
    "video_source",
    "final_source",
    "final_frame",
    "first_frame",
    "hero_frame",
    "presenter_product",
    "product_presenter",
)
PROMPT_COMPILER_VERSION = "compact-commerce-v1"


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
        supports_audio = bool(payload_defaults.get("generate_audio")) or model.get("provider") in {"119337", "fal_queue"}
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
        "source_image_field": model.get("source_image_field", "image"),
        "reference_field": model.get("reference_field", "reference_images"),
        "reference_payload_format": model.get("reference_payload_format", "url_objects"),
        "min_duration_seconds": int(model.get("min_duration_seconds", 1)),
        "max_duration_seconds": int(model.get("max_duration_seconds", 15)),
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
        "prompt_compiler": PROMPT_COMPILER_VERSION,
        "supports_audio": bool(supports_audio),
        "supports_lip_sync": bool(model.get("supports_lip_sync", True)),
        "supports_multi_segment_generation": bool(model.get("supports_multi_segment_generation", True)),
        "capability_source": "model config",
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
            (r"\bsoft plush motion\b", "soft camera movement around the plush"),
            (r"\bsubtle plush motion\b", "subtle camera movement around the plush"),
            (r"\bsoft product motion\b", "soft camera movement around the product"),
            (r"\bsubtle product motion\b", "subtle camera movement around the product"),
            (r"\bthe product moves\b", "the presenter moves the product by hand"),
            (r"\bthe toy moves\b", "the presenter moves the toy by hand"),
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


def prompt_contract(speaker_mode: str, product_motion_policy: str, commerce_platform: str, seller_persona: str) -> str:
    lines = [f"Commercial guardrail: {commerce_platform} product ad; keep product, proof, trust, and CTA clear."]
    if speaker_mode == "digital-human-spoken":
        lines.append(
            f"Speaking mode: the visible {seller_persona} is the presenter; speak to camera with natural lip sync, no detached voiceover."
        )
    elif speaker_mode == "voiceover":
        lines.append("Speaking mode: use off-screen voiceover; any visible model demonstrates silently or with minimal natural reactions.")
    else:
        lines.append("Speaking mode: no spoken audio; communicate through product demonstration, camera, hands, and approved packaging identity.")

    lines.append(
        "Clean Provider frame policy: no newly generated written or typographic elements. "
        "Preserve approved packaging marks; invent no other labels, price/CTA cards, or UI."
    )

    if product_motion_policy == "static-inanimate":
        lines.append(
            "Product motion policy: this is an inanimate physical product. It must not blink, breathe, talk, walk, gesture, or act alive. "
            "Only presenter, hands, camera, lighting, props, or turntable may move it; preserve identity, shape, color, material, and proportions."
        )
    elif product_motion_policy == "demonstrated-function":
        lines.append("Product motion policy: show only real product function or mechanism; avoid fantasy movement unrelated to the product's real use.")
    elif product_motion_policy == "live-subject":
        lines.append("Product motion policy: the subject is live; keep motion natural, safe, and realistic.")
    elif product_motion_policy == "software-screen":
        lines.append("Product motion policy: show UI/screen interactions clearly; avoid unrelated physical object animation.")
    else:
        lines.append("Product motion policy: fluid or food motion may be natural, such as pouring, steam, melting, or mixing; keep the product appetizing and realistic.")
    return " ".join(lines)


def reference_strategy_contract(reference_strategy: str, model: dict) -> str:
    model_name = model.get("model", "configured video model")
    if reference_strategy == "per_segment_source_frames":
        return (
            f"Reference strategy: per_segment_source_frames for {model_name}. "
            "This shot uses its own approved source/first-frame image and should become one segment in a stitched final ad. "
            "Do not treat any storyboard sheet as an uploaded video source for this single-image route."
        )
    if reference_strategy == "storyboard_sheet_reference":
        return (
            f"Reference strategy: storyboard_sheet_reference for {model_name}. "
            "Use the uploaded storyboard sheet only for shot order, timing, and rhythm. Render full-screen video; do not reproduce grid panels, borders, labels, or a collage layout."
        )
    if reference_strategy == "multi_reference_storyboard":
        return (
            f"Reference strategy: multi_reference_storyboard for {model_name}. "
            "Use product, presenter, scene, and storyboard references together. The storyboard controls sequence and rhythm only; identity comes from product and presenter references."
            " Render full-screen video; do not reproduce grid panels, borders, labels, or a collage layout."
        )
    return (
        f"Reference strategy: single_source_frame for {model_name}. "
        "Use one approved source/first-frame image for a continuous video segment."
    )


def creative_variant_contract(creative_variant: str, commerce_platform: str) -> str:
    if creative_variant == "story_reversal":
        return (
            f"Creative variant: story_reversal lifestyle story-seeding ad for {commerce_platform}. "
            "The video must include a clear story hook in the first 3 seconds, one simple conflict or pain point, "
            "a concise reversal, the product as the solution that explains the reversal, and a direct CTA. "
            "Keep the product visible and commercially useful; do not make a pure story where the product appears only at the end."
        )
    if creative_variant == "hybrid":
        return (
            f"Creative variant: hybrid ad for {commerce_platform}. "
            "Open with a short lifestyle/story hook, then quickly switch to direct product proof, selling points, demonstration, and CTA. "
            "Balance attention and conversion; product clarity wins over plot complexity."
        )
    if creative_variant == "ugc_review":
        return (
            f"Creative variant: ugc_review buyer-perspective ad for {commerce_platform}. "
            "Use a real-feeling first-person review, natural product handling, honest experience details, one or two concrete selling points, "
            "and a clear CTA. Do not invent fake personal results, fake authority, or unverifiable testimonial claims."
        )
    if creative_variant == "comparison_test":
        return (
            f"Creative variant: comparison_test product comparison ad for {commerce_platform}. "
            "Set up a fair side-by-side or before/after-style test, compare objective features and usage outcomes, then explain the product advantage and CTA. "
            "Avoid malicious competitor attacks, trademark misuse, or claims that are not supported by supplied evidence."
        )
    if creative_variant == "lifestyle_seed":
        return (
            f"Creative variant: lifestyle_seed social seeding ad for {commerce_platform}. "
            "Place the product in an aspirational but believable daily scenario, show why it belongs in the user's lifestyle, keep the product visible, "
            "and use a soft CTA suited to saving, comparing, asking, or shopping."
        )
    if creative_variant == "premium_brand":
        return (
            f"Creative variant: premium_brand high-end brand ad for {commerce_platform}. "
            "Emphasize design, material, craftsmanship, restraint, and brand feeling. Use clean composition and premium pacing; "
            "do not turn the ad into low-price shouting, noisy stickers, or discount-first hard selling."
        )
    if creative_variant == "feature_demo":
        return (
            f"Creative variant: feature_demo functional product demonstration for {commerce_platform}. "
            "Show the product feature clearly, demonstrate real use, include close-up proof, and end with a concise CTA."
        )
    if creative_variant == "unboxing":
        return (
            f"Creative variant: unboxing first-impression product ad for {commerce_platform}. "
            "Show package reveal, product details, tactile handling, setup or first use, and a buying reason without inventing included accessories."
        )
    if creative_variant == "live_shopping_teaser":
        return (
            f"Creative variant: live_shopping_teaser ad for {commerce_platform}. "
            "Preview the live-room value, show hero product and limited offer or demo reason, create urgency honestly, and drive viewers to the live/shop destination."
        )
    if creative_variant == "retargeting_offer":
        return (
            f"Creative variant: retargeting_offer remarketing ad for {commerce_platform}. "
            "Remind the viewer of the product benefit, answer one likely objection, show the offer or trust proof, and give a direct CTA without fake scarcity."
        )
    return (
        f"Creative variant: commerce_direct conversion-focused product ad for {commerce_platform}. "
        "Prioritize clear product exposure, presenter selling, function, material, price or offer if provided, usage scene, purchase reason, proof, and CTA."
    )


def platform_prompt_contract(platform_contract: dict) -> str:
    if not platform_contract:
        return ""
    return strip_provider_caption_terms(
        f"Platform contract: {platform_contract.get('display_name')}, {platform_contract.get('actual_aspect_ratio')}, "
        f"structure={platform_contract.get('recommended_structure')}. Safe zone profile: {platform_contract.get('safe_zone_profile')}. "
        f"CTA: {platform_contract.get('cta_type')}; keep product clear."
    )


def scenario_prompt_contract(scenario_contract: dict) -> str:
    if not scenario_contract:
        return ""
    return (
        f"Commerce scenario: {scenario_contract.get('commerce_scenario')}. "
        f"Structure: {scenario_contract.get('typical_structure')}. "
        f"Risk: {scenario_contract.get('risk_control')}."
    )


def compliance_prompt_contract(compliance_contract: dict) -> str:
    if not compliance_contract:
        return ""
    return (
        f"Compliance contract: risk {compliance_contract.get('claim_risk')} for {compliance_contract.get('product_category')}. "
        "Use supplied facts only; invent no efficacy, safety, certification, price/discount/availability, before-after, authority, or personal results. "
        "UGC/review must sound like a real experience."
    )


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
                "For grok-video-1.5 or other single-image routes, use per_segment_source_frames."
            )
        if not storyboard_reference_present(references):
            warnings.append(f"reference_strategy {strategy} selected but no reference role=storyboard was provided.")
    return strategy, warnings


def reference_token(index: int, style: str | None) -> str:
    normalized = (style or "angle").strip().lower()
    if normalized in {"seedance_at", "at", "paren_at", "img_at"}:
        return f"@(img{index})"
    if normalized in {"at_image", "seedance_image"}:
        return f"@Image{index}"
    return f"<IMAGE_{index}>"


def asset_identity(asset: dict) -> str:
    return str(asset.get("value") or asset.get("path") or asset.get("url") or "")


def with_role(asset: dict, role: str, asset_id: str) -> dict:
    result = dict(asset)
    result.setdefault("role", role)
    result.setdefault("id", asset_id)
    return result


def select_video_source_asset(product_asset: dict, references: list[dict], model: dict) -> tuple[dict, list[str], str]:
    warnings: list[str] = []
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


def build_video_reference_assets(product_asset: dict, references: list[dict], model: dict) -> tuple[list[dict], list[dict], list[str]]:
    warnings: list[str] = []
    if not model_supports_reference_images(model):
        return [], [], warnings

    include_product = bool(model.get("include_product_as_reference")) or (model.get("input_mode") == "reference-to-video")
    max_references = int(model.get("max_reference_images") or len(references) or 1)
    candidates: list[dict] = []
    if include_product:
        candidates.append(with_role(product_asset, "product", "product"))
    candidates.extend(dict(ref) for ref in references)

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
    for index, asset in enumerate(deduped, start=1):
        token = reference_token(index, style)
        item = dict(asset)
        item["ref_index"] = index
        item["prompt_token"] = token
        mapped.append(item)
        prompt_map.append({
            "token": token,
            "role": item.get("role", "reference"),
            "value": asset_identity(item),
        })
    return mapped, prompt_map, warnings


def reference_prompt_contract(model: dict, video_source_asset: dict, video_reference_assets: list[dict]) -> str:
    parts: list[str] = []
    source_token = model.get("source_prompt_token")
    source_is_uploaded = not video_reference_assets or bool(model.get("include_source_image_with_references", True))
    if source_token and source_is_uploaded:
        parts.append(
            f"Source image rule: {source_token} is the approved source frame; preserve product identity, presenter, scene, colors, proportions, and composition."
        )
    if video_reference_assets:
        mapping = "; ".join(
            f"{asset.get('prompt_token')} = {asset.get('role', 'reference')} reference"
            for asset in video_reference_assets
        )
        parts.append(
            f"Reference image map: {mapping}. Use them for identity and continuity; do not invent a different product, presenter, scene, or storyboard context."
        )
    elif model_supports_reference_images(model):
        parts.append("Reference image map: no extra reference images were provided; rely on the uploaded source/product image only.")
    elif not parts:
        parts.append(
            "Single-source rule: this model route cannot use separate reference images, so the uploaded source image must already contain the approved product, presenter, and scene."
        )
    return " ".join(parts)


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
) -> dict:
    if base_prompt:
        prompt = sanitize_prompt_text(base_prompt, speaker_mode, product_motion_policy)
    else:
        prompt = (
            f"{seconds}-second vertical e-commerce product ad segment for {project_name}. "
            "Show the hero product clearly, preserve product appearance, use clean commercial lighting, "
            "smooth camera motion, natural presenter delivery, and a clear selling moment."
        )
    if segment_total <= 1:
        segment_focus = "hook, product proof, and CTA inside one complete commercial beat"
    elif segment_index == 1:
        segment_focus = "opening hook, product reveal, and first proof; end on an intentional commercial cut"
    elif segment_index == segment_total:
        segment_focus = "final proof, buying reason, and CTA; finish the complete message"
    else:
        segment_focus = "product demonstration and trust proof; end on an intentional commercial cut"
    speech_contract = (
        f"Spoken dialogue for this segment only: {spoken_script.strip()} "
        "Speak the complete words naturally with a brief neutral head and tail pause; do not repeat another segment's opening."
        if spoken_script.strip()
        else "No approved spoken dialogue was supplied for this segment; do not invent price, offer, efficacy, or policy facts."
    )
    components = [
        {"name": "visual_direction", "text": prompt.strip(), "planning_only": False},
        {
            "name": "segment_and_speech",
            "text": f"Segment {segment_index} of {segment_total}: {segment_focus}. {speech_contract}",
            "planning_only": False,
        },
        {"name": "creative_variant", "text": creative_variant_contract(creative_variant, commerce_platform), "planning_only": False},
        {"name": "platform", "text": platform_prompt_contract(platform_contract), "planning_only": True},
        {"name": "scenario", "text": scenario_prompt_contract(scenario_contract), "planning_only": True},
        {"name": "compliance", "text": compliance_prompt_contract(compliance_contract), "planning_only": False},
        {
            "name": "reference_strategy",
            "text": ""
            if reference_strategy == "single_source_frame" and model.get("source_prompt_token")
            else reference_strategy_contract(reference_strategy, model),
            "planning_only": False,
        },
        {"name": "reference_identity", "text": reference_prompt_contract(model, video_source_asset, video_reference_assets), "planning_only": False},
        {
            "name": "render_guardrails",
            "text": prompt_contract(speaker_mode, product_motion_policy, commerce_platform, seller_persona),
            "planning_only": False,
        },
    ]
    for component in components:
        component["text"] = strip_provider_caption_terms(component["text"])
    active = [component for component in components if component["text"]]
    budget_chars, max_chars = prompt_limits(model)
    if budget_chars is not None and max_chars is not None and budget_chars > max_chars:
        raise ScriptError(
            f"Invalid model prompt limits: prompt_budget_chars={budget_chars} exceeds max_prompt_chars={max_chars}"
        )

    def render(items: list[dict]) -> str:
        return " ".join(item["text"] for item in items).strip()

    compiled = render(active)
    omitted: list[str] = []
    if budget_chars is not None and len(compiled) > budget_chars:
        for optional_name in ("scenario", "platform"):
            optional = next((item for item in active if item["name"] == optional_name), None)
            if optional is None:
                continue
            active.remove(optional)
            omitted.append(optional_name)
            compiled = render(active)
            if len(compiled) <= budget_chars:
                break
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
    return {
        "prompt": compiled,
        "contract": {
            "compiler": PROMPT_COMPILER_VERSION,
            "char_count": len(compiled),
            "utf8_bytes": len(compiled.encode("utf-8")),
            "budget_chars": budget_chars,
            "max_chars": max_chars,
            "included_components": [item["name"] for item in active],
            "omitted_planning_components": omitted,
            "component_char_counts": {item["name"]: len(item["text"]) for item in active},
            "truncated": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Project name")
    parser.add_argument("--project-root", default="projects", help="Root folder for generated projects")
    parser.add_argument("--product-image", required=True, help="Product image path, URL, or data URI")
    parser.add_argument("--reference-image", action="append", default=[], help="Optional reference image as path/url or role=path/url. Repeat for model, scene, storyboard, etc.")
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
    parser.add_argument("--language", default="zh", help="Spoken language used for pacing estimates and semantic segmentation")
    parser.add_argument("--brief", help="Optional project brief JSON")
    parser.add_argument("--config", help="Path to model config JSON")
    parser.add_argument("--speaker-mode", choices=SPEAKER_MODES, default=None, help="Presenter/speech mode. Default: digital-human-spoken")
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
            brief_data = json.loads(Path(args.brief).expanduser().read_text(encoding="utf-8"))
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

        product_asset = copy_or_record_asset(args.product_image, assets_dir)
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
        references = [copy_or_record_reference(item, assets_dir, i) for i, item in enumerate(reference_inputs, start=1)]
        segment_sources = [copy_or_record_segment_source(item, assets_dir, i) for i, item in enumerate(args.segment_source_image, start=1)]
        segment_sources = sorted(segment_sources, key=lambda item: int(item.get("segment_index", 0)))
        expected_indices = list(range(1, len(segment_sources) + 1))
        actual_indices = [int(item.get("segment_index", 0)) for item in segment_sources]
        if actual_indices != expected_indices:
            raise ScriptError(f"Segment source images must be contiguous from shot_01. Got indices: {actual_indices}")
        default_speaker_mode = "silent-captions" if selected_platform_profile.get("audio_policy") == "no_audio" or selected_platform_profile.get("speaker_policy") == "avoid_talking_head" else "digital-human-spoken"
        speaker_mode = coerce_choice(args.speaker_mode or brief_data.get("speaker_mode") or default_speaker_mode, SPEAKER_MODES, "speaker_mode")
        product_motion_policy = coerce_choice(args.product_motion_policy or brief_data.get("product_motion_policy") or "static-inanimate", PRODUCT_MOTION_POLICIES, "product_motion_policy")
        creative_variant = coerce_choice(args.creative_variant or brief_data.get("creative_variant") or "commerce_direct", CREATIVE_VARIANTS, "creative_variant")
        commerce_scenario = coerce_choice(args.commerce_scenario or brief_data.get("commerce_scenario") or "auto", COMMERCE_SCENARIOS, "commerce_scenario")
        segment_strategy = coerce_choice(args.segment_strategy or brief_data.get("segment_strategy") or "auto", SEGMENT_STRATEGIES, "segment_strategy")
        reference_strategy, strategy_warnings = resolve_reference_strategy(args.reference_strategy or brief_data.get("reference_strategy"), model, references, segment_sources)
        product_category = args.product_category or brief_data.get("product_category") or "unknown"
        seller_persona = args.seller_persona or brief_data.get("seller_persona") or "synthetic e-commerce presenter"
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
            "lexical_source": "confirmed_script" if spoken_script else "final_audio_transcript",
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

        visual_bible = {
            "product_reference": product_asset,
            "style": brief_data.get("style", "premium social-commerce ad"),
            "palette": brief_data.get("palette", "clean commercial lighting, product colors preserved"),
            "camera": brief_data.get("camera", "smooth push-in, macro details, stable hero shot"),
            "provider_text_policy": "clean_frames_no_newly_generated_written_elements",
            "local_subtitle_style": subtitle_style if subtitle_plan.get("enabled") else "disabled",
            "consistency_rule": "Reuse the same product reference, aspect ratio, resolution, style suffix, and campaign promise for every segment.",
            "speaker_mode": speaker_mode,
            "product_motion_policy": product_motion_policy,
            "commerce_platform": platform,
            "platform": platform,
            "placement": placement,
            "creative_variant": creative_variant,
            "commerce_scenario": scenario_contract["commerce_scenario"],
            "reference_strategy": reference_strategy,
            "safe_zone_profile": safe_zone_profile,
        }
        video_source_asset, asset_warnings, video_source_reason = select_video_source_asset(product_asset, references, model)
        video_reference_assets, reference_prompt_map, reference_warnings = build_video_reference_assets(product_asset, references, model)
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
        forced_count = len(segment_sources) if reference_strategy == "per_segment_source_frames" else None
        duration_plan, segment_scripts = build_duration_plan(
            delivery_max_seconds=duration,
            allowed_slots=allowed_slots,
            script_text=spoken_script,
            language=language,
            max_seconds=max_duration,
            forced_count=forced_count,
        )
        segments = duration_plan["request_durations_seconds"]
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
            "seller_persona": seller_persona,
            "default_speaker_rule": "Visible model/digital-human spoken selling unless the user explicitly requests voiceover or silent captions.",
            "default_motion_rule": "Ordinary physical products are inanimate/passive unless the user or product analysis identifies a real live subject or demonstrated mechanism.",
        }
        asset_contract = {
            "product_asset": product_asset,
            "video_source_asset": video_source_asset,
            "video_source_reason": video_source_reason,
            "segment_source_assets": segment_sources,
            "confirmed_references": references,
            "video_reference_assets": video_reference_assets,
            "reference_prompt_map": reference_prompt_map,
            "model_supports_multiple_references": model_supports_reference_images(model),
            "model_input_mode": model.get("input_mode") or model.get("mode"),
            "source_image_field": model.get("source_image_field", "image"),
            "reference_field": model.get("reference_field", "reference_images"),
            "reference_payload_format": model.get("reference_payload_format", "url_objects"),
            "reference_prompt_style": model.get("reference_prompt_style", "angle"),
            "single_image_model_rule": (
                "For single-image image-to-video models, the video_source_asset must be the same confirmed visual the user approved. "
                "If the proposal used generated presenter/storyboard references, generate or choose one final source image containing the product, presenter, and scene, then pass it with --video-source-image or role=video_source."
            ),
            "warnings": asset_warnings,
        }

        continuity_plan = {
            "mode": "planned_cut",
            "reason": "Commerce ads use intentional hook/demo/proof/CTA cuts instead of promising a seamless generated one-take.",
            "shared_visual_bible": True,
            "source_strategy": reference_strategy,
            "last_frame_relay": False,
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
        stitching_plan = {
            "required": len(segments) > 1,
            "audio_boundary_policy": "pcm_intermediates_no_fades_or_crossfades_single_final_aac_encode",
            "per_clip_fades_applied": False,
            "crossfade_applied": False,
            "intermediate_audio_codec": "pcm_s16le",
            "single_final_aac_encode": True,
            "tail_trim_policy": "verified_idle_tail_only",
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
                args.prompt,
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
                "continuity_mode": "planned_cut",
                "prompt": compiled_prompt["prompt"],
                "prompt_contract": compiled_prompt["contract"],
                "image": shot_source_asset,
                "references": references,
                "video_references": video_reference_assets,
                "reference_prompt_map": reference_prompt_map,
                "request_file": str(requests_dir / f"{shot_id}_request.json"),
                "clip_file": str(clips_dir / f"{shot_id}.mp4"),
            })
            cursor += seconds

        manifest = {
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
            "references": references,
            "brief": brief_data,
            "language": language,
            "spoken_script": spoken_script,
            "visual_bible": visual_bible,
            "continuity_plan": continuity_plan,
            "duration_plan": duration_plan,
            "duration_plan_digest": duration_plan["duration_plan_digest"],
            "subtitle_plan": subtitle_plan,
            "production_contract": production_contract,
            "stitching_plan": stitching_plan,
            "creative_contract": creative_contract,
            "platform_contract": platform_contract,
            "scenario_contract": scenario_contract,
            "compliance_contract": compliance_contract,
            "asset_contract": asset_contract,
            "reference_asset_contract": asset_contract,
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
