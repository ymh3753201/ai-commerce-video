# Model Capabilities

This Skill is model-config driven. Model name, provider, route, input mode, image field, duration, resolution, response shape, key, and billing guard form one contract. Never switch a provider by changing only a name or URL.

Official xAI sources checked on 2026-08-23:

- https://x.ai/news/grok-imagine-video-1-5-references
- https://docs.x.ai/developers/model-capabilities/video/generation
- https://docs.x.ai/developers/model-capabilities/video/reference-to-video
- https://docs.x.ai/developers/model-capabilities/video/image-to-video
- https://docs.x.ai/developers/model-capabilities/audio/text-to-speech

## Capability Table

| Config key | Provider | Mode | Images | Duration | Resolution | Main use |
|---|---|---|---:|---:|---|---|
| `grok_video_15_reference` | MikuAPI relay | reference-to-video | 1–7 | accepts 1–15s; reliable planning ceiling currently 10s | 480p/720p | Default professional ads using an all-generated Reference Pack with a faithful product master first |
| `grok_video_15_reference_xai` | official xAI | reference-to-video | 1–7 | 1–15s | 480p/720p | Optional direct route using the same model and visual contract |
| `grok_video_15` | MikuAPI relay | image-to-video | exactly 1 first frame | 1–15s | 480p/720p | Preserved legacy workflow when one approved composite first frame is sufficient |
| `grok_image_video` | third-party 119337 | provider-specific image/video | up to 7 | 15s single, 10s multi | 480p/720p | Optional legacy provider route; keep its aliases isolated |
| `seedance2` | fal queue | reference-to-video | up to 9 | up to 15s | configured provider limits | Optional Seedance storyboard workflow |

Reference-to-video on `grok-imagine-video-1.5` supports up to 15 seconds but is capped at 720p. Native 1080p applies to xAI text-to-video and image-to-video, not reference-to-video.

Official model capability and route verification are separate layers. Official xAI capability includes 1–7 `reference_images`, optional preset `reference_audios` entries with `<AUDIO_n>` tokens, a maximum 15-second duration, and an output audio track. Ordinary Skill speech uses dialogue/VO plus natural-language delivery direction in the prompt and does not require preset audio references. The same prompt-native audio block also requests action-synced SFX, scene ambience, an optional original instrumental score, and mix priority. Two saved MikuAPI paid outputs requested 15 seconds but returned about 10.042 seconds, so that relay now keeps the official/request maximum of 15 seconds but uses 10 seconds as its verified reliable planning ceiling. This is route evidence, not a claim that the official model is limited to 10 seconds. An audio track alone proves neither intelligible speech nor the requested non-speech layers.

## Capability Evidence Layers

| Layer | What it proves | What it does not prove |
|---|---|---|
| Official xAI capability | field names, reference limits, preset-voice conditioning, duration and resolution | that a relay exposes every feature correctly |
| Static route configuration | payload builder, optional preset allowlist and offline limits | that an optional preset works through a relay |
| Free same-route readiness | current credential/network can see the video model through `GET /v1/models` | that a paid generation will produce intelligible speech |
| Optional voice diagnostic | a route happens to expose `GET /v1/tts/voices` | required availability for prompt-native speech |
| Real output review | actual duration, image adherence, speech clarity, audible SFX/ambience/music and selling meaning | general compatibility beyond that saved task |

Preset voice input is `voice-conditioned speech`: it guides the native voice produced with the video. It is not a contract for phoneme-exact or frame-exact lip sync. A visible talking presenter may be directed, but exact mouth timing must never be promised. The model's native-audio capability and the relay's model visibility do not prove that a particular output contains the requested voice state. Every new non-silent delivery therefore needs one output-bound voice-contract check: required speech and presentation for spoken plans, or absence of unplanned human speech for `no-speech`. This is a post-generation check, not a preflight or paid gate.

## xAI Mode Boundary

- Image-to-video: raw REST field `image`; exactly one still becomes the first frame.
- Reference-to-video: raw REST field `reference_images`; 1–7 images guide identity and style but do not force the first frame.
- Python SDK: the equivalent reference argument is `reference_image_urls`.
- Raw REST requests must never mix `image` with `reference_images`.

