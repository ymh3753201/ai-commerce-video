# Workflow

Use this workflow for product selling videos, e-commerce ads, product reveal videos, UGC-style short ads, and social platform ads.

## Codex-Native Analysis and Image Generation

Use Codex itself for the intelligence layer:

Use Codex `imagegen` / image2 as the approved local reference-image preparation path.

- analyze uploaded product photos, model/person images, reference images, product info, price, duration, platform, and business intent with Codex's built-in multimodal understanding;
- write the ad angle, selling points, storyboard, Stage 1 voice contract (on-camera speech, off-screen voiceover, or no human voice), any required spoken copy, optional local-caption plan, sound direction, and clean-frame model prompts with Codex's built-in LLM reasoning;
- before generating references, design the commercial idea, route-aware complete-beat storyboard, transitions and edit-safe boundaries, complete Reference Pack, image prompts, sound timeline, and final video-prompt blueprint; after Stage 1 approval, use Codex `imagegen` / image2 to regenerate every Provider-facing image from the supplied evidence, including the professional product master. Pass all trustworthy same-SKU product views together in `referenced_image_paths` whenever the output shows or depends on the product, and append person/scene/style evidence only when that control needs it;
- do not introduce a separate LLM API, vision API, or image-generation API for these steps;
- use the external video API only after confirmation, only for rendering the same confirmed source/reference images into MP4 video.

## Default Professional Two-Stage Path

Avoid a long interview or many micro-approvals. Make conservative assumptions and label them. Use exactly two meaningful gates for ordinary professional multi-reference work:

1. Stage 1 creative approval: show the product understanding, one recommended ad direction, 15-second storyboard/script, motivated cuts, explicit speaking subject or no-human-voice decision, remaining sound layers, reference portfolio, every planned image prompt, and the final video-prompt blueprint. No reference generation or video API call occurs before this approval.
2. Stage 2 asset and paid approval: after preparing every actual reference and completing no-cost preflight, show the ordered `<IMAGE_n>` set, the same frozen voice/sound meaning, final prompt meaning, subtitle choice, and exact paid request count. `确认并生成` approves only this frozen set.

Do not split Stage 1 into separate approvals for concept, script, storyboard and prompts. Do not split Stage 2 into separate approvals for images, preflight and payment.

Default video settings:

- delivery duration: 15 seconds unless the user specifies otherwise; request duration is then split by the selected route's verified reliable planning ceiling (current MikuAPI R2V: 10 seconds, official xAI R2V: 15 seconds);
- aspect ratio: follow `platform_contract`; default to 9:16 for Douyin, TikTok, Reels, Shorts, and Xiaohongshu, and use 16:9 for Amazon Sponsored Brands Video, Amazon Sponsored Products Video, and many product-page videos unless the user chooses another placement-specific format;
- resolution: 720p unless the user asks for 1080p or the model route requires another value;
- structure: split by the selected route's reliable planning ceiling. Current MikuAPI R2V uses at most 10 seconds per planned request (`15s = 10+5`); official xAI R2V documents one request up to 15 seconds. Exact-first-frame I2V remains an explicit higher-cost route.
- speaker/talent mode: freeze `talent_presence=none|hands_only|presenter` separately from `speaker_mode=digital-human-spoken|voiceover|no-speech`. `silent-captions` is reserved for a fully silent placement. The director chooses from the user's task, images, platform and creative logic; a visible presenter may speak, demonstrate silently under voiceover, or perform silently with only environment/music. Optional visible-presenter gender and voice gender remain separate facts. Product category is context, not a hard prohibition. `none` explicitly forbids all visible humans; an explicit female/male presenter requires a matching generated control on the default R2V route. Never invent a mechanism, prop, efficacy, or self-moving inanimate product.
- product motion policy: ordinary physical products are inanimate/passive by default; do not let the product blink, speak, walk, breathe, gesture, change expression, or act alive.
- creative variants: in the normal fast path, Codex selects one professional AI recommendation automatically and may show one concise alternative as an optional revision direction. Expand to a multi-version matrix only for an explicit A/B or batch-testing request. In review-first mode, the user can reply `按 AI 推荐` without understanding model or editing terminology.
- default selected variant after explicit choice: `commerce_direct` unless the user selects `story_reversal`, `hybrid`, or accepts a different AI recommendation.
- reference strategy: the default MikuAPI relay route uses `multi_reference_commercial` with the xAI-compatible `grok-imagine-video-1.5` contract. Prefer product master + Hook keyframe + Proof/Payoff keyframe; add separate talent, scene, detail, or action controls only when needed. Storyboard/contact sheets are review-only. When exact shot-start control is required, use the separately approved `per_segment_source_frames` Image-to-Video route.
- commercial style: practical e-commerce ad is the default selected variant, suitable for Taobao, Amazon, cross-border product listings, paid social ads, and live-shopping short clips.
- contracts: every prepared project should write `visual_design_contract`, `creative_contract`, `platform_contract`, `scenario_contract`, `compliance_contract`, `reference_asset_contract`, and `model_capability_contract` into `generation-plan.json`.
- asset continuity: keep raw evidence, the complete generated Reference Pack and review-only previews separate. The generated professional product master is first in the reference field; no user-uploaded image, cropped derivative or chat-visible preview may appear there.
- image preparation: record the ordered imagegen input asset IDs, paths and hashes, plus the prompt and role of every generated Provider control and any review-only storyboard preview. Keep this detail internal unless it helps the final decision or the user requested a plan review.

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

