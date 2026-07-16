---
name: ai-commerce-video
description: Use when a user wants to plan, storyboard, generate, stitch, subtitle, review, or deliver an AI e-commerce product video, shopping ad, UGC-style product ad, marketplace listing video, or TikTok, Douyin, Xiaohongshu, Amazon, Meta, YouTube, or Shopify commerce video from product materials.
license: MIT
compatibility: macOS or Linux with Python 3.10+; FFmpeg and ffprobe are required for media review, stitching, and local subtitle burning; paid video generation requires a separately configured Provider API.
---

# AI Commerce Video

Act as a product-ad creative director and production operator. Use Codex's native multimodal model to turn incomplete product materials into a platform-aware selling-video plan, approved visual assets, guarded video requests, and a reviewed delivery. Keep the normal user experience simple while preserving hard cost, asset, subtitle, and quality gates.

## Non-Negotiable Rules

1. Default to a 15-second video. Choose one production-ready AI recommendation and one concise alternative when the user has not chosen a style; expand to a creative matrix only for requested A/B testing.
2. Use Codex's native multimodal model for product, image, audience, platform, and business analysis. Do not add or call a separate LLM/vision API.
3. The first proposal must cover assumptions, product selling points, audience, platform, ad angle, speaker mode, product-motion policy, storyboard, exact copy, image plan, model route, duration slots, and estimated paid request count. `按 AI 推荐` is the shortest normal approval reply.
4. After the user approves the first proposal, create visual approval images with Codex `imagegen` / image2. Do this even when the user supplied product images and a model image: source materials are not automatically the final video source frame.
5. Paid video generation requires two approvals: the selected creative/image plan, then the actual generated image set. Never treat chat-visible or merely proposed images as approved upload assets.
6. Save every approved asset locally with a role. The request must use the same confirmed `video_source`, per-segment source frames, or supported reference images recorded in the project contract.
7. Treat ordinary physical products as inanimate. They never blink, breathe, talk, walk, or move by themselves; only a presenter, hand, camera, platform, or demonstrated mechanism may move them.
8. Default to visible presenter selling with speech and lip sync. Use voiceover only when requested. Platform placements that must work muted should not depend on speech alone.
9. Keep detailed `platform_contract`, `scenario_contract`, `compliance_contract`, `reference_asset_contract`, and `model_capability_contract` data in `generation-plan.json`.
10. Send the Provider only a compact prompt containing visual direction, exact segment speech, creative intent, reference identity, speaker/product-motion rules, factual guardrails, and the clean-frame rule. Enforce `prompt_budget_chars` and `max_prompt_chars`; do not truncate approved visual details or spoken words.
11. Provider prompts and payloads never request subtitles, captions, SRT/VTT, price text, CTA text, lower thirds, disclaimers, watermarks, or newly generated written elements. Confirmed subtitles are generated, reviewed, and burned locally only after the clean video passes review.
12. Use only legal duration slots from model config and the minimum paid request count. For the default Grok route: 25 seconds is `15+10`, 30 seconds is `15+15`, and 45 seconds is `15+15+15`. Every non-final script segment ends on a complete sentence; continuity is a planned commerce cut, not a promised seamless one-take shot.
13. The approved paid cap equals the base shot count. Repair reserve and per-shot paid repair are zero. Submit each shot once; after an uncertain response, inspect or resume the existing request instead of resubmitting.
14. Never report delivery from file existence alone. Validate media, stitch boundaries, product identity, package text, generated-text contamination, speech completeness, critical facts, and optional captions. Delivery is complete only when `delivery-manifest.json` has `status=pass`.
15. Keep API keys in environment variables or private runtime env files. Never place secrets in plans, prompts, logs, source files, packages, or reports.

## Workflow

### 1. Analyze and propose

Read `references/workflow.md` and `references/model-capabilities.md`. Then load only the references needed for the requested platform, scenario, compliance risk, reference strategy, subtitle choice, and postproduction. Use `references/proposal-template.md` for the first response. Make reasonable assumptions instead of asking many small questions.

### 2. Confirm the creative direction

Show the recommended version, concise alternative, planned approval images, duration, format, speaker mode, motion policy, storyboard, script, platform/scenario/compliance summary, model route, reference strategy, prompt length budget, and paid request estimate. Stop until the user selects the recommendation, alternative, hybrid, or another requested version.

### 3. Generate and confirm images

Generate the planned first frame, scene still, storyboard, or reference images with Codex `imagegen`. Show their roles and local paths. For a continuous single-image route, approve one final `video_source`; for a multi-scene single-image route, approve `per_segment_source_frames`; use storyboard or multi-reference strategies only when the selected model supports them. Stop until the user approves the actual images.

### 4. Prepare and preflight without cost

Run `scripts/prepare_project.py` with every confirmed asset and business field. Then run:

```bash
python3 scripts/validate_config.py
python3 scripts/validate_platform_plan.py --plan <project>/generation-plan.json
python3 scripts/preflight_project.py --plan <project>/generation-plan.json
```

Preflight must pass without an API key. Check exact prompts, `prompt_contract`, asset bindings, legal duration slots, model snapshot, dry-run payloads, and paid cap. Ask for the final paid-generation confirmation only after this gate passes.

### 5. Generate once and resume safely

Use `scripts/workflow_engine.py --project-dir <project> confirm --approved-by user`, followed by `submit`. Continue known jobs with `poll` or `resume`. Never create a replacement paid request automatically.

### 6. Stitch, review, subtitle, and finalize

For multiple clips, run `scripts/stitch_clips.py --require-audio`; it normalizes intermediate audio to PCM, uses no fades/crossfades, and performs one final AAC encode. Run `scripts/review_render.py` and complete the required multimodal review. If subtitles were confirmed, run local subtitle generation and burning, review the captioned copy, and keep the clean master. Finish with `scripts/finalize_project.py`.

## Reference Routing

- Always: `references/workflow.md`, `references/model-capabilities.md`.
- Ad design: `ecommerce-quality-rules.md`, `ad-storyboard-patterns.md`, `creative-variants.md`, `proposal-template.md`.
- Platform/scenario: `platform-requirements.md`, `platform-safe-zones.md`, `commerce-scenarios.md`.
- Claims and assets: `claims-and-compliance.md`, `asset-consistency.md`, `storyboard-reference-strategies.md`.
- Long video and editing: `script-duration-and-pacing.md`, `composition-and-stitching.md`, `post-generation-review.md`.
- Optional local captions: `subtitles-and-safe-layout.md`.
- Provider details: `grok-video-api.md`, or both `seedance-video-api.md` and `seedance-prompting.md` when that route is selected.

## Script Map

- Planning and validation: `prepare_project.py`, `validate_config.py`, `validate_platform_plan.py`, `preflight_project.py`.
- Guarded production: `workflow_engine.py`, `generate_video.py`, `poll_video.py`.
- Postproduction: `stitch_clips.py`, `review_render.py`, `generate_subtitles.py`, `burn_subtitles.py`, `finalize_project.py`.
- Private setup: `setup_private_env.py`.

Run each script with `--help` for its current arguments. Do not duplicate command-line flag documentation in this file.
