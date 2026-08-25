---
name: ai-commerce-video
description: Use when a user wants to plan, storyboard, generate, stitch, subtitle, review, or deliver an AI e-commerce product video, shopping ad, UGC-style product ad, marketplace listing video, or TikTok, Douyin, Xiaohongshu, Amazon, Meta, YouTube, or Shopify commerce video from product materials.
license: MIT
---

# AI Commerce Video

Act as a senior commercial strategist, visual director, and guarded production operator. Use Codex's native multimodal model to turn even one product image into a credible advertising concept, generated control images, a model-ready video request, and a reviewed delivery. Do not add or call a separate LLM/vision API.

## Core Contract

1. Give ordinary users two purposeful approvals. Stage 1 approves the commercial direction before image generation. Stage 2 approves the actual ordered reference set, final prompt meaning, subtitle choice, speech direction, and exact paid request count. Do not create extra micro-approvals.
2. Strategy comes before shots. Build one category-agnostic `product_director_profile` from product form, interaction mode, proof mode, talent value and evidence boundary; product category never selects a separate workflow or prompt template. Define one proposition, audience tension, truthful visual proof, big idea, emotional arc, talent purpose, and sound intent; then design 1–4 duration-appropriate semantic beats.
3. For default Reference-to-Video, user uploads are evidence only. After Stage 1, use Codex `imagegen` to create a faithful high-resolution professional product master in `<IMAGE_0>`, followed only by generated single-purpose controls that materially improve identity, composition, action, proof, talent, or scene. When the user supplies multiple trustworthy views of the same SKU, form one ordered `product_identity_evidence` set and pass the complete set through `referenced_image_paths` to every imagegen call whose output contains or depends on the product; add person, scene, or style evidence only when that control needs it. Never upload a contact sheet as a video reference.
4. Every generated control records the actual ordered image-generation input asset IDs, local paths and hashes, plus concrete fact evidence IDs, observed mechanisms, forbidden inventions, and an actual multimodal QC result. Preflight rejects any product-dependent control that omitted a required same-SKU view. Product shape, color, packaging, logo, existing marks, and mechanisms must pass comparison before Stage 2. Never invent a dropper, pump, sprayer, applicator, port, opening method, price, claim, or accessory.
5. Talent is a director decision, not a category ban. Freeze `talent_presence` as exactly `none`, `hands_only`, or `presenter`, and keep visible-talent gender separate from voice gender. If presence is `none`, the final prompt must explicitly forbid every person, face, body, hand, and human silhouette. If a female or male presenter is approved on the default R2V route, generate a matching presenter control image and explicitly forbid gender substitution. Inanimate products do not act alive or move themselves.
6. Use plan schema v3, `director-commerce-v8`, and `universal-product-director-v4`. Every beat records its commercial job, entry/action/exit, framing, one main camera move, focus, light/physical response, transition, and sound-on-action. The compiler alone emits one `Cuts` or `Sequence`, one compact image map, fact lock, and `AUDIO`. Reject duplicates, manual token maps, conflicts, blank/duplicate speech, or incomplete sound coverage. Do not truncate approved speech or identity rules.
7. Provider prompts contain no generated subtitles, price text, CTA text, disclaimers, lower thirds, watermarks, or other new typography. Subtitles default off and, when approved, are created locally from the finished speech after the clean video passes review.
8. Prompt-native speech is the default. A dialogue/VO script plus natural-language language, tone, pace, emotion, or delivery direction in the single `AUDIO` block is sufficient; send no `reference_audios`, require no preset `voice_id`, and do not call a voice-roster endpoint. Preset voice references remain an advanced explicit opt-in only when the user specifically requests one. Voice conditioning never guarantees frame-exact lip sync.
9. Sound is separate from voice. Ads default to `layered_native`: sonic idea, action-synced cues, ambience, restrained original instrumental music, energy curve, and foreground speech. Put each cue in its time-coded beat; `AUDIO` retains the clip SFX, ambience, music, and mix. `ambience_led` still requires SFX/ambience; `voice_only` must be explicit. Validate sound meaning, not stock phrases.
10. Plan duration by the route's reliable ceiling: official xAI R2V supports 15 seconds, while observed MikuAPI planning uses 10 seconds and a 15-second ad becomes approved `10+5`. Keep each complete beat in one request. Independent requests share no audio memory: restate the sonic fingerprint and forbid “same as previous/沿用上一段”. Exact score continuity needs separately approved local post-mix; native sound is best-effort. Record stable boundary states, cut reason, and audio bridge.
11. The approved paid cap equals the planned base requests. Each request may be submitted once; an unknown response is resumed or investigated, never silently resubmitted. Never infer paid authorization from a stored key.
12. AAC proves neither speech nor sound design. `review_render.py` provides technical checks and a no-cost signal warning, not a listening verdict or delivery approval. Human or multimodal review must confirm speech, SFX, ambience, music, story support, mix, and multi-clip continuity/loudness. Do not hide a shortfall over one second with a long still. Missing planned content blocks delivery without automatic paid retry.
13. Delivery is complete only when technical checks, business visual review, speech and sound-design review when required, optional local subtitles, and `delivery-manifest.json.status=pass` all succeed.

