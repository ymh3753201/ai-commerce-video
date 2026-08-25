# Subtitles and Safe Layout

Use this reference only when the user requests subtitles or the confirmed platform plan requires a captioned delivery.

## Non-Negotiable Provider Rule

The video Provider must generate clean frames only. Never place subtitle, caption, SRT, VTT, lower-third, price-text, CTA-text, disclaimer-text, or other written-overlay instructions in the Provider prompt or payload. Generated lettering is unreliable and can contaminate product packaging.

An enabled subtitle plan must contain:

```json
{
  "enabled": true,
  "request_source": "user_plan_confirmation",
  "confirmation_status": "confirmed",
  "provider_policy": "never_send",
  "render_policy": "postproduction_burn_only",
  "paid_api_call": false,
  "subtitle_included_in_payload": false
}
```

If these fields are absent or changed, keep subtitles disabled and proceed with the clean video. Stop only before subtitle generation/burning until the subtitle plan is corrected.

## Local Postproduction Flow

1. Finish and review the clean video first.
2. Transcribe final audio locally with the configured Whisper executable/model.
3. Use the finished video's actual audio transcript for subtitle wording and timing. The planned script is review context only; do not force planned words into captions when the model paraphrased them.
4. Review names, SKU, price, discount, unit, offer, CTA, and disclaimer text.
5. Render subtitles with `burn_subtitles.py` into a separate `final.captioned.mp4`.
6. Preserve `final.mp4` as the clean Provider master.
7. Review the captioned output and only then finalize delivery.

Subtitle generation and burning are local postproduction operations and must not spend video-generation credits.
Do not require Whisper, libass, FFmpeg subtitle filters, or an SRT file during paid-video preflight. Check those dependencies only after the clean video exists and only when subtitles were requested.

## Commerce Caption Style

- Use short phrase groups, normally one or two lines.
- Use high contrast with outline or shadow; do not cover the product, hands, face, packaging, or proof detail.
- Keep captions inside the selected platform safe zone and above shopping anchors/native controls.
- Emphasize only verified selling words; do not add claims that were not spoken or approved.
- Keep numeric facts exact, including currency, decimal point, percentage, capacity, size, and time limits.
- Avoid decorative fonts that reduce mobile readability.

## Caption Review Gate

The captioned delivery must verify:

- subtitle presence and local postproduction origin;
- safe-zone placement and mobile readability;
- timing matches final speech;
- no clipped lines, overlapping text, invented claims, or unapproved text;
- product packaging remains readable and unobstructed;
- critical facts match the confirmed plan exactly.
