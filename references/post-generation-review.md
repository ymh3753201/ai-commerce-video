# Post-Generation Review

Use this reference after every generated clip is downloaded. A playable MP4 is not yet an accepted commerce deliverable.

## 1. Clip and Job Review

- Every planned shot has one verified job and exactly one paid submission attempt.
- Every expected clip exists, passes ffprobe, and matches its request ID and SHA-256 record.
- No shot is silently replaced, skipped, or resubmitted.

## 2. Clean Technical Review

- Final duration stays within `delivery_max_seconds` plus the small probe tolerance.
- Resolution, aspect ratio, frame rate, codecs, and audio stream match the delivery plan.
- Multi-clip output has a stitch report proving PCM intermediate audio, no per-clip fade, no crossfade, and one final AAC encode.
- Inspect reported silence and freeze regions, especially around every clip boundary.
- Spoken sentences are complete at each boundary; no syllable, number, unit, or CTA is cut.

## 3. Clean Multimodal Business Review

Codex must inspect the clean video and record:

- `video_sha256` matching the exact clean MP4 reviewed;
- approved product identity is preserved;
- packaging, label, logo, color, shape, and key details have not drifted;
- no accidental generated text appears anywhere;
- no unapproved person, object, product variant, scene, or visual claim appears;
- spoken content is complete and understandable;
- price, offer, SKU, specifications, claims, disclaimer needs, and CTA are exact;
- platform framing and product exposure support conversion.

Do not approve a clean output merely because it can play.

## 4. Caption Review

When subtitles are enabled, review the clean master first, then the separately burned captioned video using `subtitles-and-safe-layout.md`. Keep both artifacts and reviews distinct.

## 5. Final Delivery Gate

`finalize_project.py` may write `delivery-manifest.json` with `status=pass` only when:

- job count and paid cap match the approved base plan;
- current plan, duration plan, paid job ledger, and final confirmation still match the frozen production-contract digests;
- every job is verified with exactly one paid submission;
- clean technical review passes;
- clean multimodal business review passes;
- caption review passes when subtitles are enabled;
- technical, clean-visual, and optional caption reviews are bound to the exact clean/captioned MP4 SHA-256 values;
- the chosen final MP4 exists and has a recorded hash.

If any item fails, keep `finalize-report.json.status=blocked`; do not claim final delivery and do not automatically purchase a repair generation.