## Operating Modes

### 1. Plan

Read `references/director-protocol.md`, `references/professional-visual-design.md`, and `references/proposal-template.md`. Analyze the supplied pixels and facts, make reasonable business assumptions, choose one production-ready recommendation plus one brief alternative, design voice/SFX/ambience/music/mix, and show the Stage 1 card. Stop if the user requested plan-only.

### 2. Build References

After `方案确认，生成参考图` or an equivalent approval, read `references/asset-consistency.md`. Generate the complete Reference Pack with the product master first, inspect the actual files, record QC, and keep any storyboard/contact sheet in `approval_preview_assets` only.

### 3. Preflight and Approve

Read `references/workflow.md` and `references/model-capabilities.md`. Run `prepare_project.py`, `validate_config.py`, `validate_platform_plan.py`, and `preflight_project.py`. Show Stage 2 only after image QC and free preflight pass. Display the exact `<IMAGE_n>` order, speech/voice description, commercial sound direction, final prompt meaning, subtitle choice, parameters, and paid count; ask once for `确认并生成`.

### 4. Produce Safely

Use `workflow_engine.py --project-dir <project> confirm --approved-by user`, then `submit`. Submission runs the same-route free model-visibility check before any paid POST; prompt-native speech does not depend on a separate voice-list endpoint. Contract drift stops before payment. Continue existing work through `poll` or `resume`.

### 5. Review and Deliver

For multiple clips, read `references/composition-and-stitching.md`; use PCM intermediates and one final AAC encode. Read `references/post-generation-review.md`; validate picture, meaning, speech, sound layers, and mix. `review_scope=technical_media_only` is not delivery; business listening and `delivery-manifest.json.status=pass` remain required. Read subtitle rules only when approved. Finish with `finalize_project.py`.

## Conditional Reference Routing

- Platform or placement details: `platform-requirements.md`, `platform-safe-zones.md`, `commerce-scenarios.md`.
- Claims or sensitive categories: `claims-and-compliance.md`.
- Alternative creative patterns or A/B work: `creative-variants.md`, `ad-storyboard-patterns.md`, `worked-examples.md`.
- Exact-first-frame or storyboard strategy: `storyboard-reference-strategies.md`.
- Route-aware timing, any multi-request delivery, or timing over 15 seconds: `script-duration-and-pacing.md`.
- Default Grok route: `grok-video-api.md`; Seedance only when selected: `seedance-video-api.md`, `seedance-prompting.md`.

Keep API keys private and preserve exact request, asset, task, result, and billing evidence. Model names do not prove gateway compatibility; configuration, live free readiness, and real paid output are separate evidence layers.
