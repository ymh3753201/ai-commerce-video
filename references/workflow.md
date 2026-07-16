# Workflow

Use this workflow for product selling videos, e-commerce ads, product reveal videos, UGC-style short ads, and social platform ads.

## Codex-Native Analysis and Image Generation

Use Codex itself for the intelligence layer:

- analyze uploaded product photos, model/person images, reference images, product info, price, duration, platform, and business intent with Codex's built-in multimodal understanding;
- write the ad angle, selling points, storyboard, presenter spoken script, optional local-caption plan, sound direction, and clean-frame model prompts with Codex's built-in LLM reasoning;
- after the user approves the plan, generate the visual approval images with the Codex `imagegen` skill, such as final source/first-frame images, product hero images, synthetic model images, scene stills, and 6-grid or 9-grid storyboard sheets;
- do not introduce a separate LLM API, vision API, or image-generation API for these steps;
- use the external video API only after confirmation, only for rendering the same confirmed source/reference images into MP4 video.

## First Response Goal

The first user-facing proposal should be complete enough for a fast plan confirmation. Avoid turning the work into a long interview. When information is missing, make conservative assumptions and label them clearly. Do not generate new images before the user selects and confirms a creative variant plus image-generation plan.

Default video settings:

- duration: 15 seconds unless the user specifies otherwise;
- aspect ratio: follow `platform_contract`; default to 9:16 for Douyin, TikTok, Reels, Shorts, and Xiaohongshu, and use 16:9 for Amazon Sponsored Brands Video, Amazon Sponsored Products Video, and many product-page videos unless the user chooses another placement-specific format;
- resolution: 720p unless the user asks for 1080p or the model route requires another value;
- structure: one clip if duration fits the selected model, segmented clips if longer.
- speaker mode: visible model/digital-human spoken selling by default; use off-screen voiceover only if the user asks for narration/voiceover. Override this default when `platform_contract` forbids or discourages talking-head/audio-dependent ads, such as Amazon Sponsored Products Video.
- product motion policy: ordinary physical products are inanimate/passive by default; do not let the product blink, speak, walk, breathe, gesture, change expression, or act alive.
- creative variants: in the normal quick flow, Codex selects one professional AI recommendation and one concise alternative. Expand to a multi-version matrix only for an explicit A/B or batch-testing request. The user can reply `按 AI 推荐` without understanding model or editing terminology.
- default selected variant after explicit choice: `commerce_direct` unless the user selects `story_reversal`, `hybrid`, or accepts a different AI recommendation.
- reference strategy: use `single_source_frame` for continuous ads, `per_segment_source_frames` for single-image models with scene changes, and `multi_reference_storyboard` for Seedance-style multi-reference routes.
- commercial style: practical e-commerce ad is the default selected variant, suitable for Taobao, Amazon, cross-border product listings, paid social ads, and live-shopping short clips.
- contracts: every prepared project should write `creative_contract`, `platform_contract`, `scenario_contract`, `compliance_contract`, `reference_asset_contract`, and `model_capability_contract` into `generation-plan.json`.
- asset continuity: every image the user confirms as affecting the video must be saved locally and appear in the source image field or reference image field during dry-run. Chat-visible images alone do not count as video inputs.
- image-generation gate: the first proposal must include a concrete image-generation plan: what first-frame, scene, product-detail, model, storyboard, or campaign-preview images will be generated after approval, and which supplied images will be reused. Do not skip this plan just because the user supplied product and model images.

## Material Analysis

Inspect all provided inputs with Codex's native image and text understanding:

- product image(s), including different angles, detail shots, packaging, labels, back/side views, color variants, and lifestyle shots;
- digital-human/model/person image;
- product name, price, discount, audience, platform, style, brand voice;
- reference ad image/video/audio;
- requested duration, aspect ratio, resolution, model, and output folder.
- platform, placement, campaign goal, funnel stage, CTA type, offer, SKU/ASIN/product URL, shop destination, marketplace locale, and compliance risk if supplied.

If only a product image is provided, infer:

- product category, subcategory, and whether it is a living subject, inanimate product, product with a demonstrated mechanism, software screen, food/beverage, or fluid material;
- likely buyer, use scenario, gift/self-use scenario, and target platform;
- three selling points: functional value, visual/emotional value, and buying reason;
- pain point, desire, objection, and proof needed before purchase;
- one recommended ad angle;
- one e-commerce scene style;
- a 15-second storyboard.

If multiple product images are provided, classify each one before writing the plan:

