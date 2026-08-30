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

Choose the mode once in Stage 1 from the user's task, image evidence, platform, and commercial purpose. That approved choice is authoritative for every later prompt and review:

- use a visible model/digital-human only when talent strengthens desire, trust, scale, use proof, or emotion;
- when a presenter speaks, require natural-looking delivery and plausible mouth movement, but do not promise frame-exact lip sync;
- use off-screen narration when the product or visual proof should remain the hero;
- use no human speech when visual action, ambience, effects, or music can carry the ad more effectively;
- keep Provider frames free of captions; approved subtitles are created locally from the finished speech.

In the proposal, always state one of:

- `digital-human-spoken`: visible presenter speaks;
- `voiceover`: off-screen narration;
- `no-speech`: no human voice, while approved SFX, ambience, and music may remain;
- `silent-captions`: fully silent placement, with captions only when separately approved.

Also show the plain-language `speech_presentation`: `on_camera_presenter`, `off_screen_voiceover`, or `none`. Treat Chinese requests such as “人物口播”, “主播口播”, “人物讲话”, and “对镜讲解” as `digital-human-spoken` when they are the approved Stage 1 direction. A visible presenter does not decide the voice mode: the presenter may speak, demonstrate silently under voiceover, or perform silently in a no-speech ad. Never rewrite one approved relationship into another after reference generation. Save the director/user decision source and block conflicting mode, presentation, or script fields before Stage 2.

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
