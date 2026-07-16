# Script Duration and Pacing

Use this reference whenever the requested delivery is longer than one Provider request or contains spoken selling.

## Legal Request Slots

The delivery duration and the Provider request duration are different:

- `delivery_max_seconds` is the final business requirement.
- Each paid request must use one value from the selected model's `allowed_duration_seconds`.
- For the configured Grok 1.5 route, the legal slots are `4, 6, 8, 10, 12, 15` seconds.
- Prefer the minimum paid request count. Use an exact sum when possible; otherwise use the smallest legal overshoot and trim only a verified idle tail locally.

Examples:

| Delivery target | Paid request plan | Notes |
|---:|---|---|
| 15s | `15` | One request |
| 25s | `15 + 10` | Two requests, exact |
| 30s | `15 + 15` | Two requests, exact |
| 45s | `15 + 15 + 15` | Three requests, exact |

Never send arbitrary unsupported values such as 5, 7, 13, or 14 seconds merely to make a timeline add up.

## Spoken Script Contract

- Write one approved campaign script, then split it by complete sentence meaning.
- Every paid segment gets its own `spoken_script`; never repeat the whole script in every request.
- Each non-final segment must end with a complete sentence, not an unfinished list, conjunction, price, unit, product name, or CTA.
- Leave a small speech margin. A 15-second generated clip should normally contain no more than about 14.2 seconds of estimated speech.
- Never cut a spoken word to meet the final duration. Trim only a silent or visibly idle tail after review.

## Continuity Contract

Use `continuity_plan.mode=planned_cut` for multi-segment commerce video. Keep consistency through:

- the same approved product identity and product colors;
- the same presenter identity when present;
- one campaign visual bible and lighting family;
- stable aspect ratio, resolution, and prompt guardrails;
- an intentional hook/demo/proof/CTA sequence;
- cuts at completed sentences and stable visual moments.

This improves business continuity without claiming that separate generative requests will create a mathematically seamless one-take video.

## Cost Contract

- `base_request_count` equals the number of planned shots.
- `approved_paid_cap` equals `base_request_count`.
- `repair_reserve=0` and `per_shot_repair_limit=0`.
- A shot may be submitted only once. Resume means poll the stored request ID, not resubmit.
- If a result fails business review, stop and ask for a new paid authorization before any replacement generation.
