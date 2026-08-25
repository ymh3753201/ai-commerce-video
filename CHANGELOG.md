# Changelog

## Unreleased

- Closed the legacy direct paid-submit bypass: real Provider POSTs now require the immutable workflow confirmation, readiness binding, frozen production contract, paid cap and one-submit ledger.
- Bound free readiness to the exact Provider/model/base URL/network route used for paid POST, and reject credentialed polling URLs on a different host.
- Stopped auto-filling image-generation input and QC evidence, isolated the optional 119337 credential, and made private env writes atomic.

- Added one ordered `product_identity_evidence` contract for 1–3 trustworthy same-SKU views. Repeated `--product-image` inputs now remain one evidence set; product-dependent Codex imagegen controls record ordered input IDs, paths and SHA-256 values, and free preflight blocks missing views without adding another user approval or paid request.
- Added plan schema v3, `director-commerce-v8`, and `universal-product-director-v4`: one category-agnostic product director profile now serves physical, wearable, consumable, functional, digital, living, and unknown products. Beats carry commercial job, entry/action/exit state, framing, one dominant camera movement, focus, light/physical response, transition, and synchronized sound-on-action.
- Hardened native commercial sound across independent requests. Every clip now restates a self-contained sonic fingerprint, preserves its signature SFX, renders every cue beside the matching visible action, links those cues from the single AUDIO block, and rejects cross-clip shorthand before payment. Technical review now separates media status from formal delivery and adds a no-cost silence/signal warning without pretending it replaces listening.
- Added explicit `commercial_montage` versus `continuous_sequence` prompt rendering, compact reference maps, creative/reference/guardrail/audio density metrics, and prompt-limit provenance that separates xAI-documented capability from internal adapter/workflow budgets.
- Changed multi-request planning from overlapping time fragments to whole semantic-beat allocation with route-boundary reflow. Stitch contracts now preserve stable exit/entry states, cut motivation and audio bridges, and require edit, sound-continuity and loudness review.
- Expanded commercial audio from clip-level labels to one sonic idea, per-beat timecoded cues, ambience bed, score palette, energy curve and mix hierarchy. Validators now check semantic sound fields instead of requiring stock warning phrases in every Provider prompt.
- Added an explicit commercial `sound_design_contract`. Ordinary ads now default to action-synced SFX, scene ambience, restrained original instrumental music without vocals, and clear foreground speech; intentional no-music plans remain ambience-led, while voice-only must be explicit. Preflight and final review now reject missing required sound layers or an unusable mix without authorizing an automatic paid retry.
- Separated visible-talent presence/gender from voice gender. Product-only prompts now explicitly exclude every human form, approved female/male presenters require a matching generated control on default R2V, and final delivery blocks unexpected people, presenter-gender substitution, or explicit voice-gender drift.
- Added route-specific reliable duration planning. Official xAI remains documented at 15 seconds, while the default MikuAPI R2V route now plans at 10 seconds after two saved 15-second requests returned about 10.042 seconds; a 15-second Miku delivery therefore freezes `10+5` and two paid requests. Polling blocks excessive shortfall immediately and never auto-retries.

