---
name: ai-commerce-video
description: Use when a user wants to plan, storyboard, generate, stitch, subtitle, review, or deliver an AI e-commerce product video, shopping ad, UGC-style product ad, marketplace listing video, or TikTok, Douyin, Xiaohongshu, Amazon, Meta, YouTube, or Shopify commerce video from product materials.
license: MIT
---

# AI Commerce Video

Act as a commercial strategist, visual director, and guarded operator. Use Codex's native multimodal model. Do not add or call a separate LLM/vision API.

## Core Contract

1. Give ordinary users two purposeful approvals. Stage 1 approves the commercial direction before image generation. Stage 2 approves the actual ordered reference set, final prompt meaning, subtitle choice, speech direction, and exact paid request count. Do not create extra micro-approvals.
2. Strategy comes before shots. Use one category-agnostic `product_director_profile`; product category never selects another workflow. Define the proposition, audience tension, truthful proof, big idea, talent purpose, sound intent, and 1–4 semantic beats.
3. For default Reference-to-Video, uploads are evidence only. After Stage 1, use `imagegen` to create a faithful high-resolution professional product master in `<IMAGE_0>` and only needed generated single-purpose controls. Put trustworthy same-SKU views in one ordered `product_identity_evidence` set and pass all through `referenced_image_paths` to every product-dependent imagegen call; add role-specific evidence only when needed. Never upload a contact sheet.
4. Save every generated control with its role and prompt. Stage 2 full-size images are the visual gate; missing per-image QC/evidence records are warnings. Preflight still blocks raw/non-generative user images, missing generated files or product master, invalid reference order/count, and invented facts.
5. Freeze `talent_presence=none|hands_only|presenter` separately from the Stage 1 voice contract. After reading the user's request and images, the director chooses exactly one: `digital-human-spoken` (the visible presenter speaks), `voiceover` (off-screen narration), or `no-speech` (no human voice; ambience/SFX/music may remain). `silent-captions` is reserved for a fully silent placement. Show “说话主体：画面人物/画外旁白/无语音” in both cards. Once Stage 1 is approved, later preparation must preserve that choice; a visible presenter never causes voiceover to be rewritten as on-camera speech. Product-only prompts forbid humans; approved female/male presenters need a matching generated control and no gender substitution. Inanimate products never act alive or self-move.
6. Use plan schema v3, `director-commerce-v10`, and `universal-product-director-v6`. Each beat has one commercial job and main camera move. The compiler emits one `Cuts` or `Sequence`, image map, fact lock, and `AUDIO`; on-camera speech compiles to `Dialogue=` plus visible speaking/mouth direction, voiceover to `VO=` plus off-screen direction, and no-speech to `Speech=none; Voice=none` while preserving the approved non-speech sound layers. Mode, presentation, script and prompt contradictions are errors; incomplete sound cues remain warnings. Do not truncate approved speech or identity rules.
7. Provider prompts contain no generated subtitles, price text, CTA text, disclaimers, lower thirds, watermarks, or other new typography. Subtitles default off and, when approved, are created locally from the finished speech after the clean video passes review.
8. When Stage 1 selects speech, prompt-native speech is the default. A dialogue/VO script plus natural-language language, tone, pace, emotion, or delivery direction in the single `AUDIO` block is sufficient; send no `reference_audios`, require no preset `voice_id`, and do not call a voice-roster endpoint. Preset voice references remain an advanced explicit opt-in only when the user specifically requests one and the approved plan contains spoken copy. Voice conditioning never guarantees frame-exact lip sync.
9. Sound is separate from voice. Ads default to `layered_native`: sonic idea, action-synced cues, ambience, restrained original instrumental music, energy curve, and the approved human-voice state. A `no-speech` plan may still use all non-speech layers; it is not converted to a silent video. Put each cue in its time-coded beat; `AUDIO` retains the clip SFX, ambience, music, and mix. `ambience_led` still requires SFX/ambience; `voice_only` is valid only for a spoken plan; `silent` is reserved for a fully silent placement. Validate sound meaning, not stock phrases.
10. Plan duration by the route's reliable ceiling: official xAI R2V supports 15 seconds, while observed MikuAPI planning uses 10 seconds and a 15-second ad becomes approved `10+5`. Keep each complete beat in one request. Independent requests share no audio memory: restate the sonic fingerprint and forbid “same as previous/沿用上一段”. Exact score continuity needs separately approved local post-mix; native sound is best-effort. Record stable boundary states, cut reason, and audio bridge.
11. The approved paid cap equals the planned base requests. Each request may be submitted once; an unknown response is resumed or investigated, never silently resubmitted. Never infer paid authorization from a stored key.
12. `review_render.py` proves decode, duration and stitching. New non-silent plans also need one narrow `voice-review.json`: spoken plans verify audible, intelligible, meaning-preserving speech; on-camera plans additionally verify the presenter speaks with visible mouth movement; `no-speech` plans verify that no unplanned human speech appears. AAC/music is not speech proof. This internal check adds no approval or paid retry; other creative review stays optional. Never hide a shortfall over one second with a long still.
13. New projects complete after job/contract checks, technical review, the narrow Stage 1 voice-contract review, selected subtitles, and `delivery-manifest.json.status=pass`. Legacy plans remain strict. Full business review is optional and adds no hidden approval stage.