Save every trustworthy same-SKU item in one ordered `product_identity_evidence` set. A real-use or model photo can be dual-role when it also proves the exact product. Do not place unrelated scenes, styles, people, duplicate files, or another SKU in that set. Ordinary local preparation accepts repeated `--product-image` arguments; when a non-product role is also same-SKU evidence, list its saved asset ID in `visual_design.product_identity_evidence_asset_ids`.

When designing the ad, explicitly decide:

- speaker mode and speaking subject: use director judgment from the task and image evidence, then explicitly choose `digital-human-spoken`, `voiceover`, or `no-speech` in Stage 1. “人物口播/主播口播/人物讲话/对镜讲解” means the visible presenter speaks when that is the selected plan; `voiceover` keeps any visible presenter silent; `no-speech` forbids human speech while allowing approved SFX, ambience and music. Record the decision source. After approval, never infer a different mode from presenter presence, generated references or the existence of copy;
- product motion policy: `static-inanimate` for plushies, toys, accessories, decor, tools, packaging, home goods, fashion, beauty packaging, and most physical products;
- what moves: presenter, hands, camera, platform, lighting, background, packaging, or a real demonstrated product mechanism;
- what must stay stable: product identity, shape, face/print, color, logos, texture, and proportions.

## Creative Plan, Image Preparation, and Final Approval

1. Analyze the supplied materials and choose one production-ready AI recommendation.
2. Show the Stage 1 visual-plan card and wait for creative approval.
3. Use Codex `imagegen` / image2 to regenerate the complete Reference Pack. For every product-dependent output, pass the complete ordered `product_identity_evidence` set in one multi-image call, then append only the role-specific person/scene/style evidence it needs. Generate the faithful professional product master first, then the later single-purpose controls; never crop or reuse the uploaded original as a Provider reference.
4. Save and inspect the actual ordered set, prepare the project, and run no-cost preflight.
5. Show the Stage 2 card and ask once for `确认并生成`.

Neither approval permits unseen assets. Stage 1 is not paid authorization; Stage 2 is bound to the exact files, prompt meaning, subtitle choice, and paid count shown.

## Fast-Path Flow

Use this sequence for an ordinary request:

