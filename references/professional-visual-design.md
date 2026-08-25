# Professional Multi-Reference Commerce Visual Design

Use this reference before generating any approval image for `grok-imagine-video-1.5` Reference-to-Video.

## Design From the Product Outward

Start with supplied facts and pixels, not a fashionable style preset. Classify every product image by identity value: hero view, angle/detail, packaging/label, real-use context, duplicate, or unsuitable. Use all trustworthy evidence to generate and verify a faithful professional product master as the first Provider identity anchor. No raw material or non-generative derivative enters the default upload set.

Define one commercial promise and one visual proof. The 15-second film should make the viewer understand three things in order: what this is, why it matters, and what action to take. Choose the presenter, scene, wardrobe, lighting, lens language, movement, sound and edit rhythm to support that promise.

Do not branch the architecture by category keywords. Build the same `product_director_profile` for physical, soft, wearable, consumable, functional, digital, living or unknown products: product form, interaction mode, proof mode, talent value and evidence boundary. Category knowledge may improve creative judgment, but it never selects a separate prompt compiler or skips the evidence contract.

## Flexible 15-Second Structure

Choose 2–4 beats according to the big idea, speech capacity, and action completion. Do not force every ad into four slots:

| Beat count | Best use | Commercial progression |
|---:|---|---|
| 2 | Minimal luxury or one-proof hero film | Product-recognition Hook → Proof/Payoff/Packshot |
| 3 | Default commercial ad | Hook → tangible Proof/Payoff → memory-anchor Packshot |
| 4 | A distinct benefit payoff is essential | Hook → Proof → Payoff → Packshot |

The director assigns continuous times that fill the approved duration. Make the product recognizable early and keep any final static hold to about one second.

Design cuts before writing the video prompt. Prefer motivated transitions with a visible reason: hand-pass match cut, product-shape match cut, foreground occlusion, whip-pan, rack-focus reveal, macro-to-wide cut, action continuation, or sound bridge. Do not ask for random cinematic transitions. Do not promise frame-perfect edits; Reference-to-Video remains generative.

## Three Asset Layers

Keep these layers explicit and never mix them:

1. `input_evidence_assets`: raw user product, detail, presenter or scene materials. Every item remains evidence and is blocked from Provider upload.
2. `generated_reference_assets`: single-purpose support controls generated from the approved visual plan for the later Reference-to-Video slots.
3. `approval_preview_assets`: storyboard/contact sheets and annotated layouts for human review. They are never uploaded as references. Separate clean full-frame beat keyframes belong in `generated_reference_assets`, not here.

Within the evidence layer, form one ordered `product_identity_evidence` collection from every trustworthy same-SKU view. A file may have two purposes: a real-wear photo can remain model/context evidence while also entering the product collection because it proves fit and scale. Do not add unrelated people, scenes, style references, duplicates, or another SKU. Every generated image that shows or depends on the product receives this whole small collection through Codex `imagegen`; role-specific person or scene inputs are appended only when needed.

## Reference Portfolio

`grok-imagine-video-1.5` accepts 1–7 reference images, but seven is a ceiling, not a target. Default to the smallest non-conflicting portfolio, usually 3–5 images:

1. `product`: newly generated professional product master based on approved evidence; required and always first.
2. `beat_keyframe_hook`: one clean full-screen Hook composition when it materially controls the advertising idea.
3. `beat_keyframe_proof_payoff`: one clean full-screen Proof or Payoff composition.
4. `product_detail`: only when a supported second angle, texture, control, label, or mechanism must remain accurate.
5. `presenter`, `wardrobe`, `scene`, `hand_action`, or `style`: only when a specific identity, outfit, spatial, interaction, or finish risk remains unresolved.

Avoid redundant near-duplicates and conflicting examples. One image should have one primary job. Generate every support control after Stage 1, even when the user supplied a suitable presenter or scene: supplied non-product files remain evidence, while generated controls translate them into one coherent campaign world.

Do not fill all seven slots by habit. Each extra reference adds another instruction the model must reconcile. Use the smallest set that locks the product and the fewest essential campaign elements.

## Storyboard and Route Decision

A storyboard/contact sheet explains the edit to the user, but it contains several shots and functions in one image, so it remains review-only. Do not confuse that grid with separate full-screen beat keyframes: a clean keyframe can occupy one later reference slot and guide one composition/action inside the single 15-second timeline.

