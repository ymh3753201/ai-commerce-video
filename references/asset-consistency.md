# Asset Consistency

Use this reference whenever a proposal includes uploaded images, Codex-generated images, preview images, storyboards, or video generation.

## Core Rule

The video API can only use files explicitly passed to the scripts. Images shown in chat or described in text are not automatically available to the video model.

Before paid generation, create an asset ledger:

- `product`: original user product image;
- `model` or `presenter`: digital-human/person reference;
- `scene`: environment or usage-scene reference;
- `storyboard`: 6-grid or 9-grid storyboard;
- `video_source`: final confirmed source/first-frame image for source-image routes;
- `segment_source`: final confirmed source/first-frame image for one segment in a multi-clip single-image route;
- `last_frame` or `first_frame`: continuity references for multi-clip workflows.

Always show the user which actual files will be uploaded to the video model.

## Visual Approval Assets

User-supplied product/model images are source assets, not a complete visual approval set by themselves. Before generating new images, first ask the user to approve the image-generation plan. After approval, generate and save the images the user needs to inspect the ad direction:

- For single-image models, the approval set must include one final `video_source` image generated or selected for the campaign. This is the image that will be uploaded to the video model.
- For single-image models with scene changes, the approval set must include one `segment_source` image per clip. A storyboard sheet can be shown as `preview_only`, but it must not be the only image uploaded to the single-image video model.
- For multi-reference models, the approval set should include all uploaded references and at least one generated campaign visual, such as `scene`, `storyboard`, `product_detail`, `style`, or `campaign_preview`, when the model's `max_reference_images` allows it.
- If an image is generated only to help the user review the storyboard and will not be uploaded, label it `preview_only` and say so in the proposal.
- Do not proceed from a product+model-only plan to paid video generation unless the user explicitly approved skipping generated approval images.

The proposal and the dry-run must agree. Any generated approval image that is meant to influence the video must appear in `asset_contract.video_source_asset` or `asset_contract.video_reference_assets`, and then in the dry-run payload.

For `per_segment_source_frames`, each generated segment source must appear in `asset_contract.segment_source_assets`, and every shot in `generation-plan.json` must use the matching segment source as its `image`.

## Variable Material Handling

Every project can have a different source set. Classify supplied assets before deciding what to generate:

- Multiple product angles: keep the strongest image as `hero_product`; use other angles as `product_detail`, `packaging_or_label`, `angle_detail`, or `preview_only` according to quality and model capacity.
- Product + model image: keep both as source assets, then plan generated scene, storyboard, first-frame, product-detail, or campaign-preview assets before video generation.
- Product only: infer product category and buyer scenario, then plan a synthetic presenter/model image only if the ad direction needs a person; otherwise plan product-only hero, scene, or storyboard images.
- Model only or unclear product: ask for a product image or product description before creating a final video-generation plan.
- Low-quality or mismatched images: do not upload them by default; label them as `preview_only` or request/generate a better source image.

## Model Input Modes

Use the model config, not a hardcoded assumption:

- `input_mode: image-to-video`: upload the source image through `source_image_field` using `source_payload_format`, for example `image_urls: ["data:image/png;base64,..."]` on the 119337 route. If `supports_multiple_references` is true, upload only the confirmed references allowed by `max_reference_images` through `reference_field` using `reference_payload_format`.
- `input_mode: reference-to-video`: upload product, presenter, scene, storyboard, or other confirmed assets through the configured reference field. The prompt must cite the assigned tokens.
- `supports_multiple_references: false`: do not rely on separate reference images. Generate or choose one composite `video_source` image that already contains the approved product, presenter, and scene.
- `reference_strategy: per_segment_source_frames`: for single-image models with scene changes, generate multiple approved source/first-frame images and submit one request per segment.

## Reference Token Map

For multi-reference models, every uploaded reference must have a prompt token:

- Grok/xAI-style routes use `<IMAGE_1>`, `<IMAGE_2>`, and so on unless the config says otherwise.
- The bundled fal Seedance 2.0 route uses `@Image1`, `@Image2`, and so on. Older wrappers may use `@(img1)`, but only use that when the selected config says `reference_prompt_style: seedance_at`.

Example prompt fragment:

```text
Source image rule: <SOURCE_IMAGE> is the uploaded first frame.
Reference image map: <IMAGE_1> = model reference; <IMAGE_2> = storyboard reference.
Use <IMAGE_1> for the presenter identity and <IMAGE_2> for shot rhythm.
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

For models with `supports_multiple_references: true`:

- pass every confirmed reference that should affect generation as `--reference-image role=<path>`;
- keep role names meaningful: `model`, `presenter`, `scene`, `storyboard`, `product_detail`, `style`, `first_frame`, or `video_source`;
- if uploading a storyboard sheet, state in the prompt that it is shot order/rhythm guidance only and that the model must render full-screen video, not a collage or grid;
- when the user supplies only product and model images, generate at least one additional approval reference such as `scene`, `storyboard`, or `campaign_preview` if the model still has reference capacity;
- run `prepare_project.py`, then inspect `asset_contract.reference_prompt_map`;
- run `generate_video.py --dry-run`, then inspect `asset_trace.references_included_in_payload`, `asset_trace.reference_count`, and `asset_trace.payload_reference_roles`;
- if the dry-run payload does not contain the confirmed reference images, stop and fix the plan before a paid request.

## When Existing Images Are Not Suitable

If the uploaded product image is not a good video source or reference, use Codex `imagegen` to create a better image:

- preserve product identity and important product details;
- include the approved presenter, scene, and composition when a source image is required;
- use the e-commerce style approved by the user;
- save the generated image as a local file;
- show it to the user for confirmation;
- pass that file as `--video-source-image` or `--reference-image role=<path>` according to the selected model mode.

## Dry-Run Gate

After `generate_video.py --dry-run`, inspect the request file:

- `asset_trace.source_image.value`: source image actually uploaded through the source field;
- `asset_trace.locked_video_source.value`: source image selected by the plan;
- `asset_trace.segment_source_count`: number of approved per-segment source images, when that strategy is used;
- `asset_trace.references_included_in_payload`: true when references are uploaded;
- `asset_trace.reference_prompt_map`: prompt token to local file mapping;
- `asset_trace.payload_reference_roles`: roles actually included in the video API payload.

If the user confirmed a reference image and it is missing from the payload, do not call the paid video API.
