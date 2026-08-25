# Composition And Stitching

Use this reference when the video has more than one generated clip.

## Reused Design Sources

- OpenMontage `video_stitch`: probe clips first, detect mismatches, normalize when needed, and validate outputs with ffprobe.
- OpenMontage creative guide: never trust metadata alone; verify final file, duration, resolution, codec, and audio state.
- ClipForge `video-composer`: normalize every segment to the same resolution, 30fps, square pixels, `yuv420p`, and encode final output as H.264/AAC with `+faststart`.

These designs are reused as lightweight Python behavior in `scripts/stitch_clips.py`; the full OpenMontage/ClipForge runtime is not copied because it is much larger than a Codex skill needs.

## Default Stitch Profile

- video codec: `libx264`
- audio codec: `aac`
- CRF: `18`
- preset: `medium`
- pixel format: `yuv420p`
- fps: `30`
- intermediate audio: PCM `s16le`, stereo, 48000 Hz
- final audio: one AAC encode after concatenation
- resolution: first clip unless `--target-resolution WIDTHxHEIGHT` is supplied

## Spoken-Audio Boundary Policy

For videos with generated speech:

- run with `--require-audio`; a clip with missing audio blocks stitching instead of receiving synthetic silence;
- do not add per-clip audio fades and do not crossfade two separately generated speech tracks;
- normalize each intermediate clip to lossless PCM audio, concatenate the normalized streams, then perform one final AAC encode;
- stitch only at script boundaries marked `stitch_safe=true`;
- inspect silence/freeze reports around every boundary before delivery.

The goal is a clean planned cut. Independent model requests share no native audio memory, so each request must already restate its full music palette, rhythm, texture, ambience, signature SFX and mix. The stitcher preserves the returned tracks; it cannot create missing sound layers or make independently generated music identical. Exact score continuity requires a separately approved local post-production mix.

For vertical ads, prefer:

```bash
python3 ai-commerce-video/scripts/stitch_clips.py \
  --project-dir <project> \
  --target-resolution 720x1280 \
  --target-fps 30 \
  --require-audio
```

## Completion Rule

A stitched output is complete only if:

- all input clips exist;
- every input clip passes ffprobe;
- final MP4 passes ffprobe;
- final MP4 has a video stream;
- audio stream is present when `--require-audio` is used;
- the report proves `per_clip_fades_applied=false`, `crossfade_applied=false`, `intermediate_audio_codec=pcm_s16le`, and `single_final_aac_encode=true`;
- every planned script boundary is complete and reviewed;
- `.stitch-report.json` is saved next to the final MP4.
