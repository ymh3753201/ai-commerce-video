# 119337 Grok Video API

Use this reference for the configured 119337 Grok video gateway.

Source of truth: Google Doc `API接入说明`, read on 2026-07-08.

## Environment Variables

Accepted API key variables, checked in this order:

1. `AI_COMMERCE_VIDEO_API_KEY`
2. `YUNWU_API_KEY`

`XAI_API_KEY` is deliberately not accepted by the bundled third-party route. Do not print or save the raw key, and do not forward a credential issued for one provider to another provider's host.

The scripts also auto-load private runtime variables from:

1. the file path in `AI_COMMERCE_VIDEO_ENV_FILE`, when set;
2. `~/.codex/ai-commerce-video.env`, when present;
3. `<skill>/.env.local`, when present.

Recommended setup command:

```bash
python3 ~/.codex/skills/ai-commerce-video/scripts/setup_private_env.py
```

Defaults:

- `AI_COMMERCE_VIDEO_BASE_URL`: `https://api.119337.xyz/v1`
- `AI_COMMERCE_VIDEO_MODEL`: `grok-video-1.5`

## Endpoints

Model list:

```text
GET {base_url}/models
```

Create video task:

```text
POST {base_url}/video/generations
```

Poll video task:

```text
GET {base_url}/video/generations/{task_id}
```

The API is asynchronous. The create call returns a `task_id`; the client polls until success or failure.

## Models

`grok-video-1.5`:

- single-reference image-to-video only;
- text-to-video: not supported;
- multi-reference: not supported;
- must provide exactly one reference image;
- max duration: 15 seconds;
- aspect ratios: `16:9`, `9:16`;
- resolutions: `720p`, `480p`.

`grok-image-video`:

- text-to-video: supported, max 15 seconds;
- single-reference image-to-video: supported, max 15 seconds;
- multi-reference image-to-video: supported, up to 7 images, max 10 seconds;
- aspect ratios: `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`;
- resolutions: `720p`, `480p`.

The provider recommends using `GET /v1/models` as the final source if model availability changes.

## Request Fields

Required:

- `model`: model ID, such as `grok-video-1.5` or `grok-image-video`;
- `prompt`: compact video-render prompt. The configured 119337 route rejects values above `max_prompt_chars=4096`; this skill uses `prompt_budget_chars=3200` as the safer preflight gate.

Optional:

- `seconds`: video duration. Recommended values for text/single-image: `[4, 6, 8, 10, 12, 15]`; multi-reference: `[4, 6, 8, 10]`.
- `aspect_ratio`: aspect ratio.
- `resolution`: `720p` or `480p`.
- `image_urls`: recommended unified image input field; array of HTTPS image URLs or complete base64 data URLs.
- `images`: equivalent to `image_urls`; do not send both.
- `input_reference`: single-reference object, e.g. `{ "image_url": "..." }`.
- `reference_images`: multi-reference field; this skill prefers `image_urls` because the provider recommends it.

Local files are encoded by `scripts/generate_video.py` as complete base64 data URLs, not bare base64.

## Payload Examples

Single image, default configured route:

```json
{
  "model": "grok-video-1.5",
  "prompt": "Animate the product with a slow rotating camera, soft studio light, premium commercial style",
  "seconds": 15,
  "aspect_ratio": "9:16",
  "resolution": "720p",
  "image_urls": [
    "data:image/png;base64,..."
  ]
}
```

Multi-reference route:

```json
{
  "model": "grok-image-video",
  "prompt": "Create a smooth product showcase video using these references, clean e-commerce lighting",
  "seconds": 10,
  "aspect_ratio": "9:16",
  "resolution": "720p",
  "image_urls": [
    "data:image/png;base64,...",
    "data:image/png;base64,..."
  ]
}
```

## Responses

Create response:

```json
{
  "code": "success",
  "message": "",
  "data": {
    "task_id": "task_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "status": "SUBMITTED"
  }
}
```

Poll success:

```json
{
  "code": "success",
  "message": "",
  "data": {
    "task_id": "task_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "status": "SUCCESS",
    "progress": "100%",
    "result_url": "https://example.com/generated-video.mp4",
    "fail_reason": ""
  }
}
```

Poll failure:

```json
{
  "code": "success",
  "message": "",
  "data": {
    "task_id": "task_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "status": "FAILURE",
    "progress": "100%",
    "result_url": "",
    "fail_reason": "Image URL could not be fetched..."
  }
}
```

Judge completion by `data.status`, not by `progress`.

## Common Errors

- `401`: API key missing or wrong.
- `403`: permission, quota, or group restriction.
- `400 prompt is required`: prompt is empty.
- `400 Prompt length exceeds the maximum allowed length of 4096`: the request bypassed or failed the prompt compiler/preflight gate. Do not pay-submit a manually truncated retry; recompile the plan, verify the exact dry-run payload, and ask for confirmation again.
- `400 model field is required`: model is empty or unsupported.
- `400 only supports exactly one reference image`: `grok-video-1.5` received zero or multiple images.
- Image fetch failure: use public HTTPS image URLs or full base64 data URLs.

## Safety and Cost Controls

- Run `generate_video.py --dry-run` before a real request and verify the exact prompt length recorded in `prompt_contract`.
- Run no-cost `preflight_project.py` first, bind the approved contract with `workflow_engine.py confirm`, and submit with `workflow_engine.py submit` only after user approval. Continue existing request IDs with `poll`/`resume`; do not automatically resubmit.
- The configured Provider alias `grok-video-1.5` belongs to the `grok-imagine-video-1.5` family. Keep the working Provider alias in the payload unless the Provider contract is deliberately updated and revalidated.
- Never request subtitles or any newly generated written overlay from the video model. Create exact captions locally after the clean output passes review.
- Save request payloads and response bodies under the project folder.
- Download `data.result_url` promptly; it is a temporary URL.
- Treat "request submitted" as incomplete until a local MP4 exists.
