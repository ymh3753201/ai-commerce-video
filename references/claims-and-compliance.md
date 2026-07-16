# Claims and Compliance

Use this reference before writing claims, comparison copy, before/after scenes, UGC review lines, subtitles, disclaimers, and CTA. This is a creative risk-control guide, not legal advice. If the product is regulated or high-risk, ask the user for approved claims and evidence before generating final paid video requests.

## Claim Risk Levels

| Level | Use when | Rule |
|---|---|---|
| `low` | Fashion, decor, generic accessories, simple household items | Keep materials, size, price, and availability accurate. Avoid impossible claims. |
| `medium` | Food, pet, electronics, home appliances, fitness, beauty-adjacent products | Use evidence-backed feature language. Avoid guaranteed results and unfair before/after exaggeration. |
| `high` | Medical, health, supplements, baby/pregnancy, strong skincare efficacy, weight loss, safety-critical products | Avoid diagnosis, treatment, cure, permanent result, guaranteed safety, medical-grade, and professional endorsement claims unless supplied and approved by the user. |

## Category Rules

| Category | Avoid | Needs evidence | Safer wording |
|---|---|---|---|
| Beauty / skincare | Cure acne, remove wrinkles permanently, medical treatment language, fake before/after | Ingredient data, test results, approved claim sheet | Helps skin look smoother, supports daily care, creates a hydrated-looking finish |
| Supplements / health | Treats disease, cures insomnia, guaranteed weight loss, doctor-like advice | Approved health claims, certifications, dosage guidance | Supports daily routine, convenient nutrition, consult a professional if needed |
| Food / beverage | Medical benefit, guaranteed slimming, fake freshness or origin | Ingredients, nutrition, origin, certificates | Tastes fresh, convenient snack, suitable for daily sharing |
| Mother and baby | Absolute safety, medical prevention, unsuitable age claims | Age range, safety certification, material proof | Designed for supervised use, soft material, check age guidance |
| Pets | Cure illness, guaranteed behavior change, unsafe feeding claims | Vet-approved info, ingredients, size guidance | Helps daily care, suitable for specified pet type/size |
| Electronics / digital | False compatibility, waterproof without rating, battery exaggeration | Certification, IP rating, battery test, compatibility list | Works with listed devices, designed for daily use, up to stated spec when verified |
| Home / furniture | False material, fake load-bearing, impossible comfort claims | Material, dimensions, load rating, warranty | Space-saving, easy to match, comfortable-looking support |
| Clothing / fashion | Unrealistic body transformation, fake fabric, fake brand association | Material, size chart, authorized brand info | Flattering cut, soft fabric feel, easy to style |
| Fitness | Guaranteed fat loss, injury prevention, medical rehab | Training evidence, usage warnings, certifications | Helps organize training, supports daily exercise routine |
| Medical-related | Diagnosis, treatment, cure, prevention, professional claims | Regulatory approval and approved copy | Do not proceed without user-supplied approved claims. |

## UGC and Review Rules

- Review-style ads can sound natural, but must not invent a fake personal identity, fake purchase record, fake doctor/teacher/expert role, or fake result.
- Use "体验感", "使用场景", "我会怎么用", and "适合谁" rather than unverifiable absolute results.
- If the product needs real certification, ask for it or weaken the claim.

## Before/After and Comparison Rules

- Before/after scenes must be plausible and should not imply guaranteed personal results.
- Use objective test setup when possible: same lighting, same angle, same object, same time span.
- Competitor comparison should focus on feature categories, not attacking named brands, unless the user supplies verified evidence and legal approval.
- Do not manipulate the "before" scene to look artificially bad.

## Disclaimer Rules

Use a disclaimer when:

- the claim touches health, safety, baby, fitness, skin, medical, financial, or regulated outcomes;
- the visual uses before/after;
- the result depends on personal conditions, usage method, or environment;
- platform policy commonly requires it.

Keep disclaimers readable and inside the safe zone. Do not hide them under UI overlays. A disclaimer is a local postproduction overlay: never ask the video Provider to render it, because generated wording may be wrong.

## Prompt Guardrail

Use this as a planning and local postproduction guardrail. Do not instruct the video Provider to generate the disclaimer text itself:

```text
Compliance guardrail: keep claims evidence-safe and platform-safe. Do not imply diagnosis, cure, guaranteed result, professional endorsement, false scarcity, fake review, fake before/after, or competitor attack. Use realistic product-use language. If a disclaimer is required, reserve clean safe-zone space and add exact approved wording during local postproduction only.
```