1. Material analysis: inspect product, source assets, target platform, duration, living/non-living status, product motion rules, audience, pain point, selling points, and proof needs.
2. Recommended version: choose the strongest production-ready variant from `commerce_direct`, `story_reversal`, `ugc_review`, `comparison_test`, `lifestyle_seed`, `premium_brand`, `feature_demo`, `unboxing`, `live_shopping_teaser`, or `retargeting_offer`, and fully design it without asking the user to choose among jargon-heavy options.
3. Concise alternative: retain one meaningful alternative as an optional revision direction. Only expand several variants when the user explicitly requests A/B testing, batch variants, or a creative matrix.
4. Internal contracts: record platform, scene, safe-zone, compliance notes, CTA, and model capability in `generation-plan.json`; do not expand them in the ordinary user-facing proposal unless requested.
5. AI recommendation: apply the best version by default and explain the reason briefly. If recommending `hybrid`, explain how the hook and direct selling parts are balanced.
6. Stage 1: show the complete plan, image prompts, reference roles and video-prompt blueprint; wait for approval.
7. Image preparation: generate the complete Reference Pack from the approved plan, save each full-size image locally, keep the first-slot product master faithful to the evidence, generate any storyboard preview separately, and let the compiler assign tokens in exact payload order. The presence of a generated presenter control does not change the approved voice mode.
8. No-cost preparation: execute `prepare_project.py -> preflight_project.py`. Configuration and platform validators remain internal development diagnostics; they do not create more user-facing gates.
9. Stage 2: show the actual ordered images, final prompt meaning, the same Stage 1 speaking subject or no-human-voice state, remaining sound layers, subtitle choice, settings, and paid request count.
10. Final authorization: accept `确认并生成` or an equally clear instruction given while viewing that exact set, then execute `workflow_engine.py confirm/submit/resume`.

Choose the approval image set from the selected model capability:

- Default MikuAPI relay route, `grok-imagine-video-1.5`: use 1–7 generated references, normally 3–5. Put the generated professional product master first, then add only generated presenter, wardrobe, scene, hand-action, product-detail, prop, style, or clean beat-keyframe controls. These references do not force the first frame. Plan at no more than 10 seconds per current reliable request, so a 15-second delivery is `10+5` and two paid requests.
- Preserved MikuAPI single-image route: prepare one final `video_source` / first-frame image that combines the selected product, presenter, scene, framing, and e-commerce style.
- Single-image route with scene changes: do not upload a 6-grid or 9-grid storyboard sheet as the only source image. Instead plan `per_segment_source_frames`, generate one approved source/first-frame image per shot, generate each clip separately, then stitch.
- Multi-reference routes: include the complete generated Reference Pack with the product master first. Each image has one primary role; raw evidence, non-generative derivatives, redundant/conflicting controls, and storyboard-preview uploads are rejected even when capacity remains.
- Seedance-style route: use `multi_reference_storyboard` when the ad needs shot order control. Upload product, presenter, scene, and storyboard references within model limits, and state that the storyboard is rhythm/order guidance only, not a literal grid layout to reproduce.
- If no model image is provided and the selected direction needs one, prepare a clearly synthetic digital-human/model reference suited to the product and platform; in review-first mode, wait until the user asks to continue.
- If the selected route's upload capacity is already full, plan a storyboard/contact-sheet as a preview-only approval image and clearly state it will not be uploaded to the video model.

Typical generated assets:

- one faithful generated professional product master based on all approved product evidence;
- one synthetic digital model holding or using the product;
- one scene still showing the lifestyle context;
- one 6-grid or 9-grid storyboard sheet as a review-only preview when useful;
- one final video source/first-frame image for source-image models when needed, containing the approved product, presenter, and scene.
- multiple segment source/first-frame images for single-image models when the ad has scene changes or story beats that should become separate clips.
- generated first-slot product master plus separate generated model/scene/hand/detail/style/keyframe controls, with prompt tokens assigned by the compiler before confirmation.

After preparing the images, save them locally and show the ordered token map in Stage 2. A missing/unreadable file, raw-image upload, invalid order/count, or unsupported factual claim blocks. Optional AI consistency notes are shown as warnings; the user decides whether the actual image needs regeneration in Stage 2.

## Stage 2 Decision Card Checklist

Always include only the decision essentials:

1. short product/material understanding and clearly labeled assumptions;
2. one selected AI recommendation with compact storyboard and approximate spoken copy;
3. one short optional revision direction, only when useful;
4. the actual local source/reference images that will be submitted;
5. platform, ratio, total duration, long-video split, speaker mode, plain-language speaking subject (画面人物/画外旁白/无语音), and exact paid request count;
6. subtitle choice: off by default, or local postproduction after the clean video;
7. one confirmation line using `确认并生成` and stating that no automatic retry or extra paid request will be added.

