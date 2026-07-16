# E-commerce Quality Rules

Use these rules for AI shopping videos, product ads, UGC-style ads, marketplace listing videos, and live-shopping clips.

## Product Analysis

Before writing the proposal, classify the product:

- category and subcategory;
- physical product, software/screen product, food/beverage, liquid/material, live subject, or product with a demonstrated mechanism;
- buyer type and buying scenario;
- primary platform: Taobao, Tmall, Amazon, cross-border e-commerce, Douyin/TikTok shop, Xiaohongshu, independent site, or marketplace-general;
- three selling points: functional value, emotional/visual value, and purchase trigger;
- objections: price, trust, size, quality, use difficulty, compatibility, safety, or shipping;
- proof needed: close-up texture, size in hand, usage demo, before/after, packaging, scenario, offer, or social proof.

## Contract-Driven Planning

Before writing final prompts, create visible contracts:

- `platform_contract`: platform, placement, ratio, duration, audio, subtitles, CTA, safe-zone, product exposure, and common platform risks.
- `scenario_contract`: commerce scenario, storyboard logic, image/reference needs, and risk controls.
- `compliance_contract`: product category risk level, restricted claims, evidence needs, and disclaimer rule.
- `reference_asset_contract`: confirmed source image, segment source images, confirmed references, upload references, and token map.
- `model_capability_contract`: selected model, image-input limits, duration limits, audio/lip-sync support, and field names from config.

These contracts make the plan reviewable before paid generation and keep platform rules out of hardcoded prompt fragments.

## Speaker Mode

Default to `digital-human-spoken`:

- the visible model/digital-human is the seller/presenter;
- the presenter speaks directly to camera with natural lip sync;
- captions match the presenter's speech;
- use off-screen narration only if the user explicitly asks for voiceover, documentary narration, or faceless style.

In the proposal, always state one of:

- `digital-human-spoken`: visible presenter speaks;
- `voiceover`: off-screen narration;
- `silent-captions`: no speech, captions only.

## Product Motion Policy

Default ordinary products to `static-inanimate`.

Use `static-inanimate` for plushies, toys, figurines, accessories, decor, furniture, tools, packaging, cosmetics packaging, fashion products, home goods, electronics shells, books, and most physical products.

For `static-inanimate` products:

- the product must not blink, breathe, talk, walk, gesture, move limbs, change expression, turn its head, or act alive;
- the presenter, hands, camera, lighting, background, packaging, or turntable may move;
- the product may be held, placed, unboxed, shown close-up, gently rotated by hands, or placed on a turntable;
- keep product identity, face/print, color, material, logo, and proportions stable.

Use other policies only when justified:

- `demonstrated-function`: the product has a real mechanical/electronic function that should move, such as a fan, blender, lamp, scooter, robot vacuum, or toy with motorized action;
- `live-subject`: the subject is actually alive, such as a pet, plant, or person;
- `software-screen`: the product is an app, website, course, dashboard, or screen recording;
- `liquid-food`: fluid or food motion is natural, such as pouring, steaming, melting, or mixing.

## Marketplace Style

Default style should work for Taobao, Amazon, cross-border e-commerce, product detail pages, paid social ads, and live-shopping clips:

- show the product clearly within the first 2 seconds;
- make the selling point obvious without requiring story interpretation;
- include human scale, hands, usage, texture, packaging, or scene proof when useful;
- use clean commercial lighting and readable captions;
- avoid fantasy behavior, mascot animation, cinematic lore, vague mood shots, and over-stylized scenes that reduce product trust;
- make the CTA direct but not spammy.
