# Model Capabilities

This skill is model-config driven. Do not hardcode one model or one number of reference images. Choose the plan from the selected model's capabilities.

Source of truth for the 119337 route: Google Doc `API接入说明`, read on 2026-07-08.
Official xAI sources checked on 2026-07-15:

- https://docs.x.ai/developers/model-capabilities/video/generation
- https://x.ai/news/grok-imagine-video-1-5
- https://docs.x.ai/developers/pricing

Seedance 2.0 source references checked on 2026-07-08:

- https://fal.ai/models/bytedance/seedance-2.0/reference-to-video/api
- https://fal.ai/docs/documentation/model-apis/inference/queue

## Default Route

The default configured route is:

- provider: `119337`;
- base URL: `https://api.119337.xyz/v1`;
- create endpoint: `/video/generations`;
- poll endpoint: `/video/generations/{task_id}`;
- default model: `grok-video-1.5`;
- default duration: 15 seconds;
- Provider hard prompt limit: `max_prompt_chars=4096`;
- internal safe prompt budget: `prompt_budget_chars=3200`;
- primary mode: single-reference image-to-video.

## Capability Table

| Model | Text-to-video | Single image | Multi image | Max duration | Aspect ratio | Notes |
|---|---:|---:|---:|---:|---|---|
| `grok-video-1.5` | No | Yes, exactly 1 image | No | 15s | `16:9`, `9:16` | Working 119337 Provider alias for the official GA `grok-imagine-video-1.5` family; keep schemas distinct. |
| `grok-image-video` | Yes | Yes | Yes, up to 7 images | 15s text/single, 10s multi | `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3` | General model. Multi-reference requests over 10s are capped by the provider, so split before generation. |
| `seedance2` | No | Yes | Yes, up to 9 images | 15s | `9:16`, `16:9`, `1:1`, `4:3`, `3:4`, `21:9` | fal queue reference-to-video route. Use `FAL_KEY`; prompts cite references as `@Image1`, `@Image2`, etc. |

Resolution for the 119337 route: `720p` or `480p`.
Resolution for the bundled fal Seedance 2.0 route: config includes `480p`, `720p`, `1080p`, and `4k`; check current provider pricing and limits before paid generation.

The Provider prompt compiler keeps the detailed platform, scenario, and compliance contracts in the plan while sending only compact render instructions to the model. `prompt_budget_chars` is the normal hard workflow gate; `max_prompt_chars` is the Provider rejection boundary. Do not truncate approved visual details or spoken dialogue to fit either value. Remove only planning-only duplication, or split/redesign the segment before confirmation.

## Planning Rules

Use the selected model to decide how many reference images to generate and upload:

- If the selected model is `grok-video-1.5`, plan a single final video source image. This image must contain the approved product, presenter when needed, scene, and composition. Generate it only after the user approves the plan, then ask for image approval before video generation. Do not show the user a multi-reference upload plan for this model.
- If the selected model is `grok-video-1.5` and the approved ad has scene changes, do not upload a storyboard sheet as the one image. Generate one approved source/first-frame image per segment and use `--reference-strategy per_segment_source_frames` with repeated `--segment-source-image shot_XX=<path>` entries, then stitch the clips.
- If the selected model is `grok-image-video` and the request benefits from multiple references, plan product, presenter, scene, storyboard, product-detail, or style references as needed. If the user provided only product + model images, normally add at least one generated scene, storyboard, product-detail, style, or campaign-preview reference after plan approval, up to the 7-image limit. Keep multi-reference segments at 10 seconds or less.
- If the selected model is `seedance2`, prefer `multi_reference_storyboard` for story or scene-change ads: upload product, presenter, scene, and storyboard references within `max_reference_images`, cite the references as `@Image1`, `@Image2`, etc., and cite the storyboard token as shot rhythm/order guidance only.
- If a future configured model supports more images, follow `max_reference_images`, `reference_field`, `reference_payload_format`, and duration limits in `model-config.example.json`.
- If a future configured model supports text-to-video only, create a text-only plan and do not invent image uploads.
- Use `model_capability_contract` in `generation-plan.json` to record `supports_audio`, `supports_lip_sync`, `supports_multi_segment_generation`, `source_image_field`, `reference_field`, `reference_payload_format`, `max_reference_images`, duration limits, `prompt_budget_chars`, `max_prompt_chars`, and the prompt compiler version. Platform validation should read this contract/config instead of hardcoding model behavior.