Keep all platform/scenario/compliance/model contracts, safe-zone details, token maps, prompt budgets, hashes, and payload fields in project files. Show them only when the user asks for technical detail or risk review.

## Internal Post-Image Checklist

After preparing images, verify internally and summarize only the useful parts in the final card:

1. generated first-frame/source image or storyboard/contact-sheet previews;
2. local file path for every generated image;
3. role for every image: `video_source`, `model`, `scene`, `storyboard`, `product_detail`, `campaign_preview`, or `preview_only`;
4. exact token map and upload count for the selected video model;
5. whether the final image set needs revision before Stage 2 authorization.

## Guarded Video Generation Steps

### Provider Prompt Compiler

Keep the complete advertising strategy in the plan contracts. The exact Provider prompt is a compact render instruction in this order:

1. `director_action`: one compiler-owned `Cuts` or `Sequence` timeline. Each beat carries commercial job, entry state, full subject action, framing, one main camera move/pace, focus, lighting/physical response, edit-safe exit and motivated transition;
2. `visual_direction`: approved framing, lighting and product-specific visual detail;
3. `creative_intent`: one compact commerce structure;
4. `factual_guardrail`: one always-present supplied-facts-only rule;
5. `reference_identity`: one canonical source/reference binding rule;
6. `render_guardrails`: clean frame, speech mode and product-motion policy;
7. `audio`: quoted `Dialogue`/`VO` for spoken plans, or `Speech=none; Voice=none` for no-human-voice plans, plus the approved sonic idea, a compact link to time-aligned sound-on-action cues, clip signature SFX, continuous ambience, score/energy relationship, compact mix direction, and optional user-selected voice reference only for spoken plans.

`prepare_project.py` records plan schema v3, director compiler `director-commerce-v10` and the `universal-product-director-v6` architecture in each shot's `prompt_contract`. It includes exact/component lengths, creative execution ratio, reference-map ratio, guardrail/audio ratios, action density, recommended prompt range, per-beat camera moves, removed duplicate blocks, `available_visual_chars`, and `sound_cue_coverage`. Sound coverage is a rewrite diagnostic and appears as a preflight warning when incomplete; it does not block an otherwise valid image/video request. Platform/scenario/compliance/billing details stay in `generation-plan.json`. The compiler hard-enforces exactly one of `Cuts` or `Sequence`, one reference map when references exist, one `AUDIO` section, and a non-contradictory frozen Stage 1 voice presentation: on-camera `Dialogue=`, off-screen `VO=`, or no-human-voice `Speech=none; Voice=none`. Mode, presentation and spoken-script conflicts stop before Stage 2; no later heuristic rewrites them. If essential approved content cannot fit the route's internal workflow budget, rewrite the visual direction—never truncate approved dialogue or identity rules. `max_prompt_chars` and `prompt_budget_chars` are adapter/workflow limits with explicit provenance, not an xAI-published universal character limit.

Before compiling split requests, allocate each semantic storyboard beat whole to one clip and reflow its local time. Because independent requests share no native audio state, restate the full instrument/rhythm/texture, ambience, signature SFX and mix inside every clip; never write “same as previous” or “沿用上一段”. `continuity_plan.edit_boundaries` and `stitching_plan.edit_boundaries` must record the outgoing stable state, incoming state, completed-action cut reason and audio bridge. `stitch_clips.py` preserves PCM intermediates and a single final AAC encode, then records that boundary, sound-continuity and loudness review are still required. Exact identical music across clips requires a separately approved local post mix.

