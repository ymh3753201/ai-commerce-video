# Post-Generation Review

Use this reference after every generated clip is downloaded. A playable MP4 is not yet an accepted commerce deliverable.

## 1. Clip and Job Review

- Every planned shot has one verified job and exactly one paid submission attempt.
- Every expected clip exists, passes ffprobe, and matches its request ID and SHA-256 record.
- No shot is silently replaced, skipped, or resubmitted.
- `provider_trace` records gateway/upstream task IDs, channel ID when available, returned-prompt match, input receipt status, and downloaded video hash.

## 2. Clean Technical Review

`review_render.py` writes a legacy top-level `status` for compatibility, but its scope is explicitly `review_scope=technical_media_only`. New default plans report `delivery_status=technical_ready` after required media checks; legacy strict plans report `pending_business_review`. `finalize_project.py` remains responsible for the delivery manifest.

- Final duration stays within `delivery_max_seconds` plus the small probe tolerance.
- Compare each downloaded Provider clip with its approved request duration. A shortfall over one second blocks delivery; do not extend a 5–10 second result to 15 seconds with a long frozen last frame. The only normal end hold is about one second.
- Resolution, aspect ratio, frame rate, codecs, and audio stream match the delivery plan.
- Multi-clip output has a stitch report proving PCM intermediate audio, no per-clip fade, no crossfade, and one final AAC encode.
- Inspect reported silence and freeze regions, especially around every clip boundary.
- Spoken sentences are complete at each boundary; no syllable, number, unit, or CTA is cut.

The report's `sound_signal_screening` is a no-cost warning based on detected silence and the plan's expected continuous sound bed. It can flag `QC_SOUND_DESIGN_MISSING` as a candidate when long silence conflicts with the plan, but it is not speech recognition, source separation, or a listening verdict. It must never turn `planned_sfx_audible`, `planned_ambience_audible`, `planned_music_audible`, or `audio_mix_balanced` true by itself.

## 3. Optional Clean Multimodal Business Review

Use these practical fields when the user requests a detailed creative review or Codex observes a clear problem:

- `video_sha256` matching the exact clean MP4 reviewed;
- `video_complete_and_coherent=true`: all planned segments are present and joins feel reasonable;
- `source_frame_consistency=true`: the output broadly follows the approved source/reference images;
- `approved_product_identity=true`: the intended product remains recognizable;
- for `talent_presence=none`, `unexpected_person_absent=true`: no person, face, body, hand, or human silhouette appears;
- for `talent_presence=hands_only`, `hands_only_boundary_preserved=true` and `unexpected_presenter_absent=true`;
- `presenter_identity_consistency=true` and `presenter_outfit_consistency=true` when a presenter is used;
- `talent_presence_matches_plan=true`, and `talent_gender_matches_plan=true` when female/male presenter gender was explicitly approved;
- `scene_composition_consistency=true`: scene and framing broadly match the approved reference/storyboard;
- when speech was planned, `speech_intelligible=true`: an effective speech interval exists and local transcription or human listening confirms it is understandable;
- when speech was planned, `speech_meaning_preserved=true`: the main selling meaning is approximately preserved.
- when female/male voice direction was explicit, `voice_gender_matches_plan=true`.

An AAC stream, music, ambience, or sound effects do not prove speech. Record clear speech problems as notes or an optional business-review failure. New default projects do not convert this optional review into a third mandatory approval gate or automatic paid retry.

Speech and non-speech sound are separate observations. When doing the optional review, record `planned_sfx_audible`, `planned_ambience_audible`, optional `planned_music_audible`, `non_speech_sound_supports_story`, and `audio_mix_balanced`. The presence of an AAC stream cannot set these fields to true. Missing layers may use `QC_SOUND_DESIGN_MISSING`; an unusable balance may use `QC_AUDIO_MIX_FAILURE`. These findings never authorize an automatic paid retry.

Do not require word-for-word script reproduction. Packaging lettering, incidental generated text, exact price/offer/CTA/disclaimer wording, silence/freeze detections, or minor visual/timing changes are review notes unless they make the video incomplete, incoherent, misleading, or unusable.

`jobs.json.state=verified` means the Provider clip passed technical media verification. New default projects then run `review_render.py` and move from `awaiting_technical_review` to `ready_to_finalize`; only legacy strict plans wait in `awaiting_business_review`.

## 4. Caption Review

When subtitles are enabled, review the clean master first, then the separately burned captioned video using `subtitles-and-safe-layout.md`. Keep both artifacts and reviews distinct.

## 5. Final Delivery Gate

For new default projects, `finalize_project.py` may write `delivery-manifest.json` with `status=pass` when:

- job count and paid cap match the approved base plan;
- current plan, duration plan, paid job ledger, and final confirmation still match the frozen production-contract digests;
- every job is verified with exactly one paid submission;
- clean technical review passes;
- every Provider clip is within the allowed one-second duration shortfall;
- caption review passes when subtitles are enabled;
- technical and optional caption reviews are bound to the exact clean/captioned MP4 SHA-256 values;
- the chosen final MP4 exists and has a recorded hash.

Legacy plans without `quality_contract.delivery_review_policy=technical_ready` keep the former strict business-review requirements for backward compatibility. An optional visual/listening report can still be saved on a new plan and appears as warnings rather than a delivery block.

If any item fails, keep `finalize-report.json.status=blocked`; do not claim final delivery and do not automatically purchase a repair generation.

## 6. Failure Codes and Minimum Repair Scope

Record one or more explicit codes instead of writing only “画面不好”：

| Code | Failure | Minimum repair target |
|---|---|---|
| `QC_PRODUCT_DRIFT` | Product geometry, color, packaging, logo, or marks drift | clean/replace the product anchor or regenerate only the affected clip |
| `QC_CAMERA_MOVE_CONFLICT` | A clip contains competing main camera moves or motion confusion | rewrite and regenerate only that clip |
| `QC_REFERENCE_CONTAMINATION` | Grid, arrows, labels, duplicate subjects, or polluted reference content appears | regenerate the polluted support plate and affected clip |
| `QC_SPEECH_OVERRUN` | Dialogue runs past the clip, clips a word, or crosses a cut | shorten/re-time that clip's script and AUDIO block |
| `QC_HAND_ANATOMY` | Extra/fused fingers or hand-product intersection | replace the hand-action plate and affected clip |
| `QC_CTA_UNREADABLE` | Local CTA is unreadable or outside the safe zone | redo local packaging only; do not regenerate video |
| `QC_DURATION_SHORTFALL` | Provider clip is over one second shorter than approved | block delivery; never use long frozen padding |
| `QC_SPEECH_MISSING` | Planned speech is missing, unintelligible, or loses selling meaning | record an optional business-review note and preserve evidence |
| `QC_TALENT_MISMATCH` | An unexpected human appears, presenter is missing, or approved presenter gender changes | record an optional business-review note and inspect references |
| `QC_VOICE_GENDER_MISMATCH` | Explicit female/male voice direction changes | record an optional business-review note and inspect `AUDIO` |
| `QC_SOUND_DESIGN_MISSING` | Planned SFX, ambience, or music is absent or inaudible | record an optional business-review note and preserve evidence |
| `QC_AUDIO_MIX_FAILURE` | Voice masks the whole soundscape or the soundscape masks speech | record an optional business-review note and inspect the mix |

The code identifies scope; it never authorizes a paid retry. Preserve passed clips and request new paid authorization only for the smallest failed generation unit.