- Changed ordinary spoken ads from mandatory preset voice references to prompt-native speech. Dialogue/VO plus natural-language delivery direction is now sufficient; automatic `altair`, required `reference_audios`, `<AUDIO_0>`, and the blocking `/v1/tts/voices` readiness call were removed from the default path. Explicit preset voices remain optional.
- Simplified the main Skill into progressive plan/reference/production/review modes; replaced the rigid four-slot template with director-chosen 2–4 beats, added a commercial-quality rubric, concrete evidence/mechanism metadata, mandatory multimodal reference QC, and same-route live preset-voice visibility checks before paid submission.
- Added plan schema v2 and strategy-first director compiler v6: one proposition/visual-proof contract, one compiler-owned Cuts timeline/reference map/AUDIO block, prompt-native speech direction, optional explicit `reference_audios`, reference-image fact/mechanism locks, and blocked delivery for missing speech or Provider duration shortfall over one second.
- Rebuilt the professional ad-director contract: every user upload is evidence only and the mandatory first R2V reference is a newly generated, fidelity-checked professional product master; route-legal requests use time-coded beats, one main camera move per beat, motivated transitions and a structured AUDIO block; separate clean full-frame beat keyframes may guide composition without uploading a storyboard grid.
- Added a bilingual reference-image generation protocol, negative prompts, three complete worked examples, preset `reference_audios` voice-ID payload support, and local-only CTA packaging guidance.
- Restored MikuAPI as the default `grok_video_15_reference` Provider while retaining the same `grok-imagine-video-1.5` 1–7-reference REST contract; official xAI is now the explicit optional `grok_video_15_reference_xai` route with separate credentials.
- Added the official xAI `grok-imagine-video-1.5` Reference-to-Video route with 1–7 ordered references, zero-based `<IMAGE_n>` roles, 15-second generation, and strict separation from single-image first-frame mode.
- Added a professional two-stage ad workflow: approve the complete visual plan first, keep the approved product anchor and generate the support control set, then approve the actual ordered images and frozen paid request count.
- Split visual assets into raw `input_evidence_assets`, fully generated `generated_reference_assets`, and review-only `approval_preview_assets`; the default Grok route rejects every raw/copy-identical upload, requires a generated `product` master first, rejects storyboard/contact-sheet uploads, and blocks manual `<IMAGE_n>` mappings that could contradict upload order.
- Added `visual_design_contract` for commercial objective, 15-second beat design, motivated cuts, image prompts, reference-role selection, and the final video-prompt blueprint.
- Preserved the existing MikuAPI single-image route as an explicit optional adapter with separate credentials and contract fields.
- Retained the earlier `grok_video_15` MikuAPI adapter with plural create/poll endpoints, `image.url`, `duration`, and dedicated Keychain/env credential isolation.
- Added a no-cost, same-route Provider readiness gate before the first paid video POST; regional 403, DNS, and model-visibility failures now preserve the existing authorization and paid count, with optional Skill-only proxy configuration that never edits Clash or system proxy settings.
- Replaced the ordinary plan/image/script/preflight/payment confirmation chain with one final `确认并生成` authorization after the actual images and no-cost preflight are ready; review-first mode remains available on request.
- Documented `503 model_not_found` diagnosis through no-cost model visibility checks and prohibited automatic paid resubmission when the Provider cannot route the video model upstream.
- Corrected the 119337 `grok-video-1.5` single-image contract to one item in `image_urls` (`119337-video-v1`), matching the gateway's explicit model example.
- Added a final pre-HTTP contract check so model settings or rebuilt payload drift cannot silently differ from the approved no-cost preflight.
- Simplified the ordinary user proposal while retaining detailed internal project contracts.
- Changed long-video business review to practical stitch/reference consistency and meaning-based speech acceptance instead of word-for-word matching.
- Deferred optional subtitle runtime checks until after the clean video exists, so missing subtitle tools do not block video generation.
- Added `provider_image_contract_mismatch` evidence when the gateway rejects an exact-one-image payload, with automatic fallback retries prohibited.
- Added director prompt compiler v5 with a single-request beat timeline, one camera move per beat, canonical identity guards, and a final structured AUDIO block.
- Replaced product-keyword semantic deduplication with one six-component architecture and a dynamic visual-direction budget for every product category.
- Added a public brief adapter for nested product fields, `presenter_script`, visual direction, audience, selling points, price, and CTA text.
- Added structured render rules for static products, demonstrated functions, live subjects, software screens, and food/liquid motion.
- Removed API-key previews from configuration reports; validation now exposes presence only.
- Removed planning-only platform/scenario prose and exact speech duplication from Provider prompts.
- Added outbound prompt, payload, and image fingerprints plus gateway/upstream/channel result tracing.
- Added legacy-request trace recovery and correct separation of gateway database record IDs from nested upstream task IDs.
- Added source-image versus generated-first-frame evidence and a required business consistency gate.
- Clarified that downloaded/job `verified` state is technical media verification, not delivery approval.

## 1.0.0 - 2026-07-16

- Prepared `ai-commerce-video` as a standalone open-source repository.
- Added bilingual usage documentation, security policy, contribution guide, CI, and issue templates.
- Added deterministic local `.skill` packaging and release auditing.
- Added compact provider-prompt compilation with 3200/4096 character gates.
- Added platform, scenario, compliance, model, reference-asset, paid-request, review, and delivery contracts.
- Added local optional subtitle generation and burning after clean-video acceptance.
- Isolated third-party `119337` credentials from `XAI_API_KEY`.
- Verified the offline suite, installed Skill, package contents, and no-cost preflight.