- `hero_product`: best main visual for identity;
- `angle_detail`: side/back/top/detail angle that helps preserve shape or texture;
- `packaging_or_label`: packaging, logo, label, specification, or compliance detail;
- `usage_context`: product already shown in a real scene;
- `low_quality_or_duplicate`: image that should not drive video generation unless needed.

When designing the ad, explicitly decide:

- speaker mode: `digital-human-spoken` unless user requests `voiceover` or `silent-captions`;
- product motion policy: `static-inanimate` for plushies, toys, accessories, decor, tools, packaging, home goods, fashion, beauty packaging, and most physical products;
- what moves: presenter, hands, camera, platform, lighting, background, packaging, or a real demonstrated product mechanism;
- what must stay stable: product identity, shape, face/print, color, logos, texture, and proportions.

## Image Generation and Visual Approval Gate

Use a two-step gate:

1. First proposal: analyze the supplied materials, fully design one AI-recommended version, show one concise alternative when no style was specified, and ask the user to confirm the version plus image-generation plan.
2. After approval: use Codex `imagegen` / image2 to generate the planned images. Save them locally, show or attach them, and ask the user to approve or revise the images.

This is required even when the user provides both product image(s) and a digital-human/model image, because the user must approve the actual visual direction that will drive the video.

## First Proposal Flow

Use this sequence before any image generation or video API call:

1. Material analysis: inspect product, source assets, target platform, duration, living/non-living status, product motion rules, audience, pain point, selling points, and proof needs.
2. Recommended version: choose the strongest production-ready variant from `commerce_direct`, `story_reversal`, `ugc_review`, `comparison_test`, `lifestyle_seed`, `premium_brand`, `feature_demo`, `unboxing`, `live_shopping_teaser`, or `retargeting_offer`, and fully design it.
3. Concise alternative: show one meaningful alternative in short form. Only expand several variants when the user explicitly requests A/B testing, batch variants, or a creative matrix.
4. Platform/scenario/compliance contracts: summarize target platform, placement, safe-zone profile, commerce scenario, claim-risk level, CTA, and model-capability implication.
5. AI recommendation: explain which version fits the product/platform/assets better. If recommending `hybrid`, explain how the hook and direct selling parts will be balanced.
6. User choice: make `按 AI 推荐` the shortest normal reply; also allow a plan label or `两个融合`.
7. Image-generation plan confirmation: after the user chooses a version, confirm exact first-frame/reference/storyboard images, upload roles, token map, and final prompt.
8. Generate images only after that confirmation.
9. Ask for image approval or revision.
10. Execute `prepare_project.py -> validate_config.py -> validate_platform_plan.py -> preflight_project.py -> workflow_engine.py confirm/submit/resume` only after image approval.

Do not weaken the two confirmation gates. The first gate is creative-version plus image-plan approval; the second gate is generated-image approval before video generation.

Choose the approval image set from the selected model capability:

- Single-image route, such as `grok-video-1.5`: plan one final `video_source` / first-frame image that combines the approved product, presenter, scene, framing, and e-commerce style; generate it only after the user approves the plan. Separate product/model/storyboard images may be shown as supporting references, but they must be labeled preview-only unless they are part of the final source image.
- Single-image route with scene changes: do not upload a 6-grid or 9-grid storyboard sheet as the only source image. Instead plan `per_segment_source_frames`, generate one approved source/first-frame image per shot, generate each clip separately, then stitch.
- Multi-reference route, such as `grok-image-video`: plan to include the best user-supplied product angle(s) and model reference, then add generated scene, storyboard, product-detail, style, or campaign-preview references if `max_reference_images` leaves capacity. A product+model-only token map is incomplete for normal ad generation unless the user explicitly asks to skip extra visual references.
- Seedance-style route: use `multi_reference_storyboard` when the ad needs shot order control. Upload product, presenter, scene, and storyboard references within model limits, and state that the storyboard is rhythm/order guidance only, not a literal grid layout to reproduce.
- If no model image is provided, plan a clearly synthetic digital-human/model reference suited to the product and platform, then generate it after approval.
- If the selected route's upload capacity is already full, plan a storyboard/contact-sheet as a preview-only approval image and clearly state it will not be uploaded to the video model.

Typical generated assets:

- one clean product hero still;
- one synthetic digital model holding or using the product;
- one scene still showing the lifestyle context;
- one 6-grid or 9-grid storyboard sheet when useful.
- one final video source/first-frame image for source-image models when needed, containing the approved product, presenter, and scene.
- multiple segment source/first-frame images for single-image models when the ad has scene changes or story beats that should become separate clips.
- separate product/model/scene/storyboard reference images for multi-reference models, with prompt tokens assigned before confirmation.

