# Storyboard Reference Strategies

Use this reference when an ad has scene changes, multiple story beats, or a storyboard/contact sheet.

## Strategy IDs

| ID | Use when | Model fit |
|---|---|---|
| `multi_reference_commercial` | An all-generated Reference Pack with product master first, element controls and optional clean beat keyframes guides one time-coded request up to 15s | Default MikuAPI-relayed `grok-imagine-video-1.5` Reference-to-Video |
| `single_source_frame` | One continuous scene or simple product/presenter motion | Legacy Image-to-Video |
| `per_segment_source_frames` | Exact opening composition matters for several shots | Image-to-Video with one generated keyframe and one paid request per segment |
| `storyboard_sheet_reference` | A non-default Provider explicitly documents storyboard-sheet input | Provider-specific only; disabled for the default Grok route |
| `multi_reference_storyboard` | A non-default Provider explicitly supports element controls plus storyboard guidance | Provider-specific only; disabled for the default Grok route |

## Default MikuAPI Grok Decision

For the default MikuAPI relay route using the xAI-compatible Grok contract:

1. Every user-uploaded product/detail/person/scene image is evidence only and never a Provider reference.
2. Stage 1 designs the 15-second commercial, edit rhythm, generated control portfolio, one image prompt per control and the final video-prompt blueprint.
3. After approval, generate the complete Reference Pack: a faithful professional `product` master first, then only the necessary `presenter`, `wardrobe`, `scene`, `hand_action`, `product_detail`, `prop`, `style`, or uniquely named clean `beat_keyframe_*` controls.
4. Generate a storyboard/contact sheet separately when it helps the user review the edit. Mark it `review_only`; never include the grid in `reference_images`. If one beat needs stronger composition control, generate that beat as its own clean full-screen keyframe and upload it as a later reference slot.
5. Let the prompt compiler append the canonical `<IMAGE_n>` map from actual upload order. Never hand-write a competing token map in the visual prompt.

Reference images guide people, objects, clothing, locations, actions and look without becoming the first frame. Choose request count from the route's reliable planning ceiling: current MikuAPI R2V plans 15 seconds as `10+5`, while official xAI R2V documents one 15-second request. Use 1–4 duration-appropriate complete semantic beats per request and motivated transitions. Treat requested cut points as directing guidance, not a frame-exact guarantee.

For multi-request delivery, assign every complete beat to one request and reflow its local seconds. Never duplicate an overlapping action fragment across adjacent prompts. Store edit-safe exit/entry states, cut motivation and an ambience/score bridge for each boundary.

## Exact-Keyframe Route

Use `per_segment_source_frames` when exact framing or cut starts matter more than one-request simplicity:

- design the storyboard first;
- generate one clean 9:16 keyframe per segment from that storyboard and the same factual evidence;
- show every keyframe in Stage 2;
- submit one Image-to-Video request per segment;
- disclose and approve the exact higher paid count;
- normalize and stitch the returned clips.

Never upload a 6-grid or 9-grid storyboard as the only source frame. The model may animate the grid instead of interpreting it as an edit plan.

## Default Reference-to-Video Example

```bash
python3 ai-commerce-video/scripts/prepare_project.py \
  --name camping-lamp-story-ad \
  --product-image raw-product-evidence.png \
  --reference-image product_detail=raw-detail-evidence.png \
  --brief approved-visual-brief.json \
  --model-key grok_video_15_reference \
  --reference-strategy multi_reference_commercial \
  --generated-reference product=generated-professional-product-master.png \
  --generated-reference presenter=generated-presenter-control.png \
  --generated-reference scene=generated-scene-control.png \
  --storyboard-preview-image generated-storyboard-review.png \
  --duration 15
```

The generated professional product master becomes `<IMAGE_0>`. Every raw product/detail file remains evidence; generated presenter and scene controls enter later slots. The storyboard is visible to the user but remains outside the payload.

Use the preserved `grok_video_15` Image-to-Video route only when its separately configured Provider contract is selected. Example: `--reference-strategy per_segment_source_frames --segment-source-image shot_01=hook.png --segment-source-image shot_02=proof.png`.

## Other Providers

Do not infer that a multi-panel grid is understood as an edit timeline merely because multiple reference images are supported. The default Grok route accepts separate clean full-frame beat keyframes as ordinary references, while the prompt carries the timing and transition plan. Keep model fields, prompt tokens, duration limits, dry-run tests and paid-count confirmation isolated per Provider.