## Operating Modes

### 1. Plan

Read `references/director-protocol.md`, `references/professional-visual-design.md`, `references/ecommerce-quality-rules.md`, `references/ad-storyboard-patterns.md`, and `references/proposal-template.md`. Analyze the evidence, choose one recommendation plus one brief alternative, decide on-camera speech vs voiceover vs no human voice, design the remaining sound layers, and show Stage 1. Stop for plan-only requests.

### 2. Build References

After `方案确认，生成参考图` or an equivalent approval, read `references/asset-consistency.md`. Generate the complete Reference Pack with the product master first, save and inspect the actual files, and keep any storyboard/contact sheet in `approval_preview_assets` only. AI consistency notes are useful but optional; Stage 2 user review is the visual gate.

### 3. Preflight and Approve

Read `references/workflow.md` and `references/model-capabilities.md`. Prepare the project and run the single unified `preflight_project.py` readiness check. `validate_config.py` and `validate_platform_plan.py` remain developer diagnostics, not extra user-visible gates. Show Stage 2 after every actual generated upload image is saved and hard preflight passes; display advisory findings without blocking. Display the exact `<IMAGE_n>` order, the frozen Stage 1 speaking subject/voice absence and non-speech sound direction, final prompt meaning, subtitle choice, parameters, and paid count; ask once for `确认并生成`.

### 4. Produce Safely

Use `workflow_engine.py --project-dir <project> confirm --approved-by user`, then `submit`. Submission runs the same-route free model-visibility check before any paid POST; prompt-native speech does not depend on a separate voice-list endpoint. Contract drift stops before payment. Continue existing work through `poll` or `resume`.

### 5. Review and Deliver

For multiple clips, read `references/composition-and-stitching.md`; use PCM intermediates and one final AAC encode. Run `post-generation-review.md`; record the narrow Stage 1 voice-contract result with `review_voice_contract.py`, then finalize. This is not a third user approval. Full creative review stays optional; read subtitle rules only when selected.

## Conditional Reference Routing

- Platform or placement details: `platform-requirements.md`, `platform-safe-zones.md`, `commerce-scenarios.md`.
- Claims or sensitive categories: `claims-and-compliance.md`.
- Alternative creative patterns or A/B work: `creative-variants.md`, `ad-storyboard-patterns.md`, `worked-examples.md`.
- Exact-first-frame or storyboard strategy: `storyboard-reference-strategies.md`.
- Route-aware timing, any multi-request delivery, or timing over 15 seconds: `script-duration-and-pacing.md`.
- Default Grok route: `grok-video-api.md`; Seedance only when selected: `seedance-video-api.md`, `seedance-prompting.md`.

Keep API keys private and preserve exact request, asset, task, result, and billing evidence. Model names do not prove gateway compatibility; configuration, live free readiness, and real paid output are separate evidence layers.
