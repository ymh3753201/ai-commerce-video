# Creative Variants

Use creative variants to keep the first proposal from becoming one-dimensional. If the user does not specify an ad style, present several practical options before image generation, then include one AI recommendation and the reason.

## Variant IDs

| ID | Chinese label | Status | Best fit |
|---|---|---|---|
| `commerce_direct` | 正规商品广告 / 转化型带货广告 | Supported default | Marketplace conversion, product pages, live-shopping clips |
| `story_reversal` | 剧情反转广告 / 生活剧情种草广告 | Supported | TikTok, Douyin, Reels, Shorts, social hooks |
| `hybrid` | 融合方案 | Supported | Story hook plus direct product proof |
| `ugc_review` | UGC 真实测评 | Supported | Xiaohongshu, TikTok, Reels, buyer-perspective ads |
| `comparison_test` | 对比测试广告 | Supported | Feature-led products, Amazon/YouTube/Shopify comparison |
| `lifestyle_seed` | 生活方式种草 | Supported | Lifestyle, home, fashion, beauty, Xiaohongshu/Reels |
| `premium_brand` | 高级品牌片 | Supported | High-end product, brand tone, design/material value |
| `feature_demo` | 功能演示 | Supported | Electronics, appliances, tools, beauty devices, product pages |
| `unboxing` | 开箱体验 | Supported | Gifts, electronics, toys, cosmetics, fashion |
| `live_shopping_teaser` | 直播间引流 | Supported | Douyin/TikTok live commerce, seasonal offers |
| `retargeting_offer` | 再营销优惠广告 | Supported | Paid retargeting, cart abandonment, limited offer |

## `commerce_direct`

Use for Taobao, Amazon, cross-border marketplaces, product detail pages, paid conversion ads, and live-shopping style clips.

- Structure: product reveal, pain point or desire, key selling points, short demonstration, price or offer if provided, trust proof, CTA.
- Storyboard logic: keep the product clear in every major shot; use close-ups, hand demonstration, presenter-to-camera selling, before/after use, and readable captions.
- Copy style: direct, confident, easy to understand; emphasize function, material, price, use case, buying reason, and CTA.
- Risk control: do not overpromise medical, financial, safety, or impossible effects.
- Image needs: product hero still, presenter/model with product, product-detail or usage-scene reference, final `video_source` for single-image models.

## `story_reversal`

Use for Douyin, TikTok, Xiaohongshu, Reels, Shorts, and short social seeding where a lifestyle scene, misunderstanding, contrast, or joke can create attention before selling.

- Structure: 0-3s hook, 3-7s conflict/pain point or misunderstanding, 7-11s reversal, 11-15s product solution and CTA.
- Storyboard logic: the product must cause or explain the reversal; the story cannot become pure entertainment with the product added at the end.
- Copy style: short spoken lines, natural dialogue, captions that set up the hook and reversal, then one clear product benefit and CTA.
- Risk control: keep the conflict simple and safe.
- Image needs: lifestyle scene still, protagonist/presenter reference, product hero/detail reference, storyboard sheet, final source frame or segment frames.

## `hybrid`

Use when the user replies "两个融合", "融合", or when AI recommends mixing both formats.

- Structure: story hook first, then direct selling proof.
- Storyboard logic: combine one short lifestyle pain point with clear product display, demonstration, and CTA.
- Copy style: one natural hook sentence, one reversal or relief line, then direct selling copy.
- Risk control: never sacrifice product clarity for plot.
- Image needs: final source/first-frame image, product detail reference, lifestyle scene reference, optional storyboard sheet.

## `ugc_review`

Use for buyer-perspective and creator-style ads.

- Structure: real-feeling first-person hook, use context, product detail, honest benefit, CTA.
- Storyboard logic: show the product in hand or in a normal scene; include small realistic details that make the experience believable.
- Copy style: natural, specific, not too polished; avoid fake authority or fake purchase claims.
- Risk control: do not invent medical results, fake personal identity, fake order proof, or unsupported testimonial.
- Image needs: buyer/presenter reference, usage scene, product detail, caption-safe source frame.