## 119337 Request Mapping

Use provider fields:

- duration field: `seconds`;
- preferred image field: `image_urls`;
- image value format: HTTPS URL or complete base64 data URL;
- create response task ID: `data.task_id`;
- poll success video URL: `data.result_url`;
- poll failure reason: `data.fail_reason`.

Do not send old OpenAI/xAI-style fields such as `duration`, `image: {url: ...}`, or `video.url` as the primary 119337 path.

## Seedance 2.0 fal Request Mapping

Use provider fields from `model-config.example.json`:

- auth env var: `FAL_KEY`;
- auth scheme: `Key`;
- create endpoint: `/bytedance/seedance-2.0/reference-to-video`;
- status endpoint: `/bytedance/seedance-2.0/reference-to-video/requests/{request_id}/status`;
- result endpoint: `/bytedance/seedance-2.0/reference-to-video/requests/{request_id}/response`;
- duration field: `duration`;
- reference image field: `image_urls`;
- reference token style: `@Image1`, `@Image2`, etc.;
- submit response: `request_id`, `status_url`, `response_url`;
- poll success status: `COMPLETED`;
- result video URL: `video.url`.

Do not send the 119337/Grok-specific `model` or `seconds` fields to the fal Seedance route.

## Duration Splitting

The official xAI API currently documents a general 1-15 second duration range for its native route. This skill uses a configured Provider-compatible route, so production requests must follow the stricter local `allowed_duration_seconds` contract until that Provider route is deliberately revalidated. Do not confuse the official model family with a gateway alias or assume their request schema, allowed values, or billing are identical.

If requested duration is longer than the selected model or selected image mode supports:

1. Select only request values listed in `allowed_duration_seconds` or `allowed_multi_reference_duration_seconds`.
2. Use the minimum paid request count; exact delivery sum wins, otherwise use the smallest legal overshoot.
3. Split the approved spoken script into complete sentences and store a unique `spoken_script` for every segment.
4. Use one campaign-level visual bible and intentional `planned_cut` continuity.
5. Save each segment prompt separately and forbid all Provider-generated written overlays.
6. Stitch only after every generated MP4 is verified. Normalize speech audio to PCM intermediates, apply no fades/crossfades, and encode AAC once at the end.
7. Trim only a verified silent/idle tail. Never cut a spoken word.

Examples:

- `grok-video-1.5`, 15s, one image -> one 15s clip.
- `grok-video-1.5`, user wants model + product + scene -> first plan one composite source image, generate it after plan approval, confirm it, then create one 15s clip.
- `grok-video-1.5`, 25s delivery -> two paid clips using legal slots `15s + 10s`.
- `grok-video-1.5`, 30s delivery -> two paid clips using legal slots `15s + 15s`.
- `grok-image-video`, 15s, one image -> one 15s clip.
- `grok-image-video`, multi-reference 15s delivery -> legal minimum-count plan `10s + 6s`; review and locally trim only the verified idle tail to 15s.
- `seedance2`, product + presenter + scene + 6-grid storyboard, 15s -> one 15s multi-reference storyboard request if the configured provider supports it.
- 45s on a 15s route -> three clips, 15s + 15s + 15s.

The configured Grok legal slots are `4, 6, 8, 10, 12, 15`. Never send 5s, 7s, 13s, or another arbitrary value unless a selected model config explicitly lists it.

## Model Choice Rules

- Use the configured default `grok-video-1.5` when one final approved source image is enough.
- Use `grok-image-video` when text-to-video or multiple reference images are genuinely needed.
- Use `seedance2` when the user has `FAL_KEY` configured and the ad needs multi-reference storyboard control without forcing a multi-clip Grok workflow.
- If only a product image is provided but the ad needs a presenter and the selected model is single-image only, plan a composite presenter-product source image and generate it with Codex `imagegen` after plan approval.
- If a single-image model is selected but the storyboard requires scene changes, switch to per-segment source frames rather than using a storyboard sheet as the only source image.
- If product and model images are already provided, still plan the video-facing approval image(s): one composite `video_source` for single-image routes, or at least one generated scene/storyboard/campaign-preview reference for multi-reference routes when capacity allows.
- If a user asks for multiple reference control, switch to a configured model that supports multi-reference images, such as `grok-image-video` or `seedance2`, before generating the final video.
- If the user asks for a real identifiable person, require clear permission and avoid face cloning by default. Prefer synthetic digital-human references.
