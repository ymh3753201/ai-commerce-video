# Asset Consistency

Use this reference whenever a proposal includes uploaded images, Codex-generated images, preview images, storyboards, or video generation.

## Core Rule

The video API can only use files explicitly passed to the scripts. Images shown in chat or described in text are not automatically available to the video model.

Before paid generation, create an asset ledger with three distinct layers:

- `input_evidence_assets`: original user product, detail, model or scene files used to establish facts and identity;
- `generated_reference_assets`: generated `presenter`, `wardrobe`, `scene`, `hand_action`, `product_detail`, `prop`, `style`, or clean full-frame `beat_keyframe_*` controls that may enter later Reference-to-Video slots;
- `approval_preview_assets`: generated storyboard/contact sheet or annotated review images that never enter Reference-to-Video;
- `video_source`: final confirmed source/first-frame image for source-image routes;
- `segment_source`: final confirmed source/first-frame image for one segment in a multi-clip single-image route;
- `last_frame` or `first_frame`: continuity references for multi-clip workflows.

Always show the user which actual files will be uploaded to the video model.

## Visual Approval Assets

On the default route, every user upload remains evidence. The generated professional product master is the first Stage 2 Provider slot. Stage 1 must show the product-master prompt and every planned support-control prompt before any control is created:

- For single-image models, the approval set must include one final `video_source` image generated or selected for the campaign. This is the image that will be uploaded to the video model.
- For single-image models with scene changes, the approval set must include one `segment_source` image per clip. A storyboard sheet can be shown as `preview_only`, but it must not be the only image uploaded to the single-image video model.
- For the default multi-reference route, generate the complete Reference Pack, keep the professional product master first, and add only the single-purpose controls the approved clip genuinely needs.
- If an image is generated only to help the user review the storyboard and will not be uploaded, label it `preview_only` and say so in the proposal.
- Do not generate Provider references before Stage 1 creative approval. Do not proceed to paid video generation until the exact ordered upload set is visible in Stage 2 and covered by `确认并生成`.
- Before Stage 2, save every generated Provider reference locally and show the full-size actual file. Concrete evidence IDs, observed-mechanism notes and AI consistency findings are useful trace data, but missing or pending advisory fields do not replace or delay the user's Stage 2 approval.

The proposal and the dry-run must agree. Any generated approval image that is meant to influence the video must appear in `asset_contract.video_source_asset` or `asset_contract.video_reference_assets`, and then in the dry-run payload.

For `per_segment_source_frames`, each generated segment source must appear in `asset_contract.segment_source_assets`, and every shot in `generation-plan.json` must use the matching segment source as its `image`.

## Variable Material Handling

Every project can have a different source set. Classify supplied assets before deciding what to generate:

- Multiple product angles: use all trustworthy views as identity evidence, then generate one faithful professional product master as the first Provider reference; generate a separate detail control only when needed.
- Product + model image: keep both as evidence, then generate a coherent product master, presenter control and any necessary scene/detail control after Stage 1.
- Product only: infer product category and buyer scenario, then plan a synthetic presenter/model image only if the ad direction needs a person; otherwise plan product-only hero, scene, or storyboard images.
- Model only or unclear product: ask for a product image or product description before creating a final video-generation plan.
- Low-quality or mismatched images: do not upload them by default; label them as `preview_only` or request/generate a better source image.
- Exact software UI: when real interface pixels must remain exact, choose an explicit single-image or per-segment Image-to-Video route and disclose that route in Stage 1. Do not quietly place a raw screenshot inside the default evidence-only R2V Reference Pack.

## Ordered Imagegen Evidence Set

Treat all trustworthy views of one SKU as one ordered `product_identity_evidence` set, not as unrelated optional references. Repeat `--product-image` for ordinary front, side, back, packaging, detail, real-use, or worn views of that same product. When one file has two roles—for example a model photo that also proves the exact garment fit—keep its ordinary `model` role and explicitly include its asset ID in `visual_design.product_identity_evidence_asset_ids`. Do not include a different SKU, duplicate, scene-only, or style-only image in this set.

For every Codex `imagegen` call whose result contains or depends on the product—`product`, `product_detail`, product-wearing/holding `presenter`, `wardrobe`, `hand_action`, and clean `beat_keyframe_*` controls—pass the complete ordered set as `referenced_image_paths`. Add a person, scene, or style path only when that specific control needs it. Refer to each input by order and purpose in the image prompt, such as front identity, worn fit, or back/port detail. A pure empty-scene or style plate does not need product evidence.

The prepared plan can record `generation_input_asset_ids`, `generation_input_paths`, `generation_input_sha256`, and `generation_input_policy` for each generated control. These fields are useful local trace data; they are not a Provider receipt. Preflight reports incomplete evidence/QC records as warnings. It blocks only when the actual Provider set violates the hard asset contract, such as a raw user image, unreadable generated file, missing first-slot product master, illegal count/order, or preview-grid upload.

## Model Input Modes

Use the model config, not a hardcoded assumption:

- `input_mode: reference-to-video`: upload only the complete generated Reference Pack through `reference_field`. On the default MikuAPI relay and optional official xAI route this is REST `reference_images`; it is mutually exclusive with `image`, and every raw evidence image, non-generative derivative and storyboard preview is forbidden.
- `input_mode: image-to-video`: upload one source image through `source_image_field`, for example `image: {"url":"data:image/png;base64,..."}` on the preserved MikuAPI route.
- `input_mode: reference-to-video`: upload product, presenter, scene, storyboard, or other confirmed assets through the configured reference field. The prompt must cite the assigned tokens.
- `supports_multiple_references: false`: do not rely on separate reference images. Generate or choose one composite `video_source` image that already contains the approved product, presenter, and scene.
- `reference_strategy: per_segment_source_frames`: for single-image models with scene changes, generate multiple approved source/first-frame images and submit one request per segment.