## `comparison_test`

Use when comparison helps buyers understand the product.

- Structure: neutral test setup, side-by-side feature comparison, product advantage, CTA.
- Storyboard logic: compare objective properties such as size, capacity, texture, speed, setup, or visible result.
- Copy style: fair and evidence-based.
- Risk control: avoid malicious competitor attacks, trademark misuse, or superiority claims without proof.
- Image needs: side-by-side setup, product hero, result caption, optional before/after reference.

## `lifestyle_seed`

Use for soft social seeding and aspirational product placement.

- Structure: lifestyle scene, product naturally appears, benefit detail, soft CTA.
- Storyboard logic: product should feel native to the lifestyle but stay visible enough to sell.
- Copy style: warm, personal, scene-driven, not too salesy.
- Risk control: do not hide the product inside mood shots; do not fake luxury or exaggerated lifestyle outcomes.
- Image needs: lifestyle scene reference, product-in-scene source, style reference, caption-safe frame.

## `premium_brand`

Use for high-end brand tone, premium products, design goods, fashion, furniture, audio, fragrance, or beauty.

- Structure: brand atmosphere, material/design detail, restrained product motion, concise value line, elegant CTA.
- Storyboard logic: use fewer shots, cleaner lighting, and controlled camera movement.
- Copy style: refined, sparse, confident.
- Risk control: avoid low-price shouting, noisy stickers, fake awards, and unsupported luxury claims.
- Image needs: premium hero, material macro, brand scene, typography-safe frame.

## `feature_demo`

Use when the buyer needs to see how the product works.

- Structure: problem or need, feature demonstration, close-up proof, result, CTA.
- Storyboard logic: hands, scale, screen, mechanism, or before/use/after sequence should be clear.
- Copy style: plain and proof-led.
- Risk control: only show real functions and realistic outcomes.
- Image needs: product hero, hand/use close-up, detail macro, final source frame or segment frames.

## `unboxing`

Use for gifts, cosmetics, electronics, toys, fashion, and premium packaging.

- Structure: package reveal, first impression, product detail, setup/use, CTA.
- Storyboard logic: opening action should reveal product identity and value, not just packaging drama.
- Copy style: tactile and specific.
- Risk control: do not invent package contents or accessories.
- Image needs: packaging, hand scene, product hero, detail reference.

## `live_shopping_teaser`

Use to drive viewers into a live room or live-shopping event.

- Structure: live-room reason, hero product, demo or offer preview, time/action CTA.
- Storyboard logic: presenter credibility, urgency, product clarity, and shopping destination matter more than cinematic story.
- Copy style: energetic but accurate.
- Risk control: avoid false scarcity or fake limited pricing.
- Image needs: presenter/live-room frame, product hero, offer caption, CTA-safe source.

## `retargeting_offer`

Use for people who may already know or have viewed the product.

- Structure: reminder, objection answer, offer/trust proof, direct CTA.
- Storyboard logic: do not over-explain the product; solve the reason they hesitated.
- Copy style: concise, practical, conversion-focused.
- Risk control: offers, discounts, and countdowns must be accurate.
- Image needs: product hero, offer caption, trust proof, landing/checkout context.

## First Proposal Requirements

When the user has not selected a style, present:

1. `方案 A: commerce_direct`.
2. `方案 B: story_reversal`.
3. At least two additional options selected from `ugc_review`, `comparison_test`, `lifestyle_seed`, `premium_brand`, `feature_demo`, `unboxing`, `live_shopping_teaser`, or `retargeting_offer`, based on product, platform, and campaign goal.
4. AI recommendation and reason, based on product category, platform, available assets, duration, compliance risk, and model capability.
5. Clear next action: user may reply with a plan label, `两个融合`, or `按 AI 推荐`.

Only after the user selects and confirms a variant may Codex generate approval images with imagegen/image2.
