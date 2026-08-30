# Grok Imagine Video 1.5 Provider Routes

Use this reference for the default `grok_video_15_reference` route. It calls MikuAPI as a relay while preserving the `grok-imagine-video-1.5` Reference-to-Video request structure. The optional `grok_video_15_reference_xai` route calls official xAI directly with a separate credential. The preserved `grok_video_15` route is a separate MikuAPI single-image adapter and must not inherit the multi-reference payload.

Official sources checked on 2026-08-24:

- https://x.ai/news/grok-imagine-video-1-5-references
- https://docs.x.ai/developers/model-capabilities/video/generation
- https://docs.x.ai/developers/model-capabilities/video/reference-to-video
- https://docs.x.ai/developers/model-capabilities/video/image-to-video
- https://docs.x.ai/developers/model-capabilities/audio/text-to-speech

## Endpoints and Model

```text
Default base URL: https://mikuapi.org
Optional direct base URL: https://api.x.ai
GET  /v1/models
GET  /v1/tts/voices  # optional diagnostic on routes that expose it
POST /v1/videos/generations
GET  /v1/videos/{request_id}
Model: grok-imagine-video-1.5
```

The default MikuAPI route uses only `AI_COMMERCE_VIDEO_MIKUAPI_KEY` or macOS Keychain service `ai-commerce-video-mikuapi-video`. The optional official route uses only `XAI_API_KEY` or Keychain service `ai-commerce-video-xai-video`; never send that official key to MikuAPI, 119337, fal, or another relay.

The project owner defines MikuAPI as an API relay for the same model and endpoint schema. Therefore the default route keeps the official visual field design; only Provider identity, base URL and credential source differ. Official xAI capability and the relay's verified capability must be reported separately. Local config, dry-run, mock HTTP, and free model-readiness checks are verified. The relay currently does not expose `/v1/tts/voices`; this does not block prompt-native speech. Real paid `reference_audios` compatibility remains unverified and is outside the default path.

## Reference-to-Video Contract

This is the default professional commerce mode on MikuAPI and the optional direct mode on xAI:

- REST field `reference_images`: 1–7 objects containing `url`;
- Python SDK parameter `reference_image_urls`: 1–7 URL strings;
- each URL may be public HTTPS or a complete base64 data URI;
- prompt tokens: the adapter currently uses `<IMAGE_0>` through `<IMAGE_6>` in payload order. xAI documentation includes both a zero-based statement and a one-based-looking example, so `reference_index_base` and its provenance remain route configuration, not a universal official claim;
- `duration`: integer 1–15 in the official/request contract. The current MikuAPI R2V route uses a 10-second reliable planning ceiling because two saved 15-second requests returned about 10.042 seconds;
- `aspect_ratio`: normally `9:16` or `16:9`;
- `resolution`: `480p` or `720p`; reference-to-video is capped at 720p.

References guide people, product, clothing, location, scene, and style without forcing the first frame. One image should have one primary role. Use the smallest useful portfolio, normally 3–5; seven is a maximum, not a target.

The Skill's default route adds a stricter advertising-production policy above the raw API capability: every user upload remains in `input_evidence_assets`. After Stage 1 approval, generate the complete `reference_images` set, beginning with a faithful professional product master and followed by only the necessary single-purpose controls. Storyboard/contact sheets remain `approval_preview_assets`. The request builder rejects raw/copy-identical evidence reuse, a missing or non-first generated product master, non-local generated controls, storyboard roles, and non-canonical manual image-token maps.

```json
{
  "model": "grok-imagine-video-1.5",
  "prompt": "Use <IMAGE_0> to lock the product and <IMAGE_1> to lock the presenter...",
  "reference_images": [
    {"url": "data:image/png;base64,..."},
    {"url": "data:image/jpeg;base64,..."}
  ],
  "duration": 10,
  "aspect_ratio": "9:16",
  "resolution": "720p"
}
```

## Native Speech, Sound Design, and Optional Preset Voice

Stage 1 chooses the voice relationship before reference generation. Spoken ads use prompt-native speech: put the approved dialogue/VO and a concise language, tone, pace, emotion, or delivery description in the single `AUDIO` block, and omit `reference_audios`. Use `Dialogue=` plus visible speaking/natural mouth movement for approved 人物口播; use `VO=` plus an off-screen direction for approved detached narration. For `no-speech`, use `Speech=none; Voice=none`, keep any visible presenter silent, and retain the approved non-speech sound layers. Never infer a different voice mode merely because a presenter reference exists.

```json
{
  "prompt": "Cuts: 0-4s ... sound on action: 轻柔液体声与水纹同步; 4-10s ... sound on action: 轻盈掠过声与高光切镜同步. ... AUDIO: VO=“已确认口播”; Voice=克制、成熟、温暖的普通话高级广告旁白，节奏从容; SonicIdea=水光被唤醒; Cues=使用上方逐节拍 sound-on-action | SFX 轻柔液体声与高光掠过声; Ambience=连续的安静高级影棚声床; Music=克制原创器乐; Mix=口播清楚，动作音效可听见，环境与配乐在人声下保持可感知。"
}
```

