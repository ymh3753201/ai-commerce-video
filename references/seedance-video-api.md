# Seedance 2.0 Video API

Use this reference when the selected model key is `seedance2`.

Source references checked on 2026-07-08:

- https://fal.ai/models/bytedance/seedance-2.0/reference-to-video/api
- https://fal.ai/docs/documentation/model-apis/inference/queue

## Configured Route

The bundled `seedance2` model config uses the fal queue route:

- provider: `fal_queue`;
- base URL: `https://queue.fal.run`;
- create endpoint: `/bytedance/seedance-2.0/reference-to-video`;
- status endpoint: `/bytedance/seedance-2.0/reference-to-video/requests/{request_id}/status`;
- result endpoint: `/bytedance/seedance-2.0/reference-to-video/requests/{request_id}/response`;
- auth header: `Authorization: Key $FAL_KEY`;
- API key env var: `FAL_KEY`.

Keep `FAL_KEY` only in a private env file or shell environment. Do not write it into this skill, tests, README, prompts, logs, or package files.

## Payload Contract

Seedance 2.0 reference-to-video accepts up to 9 reference images through:

```json
{
  "prompt": "Use @Image1 as the product and @Image2 as the storyboard guide...",
  "image_urls": ["https://example.com/product.png", "https://example.com/storyboard.png"],
  "duration": 15,
  "aspect_ratio": "9:16",
  "resolution": "720p",
  "generate_audio": true,
  "bitrate_mode": "standard"
}
```

Do not send the 119337/Grok-specific `model` or `seconds` fields to this route. The endpoint identity is already in the URL.

## Reference Tokens

Use `reference_prompt_style: seedance_image`, which maps uploaded references in order:

- first reference: `@Image1`;
- second reference: `@Image2`;
- third reference: `@Image3`;
- continue up to the configured `max_reference_images`.

For a storyboard ad, a safe prompt map is:

```text
Reference image map: @Image1 = product reference; @Image2 = synthetic presenter reference; @Image3 = lifestyle scene reference; @Image4 = 6-panel storyboard reference.
Use @Image4 only for shot order, timing, and rhythm. Render full-screen vertical video; do not reproduce the storyboard sheet grid, panel borders, labels, or collage layout.
```

## Queue Flow

1. Submit JSON to the create endpoint.
2. Save `request_id`, `status_url`, and `response_url` from the submit response.
3. Poll `status_url` until status is `COMPLETED`.
4. Fetch `response_url`.
5. Download `video.url` from the result response.

The skill's `generate_video.py` and `poll_video.py` scripts implement this route from model config. Do not hardcode fal behavior into prompts or user-facing plans; choose it by selecting model key `seedance2`.

## Multi-Storyboard Use

Use `multi_reference_storyboard` when the ad needs multiple scenes or a story reversal and the selected model is `seedance2`:

- upload product identity images first;
- upload presenter/model identity only when the user approved that image;
- upload a generated scene or campaign preview if it helps style consistency;
- upload the 6-grid or 9-grid storyboard sheet as one reference;
- cite the storyboard token as sequence/rhythm guidance only.

If the story needs too many independent scenes, still prefer shorter segments or a simpler storyboard. A 15-second ad should usually have 3 to 5 beats, not a complex mini-film.
