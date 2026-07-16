# Platform Requirements

Use this reference before writing the first proposal when the user names a platform, ad placement, marketplace, or destination. Treat these rules as a planning snapshot, not a legal guarantee. Recheck the live ad manager before publishing because platform specs change.

## Platform Contract Pattern

Represent platform rules as `platform_contract`, not as hardcoded workflow branches.

Recommended fields:

- `platform`: user-facing platform, such as `tiktok`, `douyin`, `xiaohongshu`, `amazon`, `youtube`, `meta_reels`, or `shopify`.
- `placement`: ad surface, such as `in_feed`, `sponsored_products_video`, `sponsored_brands_video`, `shorts`, `reels`, or `product_page`.
- `recommended_aspect_ratios`, `default_aspect_ratio`, `actual_aspect_ratio`.
- `recommended_duration_seconds`, `min_duration_seconds`, `max_duration_seconds`.
- `audio_policy`, `speaker_policy`, `subtitle_required`, `cta_required`.
- `safe_zone_profile`.
- `product_exposure_rule`, `cta_rule`, `common_risks`, `recommended_structure`, `suitable_variants`.

Keep the main workflow generic: first choose the `platform_contract`, then let the proposal, image plan, `prepare_project.py`, and `validate_platform_plan.py` use it. `subtitle_required` means a viewer-facing local postproduction requirement; it never authorizes Provider-generated subtitles.

## Platform Table

| Platform / placement | Recommended ratio | Recommended length | Spoken presenter | Audio | Subtitles | Product exposure | CTA | Common risks | Good variants |
|---|---|---:|---|---|---|---|---|---|---|
| TikTok / TikTok Shop in-feed | `9:16` preferred; `1:1` and `16:9` may be accepted | 9-15s recommended, platform supports longer formats | Allowed | Recommended, but captions needed | Required for clarity | Strong hook and visible product in first seconds | Clear shop or learn action | UI covers text/CTA, weak hook, exaggerated claims | `story_reversal`, `hybrid`, `ugc_review`, `lifestyle_seed`, `live_shopping_teaser` |
| Douyin / Douyin Shop | `9:16` preferred | 15s default | Allowed | Recommended with subtitles | Required | Vertical product proof, seller credibility, product detail | Shopping/live-room action | Unsafe demos, exaggerated efficacy, shopping anchor overlap | `commerce_direct`, `story_reversal`, `hybrid`, `live_shopping_teaser` |
| Xiaohongshu | `9:16`, `3:4`, or `1:1` | 15-30s | Allowed, but should feel authentic | Allowed | Required | Real-feeling usage and reason to save/compare | Soft CTA | Fake experience, over-filtered before/after, low-quality clickbait | `ugc_review`, `lifestyle_seed`, `unboxing`, `premium_brand` |
| Amazon Sponsored Brands Video | `16:9` or `9:16`; default to `16:9` unless mobile/creator style is requested | 15-30s recommended; keep within placement limits | Allowed, but do not depend on audio | Muted-first | Strongly recommended | Brand/product visible early; product in first 2s and function in first 5s | Amazon-compatible CTA, no fake clickable button inside video | Audio-dependent message, drawn fake buttons, letterboxing, product too small on mobile | `commerce_direct`, `feature_demo`, `premium_brand` |
| Amazon Sponsored Products Video | `16:9`; vertical availability may vary by region/time | 7s+ | Avoid talking-head format | No audio; audio may be removed | Text/feature labels needed | Feature, benefit, or usage; product should dominate the frame | Usually contextual, not a hard spoken CTA | Talking-head video, slideshow feel, audio reliance, off-product branding | `feature_demo`, `commerce_direct`, `comparison_test` |
| YouTube / Shorts | `9:16` for Shorts, `16:9` for horizontal, `1:1` accepted | 6-30s common | Allowed | Useful, but text should support | Recommended | Apply ABCD: Attention, Branding, Connection, Direction | Clear direction | Slow opening, late branding, unclear direction, unsafe overlays | `premium_brand`, `feature_demo`, `lifestyle_seed`, `retargeting_offer` |
| Meta Reels / Instagram Reels | `9:16` preferred | 6-30s common | Allowed | Recommended with captions | Recommended | Native vertical product proof, social reason, CTA | One conversion action | CTA/text hidden by Reels UI | `ugc_review`, `lifestyle_seed`, `premium_brand`, `retargeting_offer` |
| Independent site / Shopify product page | `16:9`, `1:1`, or `9:16` depending layout | 15-45s | Allowed | Optional | Recommended | Product detail, size, material, use case, trust proof | Add to cart / choose option / learn more | Too social, missing product detail, unclear variant | `feature_demo`, `commerce_direct`, `unboxing`, `premium_brand` |

## Notes From Current Source Checks

- TikTok auction in-feed specs list vertical `9:16` as recommended for Non-Spark ads and provide downloadable safe-zone files; ad captions and UI can affect the safe area.
- Amazon Sponsored Products video guidance says audio is removed, video should show features/benefits/usage, the product should be prominent, and talking-head videos are not appropriate.
- Amazon video ad specs recommend `1920 x 1080` / `16:9`, muted autoplay, no letterboxing, and messages that work without sound.
- Google Ads video specs support `16:9`, `9:16`, and `1:1`; YouTube creative guidance uses the ABCD structure: Attention, Branding, Connection, Direction.
- Meta business help and Reels ad guidance emphasize `9:16` vertical assets and safe zones for Reels/Stories UI.
- Xiaohongshu/Juguang public pages emphasize seed-style marketing goals and ongoing governance against low-quality or misleading commercial content; keep review and seeding content authentic.

## Proposal Use

When a user has not specified platform:

1. Pick `marketplace_general`.
2. Present at least two creative options.
3. Include an AI recommendation.
4. Ask the user to choose platform only if platform changes creative structure materially.

When a user specifies platform:

1. State the chosen `platform_contract`.
2. Adjust aspect ratio, subtitles, CTA, safe-zone, and speaker mode.
3. If a placement conflicts with the default spoken-presenter mode, override the default in the plan. Example: Amazon Sponsored Products Video should default to caption/feature-led product demonstration, not digital-human talking head.
4. If captions or disclaimers are needed, keep all Provider frames clean and add the approved text locally after clean-video review.
