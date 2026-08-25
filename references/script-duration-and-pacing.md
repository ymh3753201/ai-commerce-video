# Script Duration and Pacing

Use this reference whenever the requested delivery is longer than one Provider request or contains spoken selling.

## Legal Request Slots

The delivery duration and the Provider request duration are different:

- `delivery_max_seconds` is the final business requirement.
- Each paid request must use one value from the selected model's `allowed_duration_seconds`.
- Read legal slots and the reliable planning ceiling from the selected model key. Do not copy one route's duration table to another route.
- Official xAI Grok Imagine Video 1.5 documents 1–15 seconds. The current MikuAPI R2V adapter accepts those request values, but two observed 15-second requests returned about 10.042 seconds, so its production planning ceiling is 10 seconds until the relay proves otherwise.
- Prefer the minimum paid request count that stays inside the route's reliable ceiling and sums exactly to the delivery. Trim only a verified idle tail when an exact legal sum is impossible.

Examples:

| Route / delivery | Paid request plan | Notes |
|---|---:|---|
| MikuAPI R2V / 15s | `10 + 5` | Two reliable route slots, exact |
| MikuAPI R2V / 25s | `10 + 10 + 5` | Three reliable route slots, exact |
| Official xAI R2V / 15s | `15` | One documented slot; still requires route preflight |
| Official xAI R2V / 25s | `15 + 10` | Two requests, exact |
| Official xAI R2V / 30s | `15 + 15` | Two requests, exact |

Do not maintain a global list of “unsupported” values. Validate every request against that model key's `allowed_duration_seconds` and `planning_max_duration_seconds`.

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

Plan shots before distributing seconds. Each semantic beat belongs to exactly one Provider request. If a preferred beat crosses a route boundary, reflow the beat timings inside the assigned clip; do not submit half of the same action in one request and the remainder in another. Every edit boundary records:

- the outgoing stable state and incoming continuity state;
- the completed visible action that motivates the cut;
- the complete-sentence speech boundary;
- the full self-contained ambience/score/SFX fingerprint restated inside both independent requests, never “same as previous” or “沿用上一段”;
- the required post-stitch visual, loudness and listening review.

Independent generations share no native audio state. Restating the sonic fingerprint improves business continuity without claiming a mathematically seamless one-take or identical music. Exact score continuity requires a separately approved local post-production mix.

## Cost Contract

- `base_request_count` equals the number of planned shots.
- `approved_paid_cap` equals `base_request_count`.
- `repair_reserve=0` and `per_shot_repair_limit=0`.
- A shot may be submitted only once. Resume means poll the stored request ID, not resubmit.
- If a result fails business review, stop and ask for a new paid authorization before any replacement generation.