## Reference Token Map

For multi-reference models, every uploaded reference must have a prompt token:

- The default MikuAPI Grok route and optional official xAI Grok route use `<IMAGE_0>`, `<IMAGE_1>`, and so on in exact payload order. Other routes follow their configured index base.
- The bundled fal Seedance 2.0 route uses `@Image1`, `@Image2`, and so on. Older wrappers may use `@(img1)`, but only use that when the selected config says `reference_prompt_style: seedance_at`.

The compiler—not the freeform visual direction—owns this mapping. Example compiled fragment:

```text
Source image rule: <SOURCE_IMAGE> is the uploaded first frame.
Reference image map: <IMAGE_0> = generated professional product master; <IMAGE_1> = generated presenter control; <IMAGE_2> = generated scene control.
Use each image only for its assigned element role.
```

For 119337 `grok-image-video`, the payload field is usually one `image_urls` list. In that case the prompt token map should refer to the ordered images in that list, not to an imaginary separate source field.

For Seedance:

```text
Reference image map: @Image1 = product reference; @Image2 = model reference.
Use @Image1 as the hero product appearance and @Image2 as the presenter identity.
```

## Single-Image Models

For any model with `supports_multiple_references: false`:

- generate or choose one final `video_source` image that already contains the approved product, presenter, and scene;
- if the storyboard needs multiple scenes, generate one `segment_source` image per scene instead of one storyboard grid;
- pass it as `--video-source-image <path>` or `--reference-image video_source=<path>`;
- for per-segment workflows, pass each image as `--segment-source-image shot_01=<path>`, `--segment-source-image shot_02=<path>`, and so on;
- do not assume separate `model`, `scene`, or `storyboard` images affect the video;
- inspect the dry-run request JSON and confirm `asset_trace.source_image.value` equals the confirmed `video_source` path.

Correct single-image command:

```bash
prepare_project.py --product-image original-product.png --video-source-image approved-presenter-product-source.png --reference-image storyboard=approved-storyboard.png
```

Correct single-image multi-segment command:

```bash
prepare_project.py --product-image original-product.png --reference-strategy per_segment_source_frames --segment-source-image shot_01=approved-hook-source.png --segment-source-image shot_02=approved-demo-source.png --segment-source-image shot_03=approved-cta-source.png --duration 15
```

## Multi-Reference Models

For the default route with `supports_multiple_references: true` and `require_generated_video_references: true`:

- pass every trustworthy same-SKU product view as a repeated `--product-image`; pass optional person, scene, style, or other non-product evidence with `--reference-image role=<path>`;
- pass the complete Provider Reference Pack as `--generated-reference role=<local-path>`, beginning with exactly one `product=<professional-master>`;
- add later roles such as `presenter`, `wardrobe`, `scene`, `hand_action`, `product_detail`, `prop`, `style`, or uniquely named `beat_keyframe_hook` / `beat_keyframe_proof` only when necessary;
- pass a storyboard/contact sheet only as `--storyboard-preview-image`; never as `--generated-reference`;
- run `prepare_project.py`, then inspect `asset_contract.reference_prompt_map`;
- run `generate_video.py --dry-run`, then inspect `asset_trace.references_included_in_payload`, `asset_trace.reference_count`, and `asset_trace.payload_reference_roles`;
- if the dry-run payload does not contain the confirmed reference images, stop and fix the plan before a paid request.

## When Existing Images Are Not Suitable

On the default route, use Codex `imagegen` to translate all evidence into an approved, fully generated Reference Pack:

- regenerate the first-slot professional product master and preserve product identity and important product details;
- include the approved presenter, scene, and composition when a source image is required;
- use the e-commerce style approved by the user;
- save the generated image as a local file;
- show its prompt in Stage 1, then show the actual generated file in Stage 2 for `确认并生成`;
- pass Reference-to-Video controls as `--generated-reference role=<path>`; use `--video-source-image` or `--segment-source-image` only for an explicitly selected Image-to-Video route.

## Dry-Run Gate

After `generate_video.py --dry-run`, inspect the request file:

- `asset_trace.source_image.value`: source image actually uploaded through the source field;
- `asset_trace.locked_video_source.value`: source image selected by the plan;
- `asset_trace.segment_source_count`: number of approved per-segment source images, when that strategy is used;
- `asset_trace.references_included_in_payload`: true when references are uploaded;
- `asset_trace.reference_prompt_map`: prompt token to local file mapping;
- `asset_trace.payload_reference_roles`: roles actually included in the video API payload.
- `asset_trace.reference_asset_policy`: must be `generated_reference_pack_only` on the default route.
- `asset_trace.raw_input_assets_uploaded` and `raw_non_product_assets_uploaded`: both must be false.
- `request_evidence.source_images`: hashes of the exact data-URI image bytes or URL fingerprints placed into the outbound payload.

If the user confirmed a reference image and it is missing from the payload, do not call the paid video API.

After polling, inspect `provider_trace.provider_input_receipt_status`. `verified` requires an upstream-reported image hash matching the sent hash. `unverified_provider_input` means only the outbound side is proven; require source-versus-first-frame multimodal review and preserve evidence if the result is unrelated.