After generating the images, save them as local files and show or attach them before video generation. If image generation fails or is unavailable, stop and explain the proposal is not ready for final video confirmation.

## First Proposal Checklist

Always include:

1. product understanding;
2. product category and product motion classification;
3. inferred missing information;
4. target user and platform;
5. whether the user already specified a creative variant;
6. `platform_contract` summary: platform, placement, aspect ratio, duration, subtitle, safe-zone, CTA, and audio/speaker rules;
7. `scenario_contract` summary: commerce scenario, story structure, image/reference needs, and risk control;
8. `compliance_contract` summary: claim-risk level and which claims need evidence;
9. one full AI-recommended variant with platform fit, selling points, storyboard, spoken script, local-caption choice, sound direction, and reference-image needs;
10. one concise alternative, normally labeled `方案 B`; keep the detailed `方案 A / commerce_direct` and `方案 B / story_reversal` matrix available for explicit A/B requests;
11. additional creative options only when batch testing or multiple campaign versions were requested;
12. AI recommendation and reason;
13. selected creative variant only after the user chooses;
14. speaker mode and presenter design;
15. planned image-generation outputs, with role, purpose, prompt summary, and whether each image will be uploaded or `preview_only`;
16. selected reference strategy and why;
17. planned source image, segment source images, and/or reference-image token map that will be uploaded to the video model after images are generated and approved;
18. model route and parameters;
19. split plan if duration exceeds one model clip or uses per-segment source frames;
20. confirmation statement asking the user to choose a plan label, request a hybrid, or accept the AI recommendation.
21. subtitle choice: disabled, or confirmed local postproduction. State clearly that the video Provider will never render subtitles.
22. legal request durations and the minimum paid request count, with automatic repair reserve fixed at zero.

## Post-Image Generation Checklist

After the user approves the plan and you generate images, show:

1. generated first-frame/source image or storyboard/contact-sheet previews;
2. local file path for every generated image;
3. role for every image: `video_source`, `model`, `scene`, `storyboard`, `product_detail`, `campaign_preview`, or `preview_only`;
4. exact token map and upload count for the selected video model;
5. whether the generated image set needs revision before video API submission.

## Guarded Video Generation Steps

### Provider Prompt Compiler

Keep the complete advertising strategy in the plan contracts. The exact Provider prompt is a compact render instruction in this order:

1. approved source-frame visual direction and product identity;
2. current segment goal and exact spoken dialogue;
3. selected commerce creative intent;
4. source/reference token map and continuity rule;
5. short fact-safety rule derived from the compliance contract;
6. speaker mode, product motion policy, and clean-frame rule.

`prepare_project.py` records the compiled result in each shot's `prompt_contract`, including `char_count`, `utf8_bytes`, `prompt_budget_chars`, `max_prompt_chars`, included components, and any planning-only components omitted to fit the safe budget. Detailed `platform_contract`, `scenario_contract`, and `compliance_contract` data stays in `generation-plan.json` for offline validation; do not copy those contracts verbatim into every Provider prompt. Do not truncate approved visual details or spoken dialogue. If the required components cannot fit, stop before confirmation and shorten the shot plan or split the segment.

1. Create a project folder:

   ```bash
   python3 ai-commerce-video/scripts/prepare_project.py --name <name> --product-image <path-or-url> --platform tiktok --placement in_feed --campaign-goal conversion --funnel-stage consideration --commerce-scenario ugc_review --creative-variant <variant> --cta-type shop_now --reference-strategy <strategy> --video-source-image <confirmed-final-source.png> --duration 25 --spoken-script '<approved complete script>' --subtitle-choice <disabled|enabled> --subtitle-request-source <default|user_plan_confirmation> --speaker-mode digital-human-spoken --product-motion-policy static-inanimate
   ```

   Use `--subtitle-request-source user_plan_confirmation` only when the user explicitly approved `--subtitle-choice enabled`; otherwise use the default disabled plan.

   For Grok 1.5 with two approved scene frames and a 30-second delivery:

   ```bash
   python3 ai-commerce-video/scripts/prepare_project.py --name <name> --product-image <path-or-url> --model-key grok_video_15 --reference-strategy per_segment_source_frames --segment-source-image shot_01=<hook.png> --segment-source-image shot_02=<proof-cta.png> --duration 30 --spoken-script '<two or more complete sentences>'
   ```

2. Validate configuration:

   ```bash
   python3 ai-commerce-video/scripts/validate_config.py --config ai-commerce-video/assets/templates/model-config.example.json
   ```