- Choose the paid topology from the selected route's reliable planning ceiling. Official xAI R2V can plan one documented 15-second request; the current MikuAPI R2V route plans 15 seconds as `10+5` because repeated 15-second requests returned about 10.042 seconds. Direct 1–4 complete semantic beats per request according to duration and keep each beat to one main camera move.
- Prefer element controls when product, person, scene or hand identity is the main risk. Add separate clean full-frame beat keyframes only when shot composition or transition continuity is the main risk. Never upload a multi-panel grid.
- Use segmented Image-to-Video when the exact opening composition of each shot matters. Generate one clean keyframe per segment from the approved storyboard, show all keyframes in Stage 2, submit one paid request per segment, and stitch them. The higher paid count must be disclosed and approved.
- Never upload a collage, storyboard grid or contact sheet as the only first frame or as an element-control reference.

## Image Prompt Contract

Every generated reference image needs a separate prompt containing:

- role and single control purpose;
- product category and factual constraints from supplied evidence;
- presenter, wardrobe, scene, framing, lens, lighting, palette and aspect ratio as relevant;
- clean commercial frame with no added text, subtitles, prices, CTA, watermark, or invented packaging;
- explicit exclusions: no duplicate product, altered logo/label, extra fingers, deformed hands, impossible product motion, collage, or contact sheet.

Do not put every control requirement into every image. The generated first-slot professional product master owns SKU identity after it passes evidence comparison. A presenter plate prioritizes a clear face and body, a scene plate the empty environment, and a detail/action plate one truthful proof.

Every generated reference records concrete `fact_source_asset_ids`, its actual ordered `generation_input_asset_ids`/paths/hashes, `mechanism_contract.observed`, `forbidden_inventions`, and an actual `multimodal_qc_result`. Product-dependent controls must use and be checked against the complete `product_identity_evidence` set before Stage 2. If the evidence does not show or state a mechanism, image prompts must forbid droppers, pumps, sprayers, buttons, ports, hinges, closures, opening methods, detachable parts, and mechanism-specific props. An attractive but unsupported applicator is a factual failure, not harmless styling.

## Video Prompt Contract

REST Reference-to-Video uses `reference_images`; the Python SDK calls the same input `reference_image_urls`. Assign prompt tokens in exact payload order: `<IMAGE_0>` through `<IMAGE_6>`. Never hand-write these tokens in the freeform visual direction. The prompt compiler appends one canonical mapping from the frozen upload order, preventing a role label from contradicting the actual file order.

Write one compact render prompt per paid request:

1. map each `<IMAGE_n>` to one locked role;
2. state aspect ratio, commercial finish, camera behavior, lighting and continuity;
3. choose `commercial_montage` or `continuous_sequence`; map complete semantic beats into the route-safe request timeline, with one main camera move per beat, supporting subject/light/material motion, an explicit entry state and an edit-safe exit state;
4. include approved dialogue exactly once, or explicitly request no dialogue;
5. preserve product identity and prohibit unsupported facts and newly generated written elements;
6. keep ordinary products passive—hands, people, camera, light, platforms, packaging, or real mechanisms may move;
7. render one compact `AUDIO` block containing voice direction, a sonic idea, time-aligned visible-action cues, ambience, score and mix hierarchy.

For multi-request films, allocate each semantic beat to exactly one clip and reflow its local times. Do not copy overlapping fragments of the same beat into adjacent prompts. Save entry/exit state, cut motivation and audio bridge at every boundary, then verify the edit and loudness after PCM-based stitching.

Reference images guide identity and style; they do not force the first frame. Never send both `image` and `reference_images` in one request.

## Two-Stage Approval

Stage 1 is creative approval: show product understanding, commercial idea, storyboard, spoken-copy meaning, transition plan, reference portfolio, every proposed image prompt and the final video-prompt blueprint. Do not generate reference images yet.

After approval, generate every planned Provider reference, save it locally, inspect it against the input evidence, and reject any control that changes the SKU or fails its single role. Generate a storyboard preview separately when useful and label it review-only. Prepare the project and complete free preflight on those exact files. Then show the actual ordered Provider set with its compiler-owned `<IMAGE_n>` assignments and the passing preflight result. Stage 2 approves those exact files, the final prompt, voice, subtitle choice and displayed paid request count. Only then confirm and submit. If an actual image, creative direction, prompt meaning, route, subtitle choice, voice, or paid count changes, repeat preflight and Stage 2.