1. Create a project folder:

   ```bash
   python3 ai-commerce-video/scripts/prepare_project.py --name <name> --product-image <path-or-url> --platform tiktok --placement in_feed --campaign-goal conversion --funnel-stage consideration --commerce-scenario ugc_review --creative-variant <variant> --cta-type shop_now --reference-strategy <strategy> --video-source-image <confirmed-final-source.png> --duration 25 --spoken-script '<approved complete script>' --subtitle-choice <disabled|enabled> --subtitle-request-source <default|user_plan_confirmation> --speaker-mode digital-human-spoken --product-motion-policy static-inanimate
   ```

   Use `--subtitle-request-source user_plan_confirmation` only when the user explicitly approved `--subtitle-choice enabled`; otherwise use the default disabled plan.

   For the default MikuAPI Grok 1.5 relay with an approved multi-reference set and a 30-second delivery:

   ```bash
   python3 ai-commerce-video/scripts/prepare_project.py --name <name> --product-image <raw-product-evidence.png> --brief <approved-visual-brief.json> --model-key grok_video_15_reference --reference-strategy multi_reference_commercial --generated-reference product=<generated-product-master.png> --generated-reference presenter=<generated-presenter-control.png> --generated-reference scene=<generated-scene-control.png> --storyboard-preview-image <generated-storyboard-review.png> --duration 30 --spoken-script '<two or more complete sentences>'
   ```

2. Run the single no-cost readiness check and freeze the production contract. This command does not require an API key and does not call the Provider:

   ```bash
   python3 ai-commerce-video/scripts/preflight_project.py --plan <project>/generation-plan.json --config ai-commerce-video/assets/templates/model-config.example.json
   ```

   Inspect `preflight-report.json`, `production-contract.json`, `model-snapshot.json`, and each dry-run request. Hard errors cover generated-file availability, raw-image isolation, payload/reference order, legal model fields and duration, frozen hashes, exact paid count, and duplicate-submit protection. Per-image evidence/QC detail and sound-cue completeness appear under `warnings` and do not block `paid_generation_allowed`. Missing optional subtitle tools are also warnings.

3. After final user approval, bind that exact frozen contract:

   ```bash
   python3 ai-commerce-video/scripts/workflow_engine.py --project-dir <project> confirm --approved-by user
   ```

4. Submit each base shot at most once:

   ```bash
   python3 ai-commerce-video/scripts/workflow_engine.py --project-dir <project> submit --config ai-commerce-video/assets/templates/model-config.example.json
   ```

   On the first submit, the command runs the configured no-cost `GET /v1/models` readiness check through the same network route that generation will use. The readiness report freezes the Provider, model, base URL and credential-free network-route summary; the generation worker recomputes and compares them immediately before POST. `generate_video.py --confirmed` is not a paid authorization path: real submission requires the immutable confirmation, readiness report, frozen production contract, paid cap and jobs ledger supplied by `workflow_engine.py submit`. Prompt-native speech does not call or depend on `GET /v1/tts/voices`; its dialogue/VO and delivery direction are already frozen in the prompt. A regional 403, DNS/connectivity failure, invisible target model, or network-route drift stops before the video POST, leaves the paid-attempt count at zero, and keeps `video-confirmation.json` valid. Once connectivity is restored, run `submit` again; do not ask for another confirmation unless the actual images, creative direction, speech meaning, subtitle choice, or paid count changed.

   The readiness check may use `AI_COMMERCE_VIDEO_PROXY_URL` as a Skill-only proxy. Otherwise it follows the standard environment/system route. It must never bypass the intended route for a misleading direct check, and must never edit Clash, another proxy app, or system network settings. Before the paid HTTP POST, submit also rebuilds the payload and model snapshot and compares them with the frozen preflight contract. Any drift blocks without contacting the Provider. Credentialed polling and Provider-result requests must remain on the frozen submit host; an external `status_url` or `response_url` is rejected before Authorization is sent. The final media URL may use a Provider CDN because that download carries no Provider API key. Once a video POST has been attempted, an unclear response is different: stop and do not rerun `submit`; the persistent ledger already records that paid attempt.

5. Poll or resume existing request IDs:

   ```bash
   python3 ai-commerce-video/scripts/workflow_engine.py --project-dir <project> resume --config ai-commerce-video/assets/templates/model-config.example.json
   ```

   Inspect the poll record's `provider_trace`: gateway task ID, gateway database record ID, true nested upstream task ID, channel ID, returned-prompt hash match, result URL hash, downloaded-video hash, and `provider_input_receipt_status`. Old request records are supported by recovering prompt and base64 image hashes from their saved payload. `unverified_provider_input` means the gateway did not echo an image fingerprint; it does not mean Codex sent the wrong file. If the returned prompt hash mismatches, stop before download. If the video is unrelated while prompt and local image evidence match, preserve the records for a provider incident report and do not auto-buy a retry.

