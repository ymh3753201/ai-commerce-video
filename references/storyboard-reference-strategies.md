# Storyboard Reference Strategies

Use this reference when an ad has scene changes, multiple story beats, or a storyboard sheet.

## Strategy IDs

| ID | Use when | Model fit |
|---|---|---|
| `single_source_frame` | One continuous scene or simple product/presenter motion | Any image-to-video model |
| `per_segment_source_frames` | Single-image model, but the ad needs multiple scenes or story beats | `grok-video-1.5` and other one-image routes |
| `storyboard_sheet_reference` | A multi-reference model can upload a storyboard sheet as one reference | Seedance-style and other multi-reference routes |
| `multi_reference_storyboard` | Product, presenter, scene, and storyboard are all uploaded as references | Seedance 2.0, `grok-image-video`, or future multi-reference models |

## Decision Rules

- If the ad is one continuous shot, use `single_source_frame`: generate one final approved `video_source` / first-frame image.
- If the selected model has `supports_multiple_references: false` and the ad needs scene changes, use `per_segment_source_frames`: generate one approved source/first-frame image per segment, then stitch the clips.
- If the selected model supports multiple references and the storyboard should influence generation, use `storyboard_sheet_reference` or `multi_reference_storyboard`.
- Never upload a 6-grid or 9-grid storyboard sheet as the only source image for a single-image model. The model may animate the collage itself instead of interpreting it as a shot plan.
- A storyboard sheet used as a video reference must be described as a rhythm/order guide, not as the literal output frame.

## Grok 1.5 Pattern

For `grok-video-1.5`, use separate segment source frames when the ad needs multiple scenes:

```bash
python3 ai-commerce-video/scripts/prepare_project.py \
  --name camping-lamp-story-ad \
  --product-image product.png \
  --model-key grok_video_15 \
  --reference-strategy per_segment_source_frames \
  --segment-source-image shot_01=shot-01-hook.png \
  --segment-source-image shot_02=shot-02-solution.png \
  --segment-source-image shot_03=shot-03-cta.png \
  --duration 15
```

This creates three 5-second shots for a 15-second ad. Generate each shot with `generate_video.py`, then stitch with `stitch_clips.py`.

## Seedance / Multi-Reference Pattern

For Seedance 2.0 or another multi-reference route, upload the storyboard sheet together with identity references:

```text
Reference image map: @Image1 = product reference; @Image2 = presenter reference; @Image3 = 6-panel storyboard reference.
Use @Image3 only as shot order and rhythm guidance. Render a full-screen vertical video. Do not reproduce the grid layout, panel borders, labels, or collage format.
```

Use the storyboard to guide sequence and timing; use product and presenter references to preserve identity.