原生音轨能力允许在同一个请求里要求人声和非人声层，但不保证 Provider 一定遵守每一层。Skill 默认把声音保存为独立的 `sound_design_contract`：`layered_native` 要求声音大创意、逐节拍可见动作同步音、环境声、原创器乐、能量曲线和混音；`ambience_led` 只在创意明确不要配乐时使用，但仍要求 SFX 和环境声；`voice_only` 只适用于明确有人声的方案；`silent` 仅用于全静音投放。`no-speech` 通常仍使用 `layered_native` 或 `ambience_led`，只是禁止人物对白和旁白。关键音效必须对应画面动作或切镜，并直接出现在该时间节拍的 `sound on action` 中；唯一 `AUDIO` 区块汇总本片段标志音、环境、音乐与混音。验证器检查这些语义字段和覆盖率，不要求提示词包含固定警告口号。

每个视频生成请求都是独立音频上下文。多段广告必须在每个请求里重新写全具体乐器、节奏、质地、空间环境、标志音和混音，不得写“沿用上一段”或“same as previous”。这种自包含写法只能提高风格接近概率，不能保证独立片段拥有完全相同的旋律、音色或响度；精确连续配乐需要另行批准的本地后期混音。

Generic xAI generation documentation mentions Video Extension, but this project has not verified an extension request for Grok Imagine Video 1.5 R2V through MikuAPI. The route remains disabled for extension and must not add a continuation request to a paid plan.

Official R2V also defines optional `reference_audios` objects containing preset `voice_id` values, referenced as `<AUDIO_n>`. Use this only when the user explicitly selects a Provider preset and the configured route supports it. The default MikuAPI path does not require `/v1/tts/voices`, a preset ID, or `<AUDIO_0>`. A prompt with `<AUDIO_n>` but no matching payload is rejected. Neither prompt-native nor preset-conditioned speech guarantees frame-exact lip sync, and an output audio stream does not prove speech exists or is understandable. Every spoken output must therefore pass the local speech-only review before formal delivery.

Visible talent and voice are independent. The plan freezes `talent_presence` and optional presenter gender separately from `voice_gender`. Product-only prompts explicitly prohibit visible humans; an approved female/male presenter on the default R2V route requires a matching generated presenter reference. Prompt-native female/male voice direction must remain in the single `AUDIO` block and is checked after generation.

## Do Not Mix Modes

The same endpoint supports mutually exclusive modes:

- image-to-video: `prompt + image`; exactly one still becomes the starting frame;
- reference-to-video: `prompt + reference_images`; 1–7 images guide identity and style but do not become the starting frame;
- text-to-video: `prompt` only.

Never send `image` and `reference_images` together. Never send the SDK name `reference_image_urls` in this Skill's raw REST payload. Never substitute retired third-party fields such as `image_urls`, `input_reference`, or `seconds`.

## Responses and Polling

The create response supplies top-level `request_id`. Poll `GET /v1/videos/{request_id}` until:

- `pending`: keep polling the same request;
- `done`: download `video.url` promptly because result URLs are temporary;
- `failed` or `expired`: preserve the response and block the shot.

Never create an automatic replacement request.

## Readiness and Cost Safety

Before the first paid POST, call authenticated `GET /v1/models` through the same network route and confirm `grok-imagine-video-1.5` is visible. Prompt-native speech performs no voice-roster call. This free check proves only current credential, route and model visibility—not successful paid generation or intelligible speech.

Immediately before POST, rebuild the payload and compare it with `production-contract.json`. Verify:

- 1–7 exact `reference_images` objects and no `image` field;
- every reference has `generated_from_approved_visual_plan` provenance; the first is the generated professional product master, and no Provider reference has byte-hash overlap with raw evidence;
- storyboard/contact-sheet previews are absent from the payload;
- ordered file hashes match Stage 2 approval;
- the compiler-owned `<IMAGE_n>` tokens each appear exactly once and cover the same ordered references;
- prompt, duration, ratio, resolution, subtitle choice, and paid cap have not drifted.
- planned prompt-native speech has the approved dialogue/VO and voice delivery description in the single `AUDIO` block, with no `reference_audios` or `<AUDIO_n>`;
- every non-`voice_only` plan has a complete `sound on action` cue beside each planned visible beat, while the same request's `AUDIO` block links those cues and retains non-empty signature SFX, `Ambience`, the approved music policy and `Mix`;
- every independent request is self-contained and contains no cross-clip shorthand such as “same as previous” or “沿用上一段”;
- an explicitly selected optional preset has one matching `reference_audios` entry per ordered `<AUDIO_n>` token.

Record the attempt before sending. If the POST response is unknown or lacks `request_id`, keep the shot blocked and do not resubmit.

For `503 model_not_found` or `Upstream temporarily unavailable`, preserve the exact request and classify Provider routing/capacity trouble rather than an image-field failure. Model visibility is not generation proof; do not automatically resubmit.

## Preserved MikuAPI Single-Image Route

`grok_video_15` keeps the previously verified MikuAPI contract: one `image: {"url": ...}` first frame, no separate references, `duration` 1–15, and MikuAPI's dedicated key. It is an explicit compatibility option, not a fallback and not proof that MikuAPI supports xAI's new multi-reference mode.

The clean-video rule is unchanged: the Provider prompt and payload must not request subtitles, prices, CTA text, lower thirds, disclaimers, watermarks, or other new written elements. Add approved subtitles locally after reviewing the clean MP4.
