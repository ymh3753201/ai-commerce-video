# Seedance Prompting Notes

Use these notes when Seedance 2.0 is selected or when writing Seedance-style prompts for future migration.

Source references:

- https://fal.ai/models/bytedance/seedance-2.0/reference-to-video/api
- https://fal.ai/docs/model-api-reference/video-generation-api/bytedance-seedance-2.0-reference-to-video

## Reference Roles

Assign every uploaded asset a clear role. Avoid vague instructions like "reference this image."

Examples:

- `@Image1 as the first frame`
- `@Image1 as the hero product appearance`
- `@Image2 as the synthetic model identity`
- `@Image3 as the lifestyle scene`
- `@Image4 as a 6-panel storyboard reference for shot order only`
- `@Video1 as camera movement reference`
- `@Audio1 as background music rhythm`

This skill maps local assets to tokens through model config. The bundled Seedance 2.0 fal route uses `reference_prompt_style: seedance_image`, which generates:

- `@Image1` for the first uploaded image reference;
- `@Image2` for the second uploaded image reference;
- `@Image3` for the third uploaded image reference.

Some third-party Seedance wrappers may use older `@(img1)` tokens. Do not use that style unless the selected model config explicitly sets `reference_prompt_style: seedance_at`.

Keep the token in the prompt next to the role. Do not only upload the file and hope the model infers its purpose.

## Prompt Formula

Use this structure:

```text
[Subject/Product] + [Scene] + [Action] + [Camera] + [Timed beats] + [Transitions] + [Audio] + [Style]
```

For videos over 8 seconds, prefer timed beats:

```text
0-3s: hook shot and product reveal.
4-8s: feature proof or lifestyle use.
9-12s: benefit and close-up.
13-15s: hero frame, tagline, CTA.
```

## E-commerce Product Ad Template

```text
Reference @Image1 as the hero product. Create a 15-second vertical product ad.
0-3s: Product enters with a dynamic slow rotation, close-up on texture and logo.
4-8s: Show the product in the lifestyle scene from @Image2, natural movement, premium lighting.
9-12s: Highlight the key selling point with a macro detail shot and subtle motion graphics.
13-15s: Hero product freeze frame, brand tagline appears, clear call to action.
Audio: upbeat commercial music, clean product interaction sounds, no noisy ambience.
Style: premium social-commerce ad, realistic lighting, smooth camera, no clutter.
```

Provider-specific Seedance example using this skill's default token style:

```text
Reference image map: @Image1 = product reference; @Image2 = synthetic presenter reference; @Image3 = 6-panel storyboard reference.
Create a 15-second vertical e-commerce ad. Preserve the product from @Image1. Use the presenter identity and outfit from @Image2. Follow the shot rhythm from @Image3 without changing the product identity. Use @Image3 only as shot order and timing guidance; render full-screen vertical video and do not reproduce grid panels, borders, labels, or a collage layout.
0-3s: Presenter hook and product reveal.
4-8s: Hand-held close-up and feature proof.
9-12s: Usage scenario and trust cue.
13-15s: Hero frame and CTA.
Audio: presenter speaks the confirmed sales script with upbeat commercial BGM and clean product handling sounds.
```

## Common Mistakes

- Do not pack too many scene changes into 4-5 seconds.
- Do not combine conflicting camera instructions such as static camera and orbit shot in the same beat.
- Do not leave reference assets unassigned.
- Do not upload references without citing their token in the prompt.
- Do not ask the model to reproduce a storyboard sheet layout; use it as timing/order guidance only.
- Do not ignore sound design; include music, sound effects, or voice direction.
- Match complexity to duration.
