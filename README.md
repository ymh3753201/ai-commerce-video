# AI Commerce Video

[简体中文](README.zh-CN.md)

`ai-commerce-video` is an open-source Codex Skill for planning, generating, stitching, reviewing, and delivering AI e-commerce product videos.

The normal user can provide a product image plus a short request. Codex treats every upload as evidence, designs a professional 15-second commercial, then regenerates the complete Provider-facing Reference Pack from the approved plan. Its first slot is a faithful professional product master, never a raw/cropped/copied upload. Stage 1 approves the concept, route-aware time-coded storyboard, image prompts, Chinese audio plan, and final video prompt. Stage 2 `确认并生成` approves the exact ordered generated references and paid request count. Raw evidence and review-only storyboard grids never enter the default payload; separate clean full-frame beat keyframes may be used when composition guidance is needed.

The v8 director contract uses one category-agnostic product profile for any product, then chooses 1–4 duration-appropriate semantic beats. Its default campaign pack is product master + Hook keyframe + Proof/Payoff keyframe. Spoken R2V uses prompt-native speech and does not depend on a voice-list endpoint. Commercial sound remains professionally directed, while per-cue completeness and post-generation listening are advisory in the default workflow. Hard gates are limited to generated-asset isolation, legal payload/model fields, paid authorization and one-submit protection, frozen-contract integrity, and technical media delivery.

## What This Repository Contains

```text
ai-commerce-video/
├── SKILL.md                  # Codex workflow and hard safety rules
├── assets/templates/         # Example model, brief, env, and subtitle configs
├── evals/                    # Behavioral evaluation scenarios
├── references/               # Platform, creative, compliance, model, and editing guides
├── scripts/                  # Offline planning, guarded generation, review, and release tools
└── tests/                    # Offline regression and media-pipeline tests
```

Generated projects, user images, videos, request records, API keys, and local model files are intentionally excluded from the repository.

Do not put API keys in the repository. Do not commit generated videos or customer-provided product assets.

## Important Provider Notice

The bundled default `grok_video_15_reference` entry uses MikuAPI as a relay for the `grok-imagine-video-1.5` reference-to-video contract.

- The default route reads only `AI_COMMERCE_VIDEO_MIKUAPI_KEY` or macOS Keychain service `ai-commerce-video-mikuapi-video`.
- Raw REST uses 1–7 `reference_images` objects. `reference_image_urls` is the Python SDK parameter, not this Skill's REST field.
- Reference-to-video does not force the first frame, is capped at 720p, and must not be mixed with image-to-video field `image`.
- The optional `grok_video_15_reference_xai` entry keeps the same model contract through the official xAI endpoint and a separate `XAI_API_KEY`.
- The preserved `grok_video_15` entry keeps MikuAPI's one-`image.url` first-frame contract and reuses the MikuAPI credential. It is not an automatic fallback.
- The optional `grok_image_video` entry reads only `AI_COMMERCE_VIDEO_119337_KEY` or Keychain service `ai-commerce-video-119337-video`; it never reuses another Provider's key.
- Add a separate model-config entry and validate its complete payload contract before using another provider.
- Local references are sent as complete data URIs inside ordered `reference_images` objects. The Skill never buys a fallback-field retry.

Official xAI references:

- [Imagine Video 1.5 with References announcement](https://x.ai/news/grok-imagine-video-1-5-references)
- [xAI video generation documentation](https://docs.x.ai/developers/model-capabilities/video/generation)
- [xAI reference-to-video documentation](https://docs.x.ai/developers/model-capabilities/video/reference-to-video)

The optional `seedance2` example uses the fal queue API and requires a separate `FAL_KEY`.

## Currently Adapted Video Models

| Config key | Provider adapter | Provider model ID | Core capability |
|---|---|---|---|
| `grok_video_15_reference` | MikuAPI relay | `grok-imagine-video-1.5` | Default R2V with 1–7 images, native audio, 1–15 second request field, current reliable planning ceiling 10 seconds, maximum 720p |
| `grok_video_15_reference_xai` | Official xAI | `grok-imagine-video-1.5` | Optional direct reference-to-video route with the same visual contract |
| `grok_video_15` | MikuAPI | `grok-imagine-video-1.5` | Preserved single-first-frame compatibility route |
| `grok_image_video` | Third-party `119337` | `grok-image-video` | Text/single-image video up to 15 seconds; up to 7 references with a 10-second multi-reference limit |
| `seedance2` | fal queue | `bytedance/seedance-2.0/reference-to-video` | Reference-to-video with up to 9 images, native audio, up to 15 seconds |

The working contract is the complete combination of provider host, endpoint, authentication, payload fields, model ID, duration slots, image limits, polling response, audio behavior, and prompt limits. A matching or similar model name does not prove API compatibility.

## Adapting Another Video Model

Do not replace only the model name or base URL. Add a separate model entry and update the Skill when capabilities differ:

1. Define provider host, create/poll/result endpoints, authentication scheme, and dedicated key-variable names.
2. Define text, source-image, multi-reference, duration, aspect-ratio, resolution, audio, speech, and lip-sync capabilities.
3. Define exact payload field names and response-normalization behavior.
4. Define legal duration slots, reference-image limits, and prompt limits.
5. Update planning and reference-strategy rules when the model has different continuity or image behavior.
6. Add dry-run payload tests, mocked submit/poll tests, prompt-budget tests, and no-key preflight tests.
7. Re-run the release audit and complete offline suite before publishing the adapter.

## Requirements

- Codex with multimodal image understanding and `imagegen`
- Python 3.10+
- macOS or Linux
- FFmpeg and ffprobe for media review, stitching, and subtitle burning
- A separately configured video-provider account only when paid generation is requested

No third-party Python packages are required by the bundled scripts.

## Project-local use

Keep this repository in the current workspace and attach or reference its `SKILL.md` path directly in the Codex request. A separate global copy is not required:

```text
Use the ai-commerce-video Skill from the current project's SKILL.md.
```

## Safe Production Flow

1. Codex analyzes the user's request and product materials.
2. Codex selects one recommended direction and keeps one concise alternative available for revision.
3. Codex shows Stage 1 with the visual system, 15-second storyboard/script, motivated cuts, reference roles, image prompts, and video-prompt blueprint.
4. After creative approval, Codex groups all trustworthy same-SKU views into one ordered product identity evidence set, passes that complete set together to every product-dependent imagegen call, and generates the Reference Pack beginning with a faithful professional product master. Person, scene, or style inputs are added only to controls that need them; every upload remains evidence and every storyboard/contact sheet remains review-only. The scripts record the exact imagegen input IDs, paths and hashes, then preflight the request without video cost.
5. Codex shows Stage 2 with the actual ordered `<IMAGE_n>` set and exact paid request count.
6. The user replies `确认并生成`, or gives an equally clear instruction while viewing that exact set.
7. The first submit performs a no-cost same-route model-visibility check. Prompt-native speech does not call a separate voice-roster endpoint. Network, regional-access, or model-visibility failure creates no video task, preserves the same confirmation, and does not require the user to confirm again after recovery.
8. Each planned shot is submitted once and resumed by request ID; no separate script, preflight, or payment confirmation is requested.
9. Clean video is stitched only at planned complete-action and complete-sentence boundaries, then technically checked. Detailed visual and listening review remains available without becoming a mandatory third gate.
10. Optional subtitles are generated from the finished audio and burned locally after clean-video acceptance.

The video model must not generate subtitles, CTA text, prices, watermarks, or other written overlays.

Bundled Grok prompts use `director-commerce-v8`, architecture `universal-product-director-v4`, and plan schema v3. A route-legal request carries exactly one `Cuts` montage or one `Sequence` timeline, one compact canonical reference map when needed, a product/fact lock, and one final `AUDIO` block. Incomplete sound coverage is reported as an advisory warning. Official xAI documents a 15-second R2V maximum; the current MikuAPI relay uses a 10-second reliable planning ceiling, so a 15-second delivery is planned as `10+5` with two approved requests. Technical media checks and `delivery-manifest.json.status=pass` remain required; detailed business listening is optional for new default plans.

## Private Configuration

Create the local private env file:

```bash
python3 scripts/setup_private_env.py
```

If this Provider must use an existing local proxy, configure it for this Skill only:

```bash
python3 scripts/setup_private_env.py --proxy-url http://127.0.0.1:7897
```

This records the route in the private env file. It does not change Clash or system proxy settings.

It writes `~/.codex/ai-commerce-video.env` with file mode `0600`. Never commit or package this file.
Configuration validation reports only whether a key exists; it never prints a key preview.

Review and adapt:

```text
assets/templates/model-config.example.json
```

Provider model IDs, endpoints, duration slots, image fields, and response formats are provider contracts. A model name alone does not prove compatibility.

## Test

Run the complete offline suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
```

Some media tests are skipped when FFmpeg is unavailable.

## Audit and Package

Run the release audit:

```bash
python3 scripts/audit_release.py
```

Build a deterministic `.skill` archive:

```bash
python3 scripts/package_skill.py --output dist/ai-commerce-video.skill
```

The package excludes repository-only documentation, tests, CI files, private env files, caches, generated projects, and release tooling.

## Scope and Limitations

- The default production design is a 15-second product ad.
- Every category shares one evidence-led director and prompt architecture; structured product form, interaction and proof dimensions adapt the creative without category-keyword templates.
- Multi-request videos allocate complete semantic beats to route-legal clips and stitch them as planned cuts with explicit visual and audio boundary review.
- Successful stitching does not guarantee seamless character, lip, voice, or motion continuity across separately generated clips.
- A third-party gateway may not return an image-receipt fingerprint. In that case the Skill can prove what it sent, but not that the upstream bound the image correctly; unrelated output must remain blocked and be escalated with the stored task evidence.
- Platform and advertising rules in this repository are planning snapshots. Recheck current platform policy before publishing a real campaign.
- Compliance guidance is not legal advice.

## License

MIT. See [LICENSE](LICENSE).