6. Stitch if there are multiple clips:

   ```bash
   python3 ai-commerce-video/scripts/stitch_clips.py --project-dir <project> --target-resolution 720x1280 --target-fps 30 --require-audio
   ```

7. Review the clean output technically. Source-versus-first-frame comparisons and full business listening remain available as optional evidence:

   ```bash
   python3 ai-commerce-video/scripts/review_render.py --project-dir <project> --video <project>/final.mp4 --clean
   ```

   A new non-silent plan reports `awaiting_voice_review` until the narrow Stage 1 voice-contract report is recorded. Legacy plans remain `pending_business_review` for compatibility.

   For a spoken plan, listen/inspect the clean MP4 and record only the required voice facts. For a visible presenter, confirm both the audible line and visible speaking/mouth movement:

   ```bash
   python3 ai-commerce-video/scripts/review_voice_contract.py --project-dir <project> --review-method codex_multimodal --speech-present yes --speech-intelligible yes --speech-meaning-preserved yes --presenter-speaks-on-camera yes --visible-mouth-movement yes
   ```

   For off-screen voiceover, omit the last two presenter flags. For `no-speech`, use only `--unexpected-speech-absent yes`. This internal check creates no user confirmation, no Provider request and no paid-retry authorization. A failed report blocks delivery and preserves the existing one-submit ledger.

8. When the confirmed subtitle plan is enabled, generate and burn subtitles locally after clean review. Never send caption instructions back to the Provider:

   ```bash
   python3 ai-commerce-video/scripts/generate_subtitles.py --plan <project>/generation-plan.json --video <project>/final.mp4 --output <project>/subtitles/final.srt
   python3 ai-commerce-video/scripts/burn_subtitles.py --plan <project>/generation-plan.json --video <project>/final.mp4 --srt <project>/subtitles/final.srt --output <project>/final.captioned.mp4
   ```

9. Finalize after required technical checks and any selected caption work pass:

   ```bash
   python3 ai-commerce-video/scripts/finalize_project.py --project-dir <project>
   ```

## Long Video Consistency

For duration above the selected model limit:

- create one `visual_bible` section in the manifest;
- reuse the same approved generated product master and generated model/scene controls while keeping every raw evidence image outside the Provider payload;
- keep the same aspect ratio, resolution, palette, camera style, and reserved safe-zone layout;
- write every segment prompt as part of the same campaign;
- choose legal model duration slots with the minimum paid request count;
- give every segment a unique complete-sentence script and an intentional planned cut;
- do not silently add last-frame relay, extra segment sources, or repair requests because each can change cost or approved assets;
- stitch only after every segment has been downloaded and ffprobe-validated;
- normalize video consistently and use PCM intermediate speech audio, no fades/crossfades, then one final AAC encode.
- when a detailed business review is requested, judge speech by clarity and approximate selling meaning and listen separately for SFX, ambience, music and mix; an AAC stream is not proof;
- treat small timing, price, CTA, disclaimer, packaging-text, or visual differences as notes unless they make the video incomplete, incoherent, or unusable;
- record presenter identity, outfit, scene, and composition differences as optional review findings.

## Completion Standard

Do not report completion only because a request was submitted. Completion requires:

- request payload saved;
- outbound prompt, payload, and image fingerprints saved;
- poll result saved;
- provider chain and input-receipt status saved;
- MP4 downloaded locally and ffprobe-validated;
- multi-clip final video normalized, stitched, and ffprobe-validated if needed;
- stitch report saved when stitching is used;
- required technical review passed; the narrow Stage 1 voice-contract review passed for new non-silent plans, including absence of unplanned human speech for `no-speech`; optional full business-review findings are recorded when requested;
- caption review passed when subtitles are enabled;
- paid submission count did not exceed the confirmed cap;
- `delivery-manifest.json` exists with `status=pass`;
- final file path reported;
- obvious failures or model limitations explained.