The default MikuAPI `grok_video_15_reference` route and optional official `grok_video_15_reference_xai` route both use `reference_images` objects. The current adapter binds zero-based tags `<IMAGE_0>`…`<IMAGE_6>` from payload order. xAI's documentation currently contains both a zero-based token statement and a one-based-looking example, so numbering is recorded as a route contract with `reference_index_contract_source`, not presented as a universal official fact. The preserved `grok_video_15` MikuAPI route uses one `image.url` object and no multi-reference payload.

Generic xAI video documentation describes Video Extension, but this Skill has not verified an extension contract for Grok Imagine Video 1.5 Reference-to-Video through MikuAPI. `supports_video_extension=false` therefore keeps extension out of production planning; do not infer support from the generic feature page or add a paid continuation request.

## Planning Rules

- Prefer the default MikuAPI relay route when its 10-second reliable planning units and exact paid count suit the project. A 15-second delivery currently becomes `10+5`. Select `grok_video_15_reference_xai` only when the user intentionally wants the official direct endpoint, has configured its separate key, and approves its separate route contract.
- Treat seven as a ceiling. Prefer product master + Hook keyframe + Proof/Payoff keyframe, then add a single-purpose identity, scene, or action control only when needed.
- Treat every supplied product/person/scene/detail image as evidence only. Generate `<IMAGE_0>` as the faithful professional product master, then generate only necessary later single-purpose controls.
- Add `product_detail` only when a second view, texture, label, mechanism, interface, or control must be accurate.
- Add `presenter` and optionally `wardrobe` when a visible seller is useful. Add `scene` for spatial and lighting consistency. Add `style` only for finish.
- Freeze `talent_presence` separately from `voice_gender`. Product-only means explicitly no visible human; hands-only forbids a face/body/presenter; a visible female/male presenter requires a matching generated presenter control on the default R2V route and a no-gender-substitution instruction.
- A storyboard/contact sheet is a human-review preview, not an element reference on the default multi-reference route. For exact shot-start control, use separately approved per-segment Image-to-Video keyframes.
- Use the preserved Miku single-image route only when one approved first frame genuinely contains everything needed. For multiple legacy clips, use approved `per_segment_source_frames` and stitch.
- The optional 119337 adapter uses only `AI_COMMERCE_VIDEO_119337_KEY` or its dedicated Keychain service. Never reuse a MikuAPI, xAI, Yunwu, or generic gateway credential for that host.
- Follow each optional provider's own reference field, prompt-token convention, durations, authentication, and response mapping.

## Prompt Compiler

Director compiler `director-commerce-v10` and architecture `universal-product-director-v6` use one category-agnostic product director profile plus proposition, audience tension, visual proof, big idea, emotional arc, talent role and sound strategy. Stage 1 first freezes on-camera speech, off-screen voiceover, or no human speech; presenter presence does not override that decision. The compiler sends one compact `Cuts` timeline for montage or one `Sequence` timeline for a continuous shot, the visual direction, concise strategy/proof, canonical compact reference map, product/fact lock, and exactly one final `AUDIO` block. On-camera speech requires `Dialogue=` plus visible speaking and natural mouth movement; off-screen narration requires `VO=` and an off-screen direction; `no-speech` requires `Speech=none; Voice=none` while retaining approved SFX, ambience, and music. Contradictory mode, presentation, or script contracts are rejected before preflight. Every timeline beat contains its complete synchronized sound-on-action cue; the AUDIO block links those cues and preserves the clip's signature SFX, ambience, music and mix. Planning, compliance, image QC, and billing detail remains in JSON. Freeform input cannot own `Cuts`, `Sequence`, `Reference image map`, `AUDIO`, or manual image-token bindings.

For xAI reference-to-video, write a compact time-coded prompt that:

1. lets the compiler assign every `<IMAGE_n>` exactly one role from frozen payload order; freeform prompts must not contain manual image tokens;
2. maps 1–4 duration-appropriate, semantically complete commercial beats into each route-legal request; use one 15-second request only on a route whose reliable planning ceiling is 15 seconds;
3. records commercial job, entry/action/exit state, framing, one dominant camera move, focus, light/physical response and a motivated edit; independent requests never share fragments of the same action;
4. includes approved dialogue exactly once for a spoken plan, or `Speech=none; Voice=none` for `no-speech`;
5. preserves product facts and forbids newly generated written elements.

Sound design and human voice are separate. `layered_native` is the normal commercial default and requests a sonic idea, time-aligned visible-action cues, ambience, restrained original instrumental music, an energy curve and mix hierarchy. `ambience_led` is an intentional no-music direction; `voice_only` is valid only for a spoken plan; `silent` is reserved for a fully silent placement. A `no-speech` plan normally remains `layered_native` or `ambience_led`: it forbids human speech without deleting the commercial soundscape. The compiler keeps timed cues beside visible actions and uses one `AUDIO` block for clip-level sound identity and mix. Validators report incomplete cue coverage or cross-request shorthand such as “same as previous” or “沿用上一段” as advisory findings. Optional post-generation listening can record the actual layers and balance.

Native audio generation is prompt-directed best-effort, not a guaranteed layer renderer. Independent video requests share no audio state, so each clip must restate the same concrete sonic fingerprint instead of referring to a previous clip. This may create a coherent edit, but it cannot guarantee identical melody, timbre, loudness, or room tone. Exact score continuity requires a separately approved local post-production music/mix layer.

When approved speech exists, the default plan uses `voice_policy=prompt_native`, keeps `preset_voice_ids=[]`, sends no `reference_audios`, and writes the dialogue/VO plus voice delivery description exactly once in `AUDIO`. “人物口播” selects on-camera `Dialogue` only when it is the approved Stage 1 choice; `voiceover` remains detached narration. A Provider preset is optional only after an explicit user choice and approved spoken copy; then the payload may send `reference_audios` and matching `<AUDIO_n>` tokens. `/v1/tts/voices` is diagnostic information, not a paid-submission gate for prompt-native speech. The generated output must still pass the narrow voice-contract review.

No xAI source checked by this project publishes a universal 4096-character video-prompt maximum. `provider_documented_max_prompt_chars=null`, `adapter_max_prompt_chars=4096`, and `workflow_prompt_budget_chars=3000` separate official evidence from internal protection. Legacy `max_prompt_chars` and `prompt_budget_chars` remain compatibility aliases. Rewrite the visual direction or simplify the reference set when required content does not fit the internal route budget; never truncate approved dialogue or identity rules. For 11–15 second ads, 1300–2400 characters is a useful internal target rather than a hard requirement. The compiler reports creative/reference/guardrail/audio ratios so a long reference map or policy block cannot silently crowd out directing information.

## Duration and Paid Count

Use only configured legal durations and the selected route's `planning_max_duration_seconds`. For the current MikuAPI R2V route, 15 seconds is `10+5`; for official xAI R2V, the documented 15-second capability remains one request. Longer deliveries use the minimum legal request count and local stitching for that route. Examples on official xAI:

- 25s: `15+10`;
- 30s: `15+15`;
- 45s: `15+15+15`.

Every planned request is submitted once. Repair reserve and automatic replacement requests remain zero. A single R2V request can follow time-coded beats, but its cut points remain generative rather than frame-exact. Independent clips used for longer deliveries can be edited coherently but cannot be promised as a seamless one-take or a shared native audio session. Each semantic beat belongs to one request; every clip restates the full sonic fingerprint, and edit boundaries carry a stable exit, continuity entry, cut motivation and audio bridge, followed by visual, sound-continuity and loudness review after stitching.

## Model Choice

- Default: `grok_video_15_reference` for MikuAPI-relayed 1–7 image reference-to-video.
- Optional direct: `grok_video_15_reference_xai` for the same model contract through official xAI.
- Compatibility: `grok_video_15` for the verified MikuAPI single-first-frame contract.
- Optional third-party: use `grok_image_video` or `seedance2` only when explicitly selected and configured.
- If a real identifiable person is requested, require clear permission; prefer synthetic presenters by default.
