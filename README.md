# AI Commerce Video

[简体中文](README.zh-CN.md)

`ai-commerce-video` is an open-source Codex Skill for planning, generating, stitching, reviewing, and delivering AI e-commerce product videos.

The normal user can provide a product image plus a short request. Codex performs multimodal product analysis, proposes a platform-aware advertising plan, generates approval images, prepares no-cost request previews, and only calls a paid video API after two explicit confirmations.

The normal production path uses a two-step approval flow: approve the plan first, then approve the actual generated image set.

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

The bundled default `grok_video_15` entry is an adapter for the third-party `119337` gateway. It is not an xAI-operated endpoint.

- Never send an xAI API key to a third-party gateway unless you independently trust that provider.
- The bundled third-party model entries intentionally do not read `XAI_API_KEY`; use a provider-specific `AI_COMMERCE_VIDEO_API_KEY` or `YUNWU_API_KEY`.
- The official xAI API uses a different request and polling schema. Do not change only the base URL from `api.119337.xyz` to `api.x.ai`.
- Add a separate model-config entry and validate its complete payload contract before using another provider.

Official xAI references:

- [Grok Imagine Video 1.5 announcement](https://x.ai/news/grok-imagine-video-1-5)
- [xAI video generation documentation](https://docs.x.ai/developers/model-capabilities/video/generation)

The optional `seedance2` example uses the fal queue API and requires a separate `FAL_KEY`.

## Currently Adapted Video Models

| Config key | Provider adapter | Provider model ID | Core capability |
|---|---|---|---|
| `grok_video_15` | Third-party `119337` | `grok-video-1.5` | Single-image image-to-video, native audio/speech, up to 15 seconds; mapped to the `grok-imagine-video-1.5` model family |
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

## Install

Copy this repository folder into the Codex skills directory:

```bash
rsync -a --delete --exclude '.git/' ./ ~/.codex/skills/ai-commerce-video/
```

Then invoke the Skill in Codex with `$ai-commerce-video`.

## Safe Production Flow

1. Codex analyzes the user's request and product materials.
2. Codex presents one recommended advertising plan and one concise alternative.
3. The user confirms the creative and image plan.
4. Codex generates approval images with its native image tool.
5. The user confirms the actual local images.
6. The scripts prepare and preflight exact provider requests without cost.
7. The user separately confirms paid generation.
8. Each planned shot is submitted once and resumed by request ID.
9. Clean video is stitched and reviewed.
10. Optional subtitles are generated and burned locally after clean-video acceptance.

The video model must not generate subtitles, CTA text, prices, watermarks, or other written overlays.

## Private Configuration

Create the local private env file:

```bash
python3 scripts/setup_private_env.py
```

It writes `~/.codex/ai-commerce-video.env` with file mode `0600`. Never commit or package this file.

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
- Longer videos are split into legal provider durations and stitched as planned cuts.
- Successful stitching does not guarantee seamless character, lip, voice, or motion continuity across separately generated clips.
- Platform and advertising rules in this repository are planning snapshots. Recheck current platform policy before publishing a real campaign.
- Compliance guidance is not legal advice.

## License

MIT. See [LICENSE](LICENSE).