3. Validate platform and plan contracts:

   ```bash
   python3 ai-commerce-video/scripts/validate_platform_plan.py --plan <project>/generation-plan.json
   ```

   Inspect the report:

   - `platform_contract` matches aspect ratio, duration, subtitles, safe-zone, CTA, and speaker/audio rules;
   - `scenario_contract` and `compliance_contract` exist;
   - `model_capability_contract` supports the requested reference image count, audio/speaker plan, and segment strategy;
   - every shot uses the locked confirmed source image or approved segment source image.
   - every request duration is a legal selected-model slot;
   - every spoken segment ends at a stitch-safe sentence boundary;
   - every Provider prompt uses the prompt compiler, its stored `char_count` matches the exact payload, and it stays within `prompt_budget_chars` and `max_prompt_chars`;
   - `subtitle_included_in_payload=false` and enabled subtitles are local postproduction only;
   - approved paid cap equals the base shot count and repair reserve is zero.

4. Freeze the no-cost preflight contract. This command does not require an API key and does not call the Provider:

   ```bash
   python3 ai-commerce-video/scripts/preflight_project.py --plan <project>/generation-plan.json --config ai-commerce-video/assets/templates/model-config.example.json
   ```

   Inspect the request JSON:

   Inspect `preflight-report.json`, `production-contract.json`, `model-snapshot.json`, and each dry-run request. Confirm asset hashes, duration digest, exact prompt length, payload fields, clean-frame prompt policy, and `expected_paid_requests`.

5. After final user approval, bind that exact frozen contract:

   ```bash
   python3 ai-commerce-video/scripts/workflow_engine.py --project-dir <project> confirm --approved-by user
   ```

6. Submit each base shot at most once:

   ```bash
   python3 ai-commerce-video/scripts/workflow_engine.py --project-dir <project> submit --config ai-commerce-video/assets/templates/model-config.example.json
   ```

   If a network response is unclear, stop. Do not rerun `submit`. The persistent ledger records the attempt before the HTTP request.

7. Poll or resume existing request IDs:

   ```bash
   python3 ai-commerce-video/scripts/workflow_engine.py --project-dir <project> resume --config ai-commerce-video/assets/templates/model-config.example.json
   ```

8. Stitch if there are multiple clips:

   ```bash
   python3 ai-commerce-video/scripts/stitch_clips.py --project-dir <project> --target-resolution 720x1280 --target-fps 30 --require-audio
   ```

9. Review the clean output technically, then complete multimodal business review using `post-generation-review.md`:

   ```bash
   python3 ai-commerce-video/scripts/review_render.py --project-dir <project> --video <project>/final.mp4 --clean
   ```

10. When the confirmed subtitle plan is enabled, generate and burn subtitles locally after clean review. Never send caption instructions back to the Provider:

   ```bash
   python3 ai-commerce-video/scripts/generate_subtitles.py --plan <project>/generation-plan.json --video <project>/final.mp4 --output <project>/subtitles/final.srt
   python3 ai-commerce-video/scripts/burn_subtitles.py --plan <project>/generation-plan.json --video <project>/final.mp4 --srt <project>/subtitles/final.srt --output <project>/final.captioned.mp4
   ```

11. Finalize only after the required clean and optional caption reviews pass:

   ```bash
   python3 ai-commerce-video/scripts/finalize_project.py --project-dir <project>
   ```

## Long Video Consistency

For duration above the selected model limit:

- create one `visual_bible` section in the manifest;
- reuse the same product image and generated model/scene references;
- keep the same aspect ratio, resolution, palette, camera style, and reserved safe-zone layout;
- write every segment prompt as part of the same campaign;
- choose legal model duration slots with the minimum paid request count;
- give every segment a unique complete-sentence script and an intentional planned cut;
- do not silently add last-frame relay, extra segment sources, or repair requests because each can change cost or approved assets;
- stitch only after every segment has been downloaded and ffprobe-validated;
- normalize video consistently and use PCM intermediate speech audio, no fades/crossfades, then one final AAC encode.

## Completion Standard

Do not report completion only because a request was submitted. Completion requires:

- request payload saved;
- poll result saved;
- MP4 downloaded locally and ffprobe-validated;
- multi-clip final video normalized, stitched, and ffprobe-validated if needed;
- stitch report saved when stitching is used;
- clean multimodal business review passed;
- caption review passed when subtitles are enabled;
- paid submission count did not exceed the confirmed cap;
- `delivery-manifest.json` exists with `status=pass`;
- final file path reported;
- obvious failures or model limitations explained.
