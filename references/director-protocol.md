# 商业广告导演执行协议

把本文件当作方案层的固定合同。先读图，再决策，再写方案；不要从“喜欢什么风格”开始。

## 1. 商品读图清单

逐项记录并区分“看得见的事实”“用户提供的事实”“待确认推断”：

1. 品类、SKU 形态、正侧背比例、主要颜色、材质与表面反射。
2. 包装是否完整；Logo、标签、规格和已有文字是否清晰；哪些文字绝不能重画。
3. 图片是否为干净商品图，是否含电商 UI、人物遮挡、低清、裁切或多 SKU。
4. 真实使用方式、尺寸关系、可运动结构和必要使用场景。
5. 可由品类和平台推断的目标人群；把推断明确标为推断。
6. 用户证据能够支持的卖点；禁止臆造功效、认证、销量、价格、折扣、成分、耐用年限和前后对比结果。

无论商品图质量高低，都只把它当作事实证据。阶段 1 通过后，必须用 Image 2 基于全部商品证据重新生成专业商品主控图；不得用裁切、复制、改名、去背或非生成式清理后的用户图冒充新参考图。低清、UI、杂乱背景和拍摄瑕疵只影响证据可信度，不构成直接上传原图的理由。

## 2. 策略与人才导演判断

先冻结七项策略：唯一商业主张、受众欲望/阻力、可视化证据、广告大创意、情绪曲线、人才作用、声音策略。不要先套“某品类只能拍某种镜头”的模板。

所有行业统一生成一份 `product_director_profile`，只描述导演真正需要的维度：商品形态、交互方式、证明方式、人物价值和事实边界。品类名称只是业务资料，不能选择另一套提示词模板。实体、食品、服装、家居、汽车、软件、宠物用品或未知商品都必须经过同一条“证据 → 商业策略 → 镜头 → 声音 → 模型编译”链路。

人物是否出现，只看能否明显增强以下至少一项：欲望、信任、尺度、使用证明、情绪。可以使用全身、局部、手部或完全不出镜；食品、数码、个护等品类也不再被硬性禁止使用人物。底线仍然不变：普通商品不能无依据自行活动；人物与特效不能发明商品机制、道具、功效或事实。

人物合同必须另存为 `talent_presence=none|hands_only|presenter`，并把“画面人物性别”与“旁白声音性别”分开。`none` 不能再混入“可见人物静默演示”这类通用句；最终提示词要明确排除人、脸、身体、手和人形剪影。`presenter` 若确认女性或男性，默认 R2V Reference Pack 必须有同性别的人物控制图，并写明不得替换性别。

只选一种主风格：`cinematic_product_hero`、`use_demo`、`lifestyle`、`unboxing_macro`、`ugc_spoken`、`before_after`。前后对比只有用户证据充分且合规时可选。

## 3. 15 秒导演方案输出

默认 9:16、720p，导演根据创意复杂度选择 2–4 个时间节拍。付费次数按路由已验证的稳定时长上限计算：官方 xAI R2V 最长 15 秒；当前 MikuAPI 中转请求 15 秒已两次实际返回约 10.042 秒，因此可靠规划上限为 10 秒，15 秒成片默认按 `10+5` 和 2 次付费请求展示给用户。不把四段时间表当成固定模板：

- 2 节拍适合极简奢华片：强 Hook/商品识别 → Proof、欲望与 Packshot 合流。
- 3 节拍适合多数商业片：Hook → 可信 Proof/Payoff → Packshot 与行动含义。
- 4 节拍只在利益兑现确实需要独立展开时使用：Hook → Proof → Payoff → Packshot。

时间分配由口播容量、动作完成度和广告大创意决定；商品要尽早可识别，最终稳定画面最多约 1 秒。每个节拍必须写清 `commercial_job`、入场状态、主体动作、构图、一个主运镜及速度、焦点、灯光运动、物理响应、离场状态、转场和同步声音。辅助的灯光、人物、液体、布料或真实机构运动不算第二个主运镜。

阶段 1 必须输出：商品分析与禁区、广告总览、唯一主风格、时间轴分镜表、逐秒口播轴、人物出镜合同、Reference Pack 槽位表、Grok 提示词蓝图、CTA/字幕方案和按当前路由计算的准确付费次数。声音必须单独给出五层：口播、动作音效、场景环境声、原创无歌词配乐、混音关系，并把关键音效对齐到可见动作或切镜。

中文口播以 38–48 个可见汉字为 15 秒设计区间，再按自然试听和总时间轴安全容量缩短。模特对白或旁白都由模型原生中文语音生成；对白用中文引号包住。不要承诺逐字复现，但冻结的提示词必须包含台词/旁白和清楚的语言、语气、节奏、情绪或声音风格描述。

## 4. Reference Pack 生图协议

Image 2 必须生成 `<IMAGE_0>`–`<IMAGE_6>` 中实际使用的全部图片。`<IMAGE_0>` 永远是基于用户证据重新生成的专业商品主控图。默认优先生成“商品主控图 + Hook 全屏关键帧 + Proof/Payoff 全屏关键帧”；只有身份、场景或动作仍无法控制时，才增加人物、场景、细节或动作图。七张是上限，不是目标。

商品主控图只承担 SKU 身份和专业产品摄影职责：单商品、干净背景、完整轮廓、适合 9:16 商业构图，并忠实保持可核验的形状、比例、颜色、材质、包装层级、瓶盖/开合结构、Logo 位置和现有标记。允许提升清晰度、布光、背景与构图；禁止发明、删除、改写或美化成另一个 SKU。生成后逐项对照全部证据；任何关键项漂移都要在阶段 2 前重新生成，禁止改用原图兜底。

允许角色：`presenter`、`wardrobe`、`scene`、`product_detail`、`hand_action`、`prop`、`style`、`beat_keyframe`。每张图必须保存具体的 `fact_source_asset_ids`、结构化 `mechanism_contract.observed`、`forbidden_inventions` 和实际多模态质检结果。只写“来自用户素材”不够，必须能追到具体证据资产。没有证据时，禁止出现滴管、泵头、喷嘴、按钮、接口、铰链、开合方式或可拆部件。关键帧必须是单张全屏广告构图，不得包含分格、箭头、说明文字或多个时间点。

每张图提示词同时保存中文导演说明和英文生产提示词。英文结构：

```text
[single role and subject], [approved pose/view], [approved lighting and palette],
clean isolated commercial reference plate, one subject, accurate anatomy,
no typography, no captions, no watermark, no storyboard panels, no arrows,
do not redesign the supplied product identity
```

Image 2 没有独立负面参数时，把以下内容作为末尾 `Exclude:` 条款：

```text
storyboard grid, contact sheet, split screen, panel borders, arrows, labels,
captions, subtitles, watermark, extra products, duplicate subject, extra fingers,
fused fingers, malformed hands, warped face, unreadable logo, invented packaging,
morphing geometry, busy background, mixed lighting, multiple actions
```

故事板拼图可单独生成给人审核，但必须进入 `approval_preview_assets`，绝不进入 `reference_images`。

## 5. Grok 1.5 镜头与提示词协议

- R2V：用于融合商品锚点、人物、场景、动作和风格，参考图不强制成为第一帧。
- I2V：用于必须精确锁定某条 clip 第一帧的情况；只上传一张首帧，提示词主要描述后续动作和一个运镜。
- 导演先选择 `commercial_montage` 或 `continuous_sequence`。前者由编译器输出唯一 `Cuts:` 时间轴；后者输出唯一 `Sequence:` 时间轴，不能伪装成多次切镜。跨多个独立生成请求时只允许有计划的商业剪辑，不承诺连续长镜头。
- 每个 R2V 请求根据时长使用 1–4 个语义完整的时间节拍：1–4 秒可用 1 个，5–10 秒通常 2–3 个，11–15 秒通常 2–4 个。单次时长不得超过所选路由的可靠规划上限。
- 每个时间节拍只声明一个主运镜：`push_in`、`pull_back`、`pan`、`tilt`、`orbit`、`track`、`locked_macro`、`static`、`crane`、`pedestal`、`handheld_follow`、`dolly_zoom`、`zoom` 或 `whip_pan`。不同节拍可以使用不同运镜，但不要在一个节拍里堆叠。
- 使用 `then`、`cut on action`、`match cut`、`foreground occlusion`、`rack-focus reveal`、`macro-to-hero match` 或声音桥明确连接相邻节拍；不要写随机转场合集。
- 官方 xAI 路由超过 15 秒拆分；当前 MikuAPI R2V 路由超过 10 秒即按最少合法请求数拆分。拆分时把每个完整语义节拍只分配给一个请求，再按该请求时长重新排布时间；禁止把同一个动作的前半段和后半段分别交给两个随机生成请求。只有用户明确要求切点/首帧精确控制时，才切到高成本分段 I2V。
- 引用图片只使用编译器生成的 `<IMAGE_0>`…`<IMAGE_6>`；不要手写 `@image1`。

Provider 提示词只保留高信息密度执行内容，详细证据、合规、质检和付费合同留在 JSON。顺序：

```text
Cuts 或 Sequence: [时间 + 商业任务 + 入场状态 + 构图 + 完整主体动作 + 一个主运镜/速度/焦点 + 灯光/物理响应 + 离场状态 + 转场 + sound on action（与该画面动作同步的完整声音）].
[精简视觉方向与广告大创意].
Reference image map: <IMAGE_0>=product identity; <IMAGE_1>=presenter identity; ...
[精简商品身份、人物和干净画面底线].
AUDIO: Dialogue/VO=“逐字台词或 none”; Voice=[语言、语气、节奏、情绪或声音风格];
SonicIdea=[声音大创意]; Cues=[引用上方逐节拍 sound-on-action，并保留本片段标志音 SFX];
Ambience=[连续场景声床]; Music=[原创器乐关系]; Mix=[人声、音效、环境与音乐层级].
```

只要有口播，默认使用提示词原生人声：在唯一 `AUDIO` 区块中写入逐字台词或旁白，并用自然语言描述声音，例如“克制、成熟、温暖的普通话高级广告旁白，节奏从容”。普通流程不冻结 `voice_id`，不发送 `reference_audios`，也不调用 `/v1/tts/voices`。只有用户明确要求某个 Provider 预设声线时，才把 `voice_id`、`reference_audios` 和 `<AUDIO_n>` 作为可选增强；它仍不是逐帧精确口型保证。

商业声音默认采用 `layered_native`：SFX、环境声和原创无歌词器乐共同承托口播。导演可以为汽车、机械、开盖、液体、脚步、布料、空间等可见动作设计标志音，但不能凭空加入与画面或商品不符的声音。每个画面节拍把完整声音动作直接写在 `sound on action` 中，使声音与可见动作、切镜或材质反应同一时间发生；唯一 `AUDIO` 区块负责汇总本片段标志音、连续环境声、音乐关系和混音层级，不重复长篇时间轴。若创意明确不要配乐，使用 `ambience_led`，此时仍要求动作音效和环境声；只有用户或导演明确说明“纯口播/无环境声”时才允许 `voice_only`。不得把 `Music=no music` 当作所有品类的默认值。

多段广告中的每次生成都是独立请求，模型不会继承上一段的音频状态。因此每个片段都必须用可直接执行的文字重新写全同一个声音指纹，例如乐器/节奏/质地、空间环境、标志音和人声混音；禁止使用“沿用上一段”“same as previous”“相同配乐继续”等依赖前文的代词。这样能提高风格接近的概率，但不能保证独立生成得到完全相同的旋律、音色或响度。若业务要求配乐逐帧一致，应改用另行批准的本地后期音乐/混音方案，不能在原生模型提示词中作虚假承诺。

编译器 `director-commerce-v8` 是唯一结构渲染者：`Cuts` 或 `Sequence` 二选一且只出现一次，`Reference image map` 和 `AUDIO` 各出现一次。它把每个计划声音提示渲染到对应时间节拍，保留片段级标志音，并记录 `sound_cue_coverage`；任何节拍缺声、标志音丢失、AUDIO 未链接时间提示或包含跨片段依赖词，都会在付费前被拒绝。自由视觉描述中的重复区块、空白 VO、重复台词、`, ,` 和手写图片映射也必须清除或拒绝。编译结果同时记录创意执行占比、参考图映射占比、底线占比、声音占比、主动作密度和提示词长度建议；这些密度指标用于改写提示，不作为新的付费阻塞门槛。

`max_prompt_chars=4096` 与 `prompt_budget_chars` 是本 Skill 的适配器/工作流预算，不是 xAI 官方公开的统一上限。11–15 秒广告通常把 1300–2400 字符作为内部目标区间；信息表达完整且合同无冲突时，不为凑固定数字添加文字。参考图映射应尽量低于总提示词的 25%，创意执行（镜头、动作、视觉方向、声音）通常应占至少一半。

Grok 禁止项：`storyboard grid`、`contact sheet`、`arrows`、`captions`、`subtitles`、`watermark`、`extra fingers`、`morphing logo`、`invented packaging`、`multiple camera moves within one beat`、`self-moving inanimate product`、`unmotivated transition stack`。CTA 文字也不交给模型生成。

## 6. 超长视频拼接与包装

请求数超过 1 时按计划顺序 concat；当前 MikuAPI R2V 的 15 秒成片因 `10+5` 可靠规划会进入该流程。每个边界都要保存出段稳定状态、入段连续状态、切镜动机和声音桥；切点只能放在完整动作与完整句子之后。先统一分辨率、帧率、像素格式和 PCM 中间音频，再进行一次最终 AAC 编码。禁止用交叉淡化掩盖语音断句。拼接报告必须标记动作边界、环境/音乐连续性和响度一致性仍需试听验收。最终 packshot 保留约 1 秒稳定画面。字幕和 CTA 均在干净视频通过后本地添加，并保持在平台 9:16 安全区内；CTA 只能使用用户提供或确认的文字。

## 7. 质检失败码与局部重做

| 失败码 | 判定 | 只重做 |
|---|---|---|
| `QC_PRODUCT_DRIFT` | 商品形状、颜色、包装或 Logo 漂移 | 商品锚点清理/对应 clip，不动已通过 clip |
| `QC_CAMERA_MOVE_CONFLICT` | 同一时间节拍堆叠多个主运镜或运动糊乱 | 该节拍的导演动作与提示词；未付费授权前不重提任务 |
| `QC_REFERENCE_CONTAMINATION` | 出现分镜格、箭头、文字、重复主体 | 污染的 Reference Pack 图及受影响 clip |
| `QC_SPEECH_OVERRUN` | 台词超时、断字或切镜吞字 | 口播时间轴和 AUDIO 块 |
| `QC_HAND_ANATOMY` | 多指、融指、手与商品穿模 | 手部动作参考图及受影响 clip |
| `QC_CTA_UNREADABLE` | 本地 CTA 不可读或越出安全区 | 本地包装层，不重新生成视频 |
| `QC_DURATION_SHORTFALL` | Provider 片段比批准时长短超过 1 秒 | 阻断交付，不用长静帧冒充完整广告 |
| `QC_SPEECH_MISSING` | 计划有口播但缺失、不可理解或销售含义丢失 | 阻断交付并保留证据，不自动付费重做 |
| `QC_TALENT_MISMATCH` | 无人方案出现人、人物缺失或明确性别被替换 | 阻断交付，核对人物合同与控制图 |
| `QC_VOICE_GENDER_MISMATCH` | 明确女声/男声方向没有保留 | 阻断交付，核对唯一 AUDIO 区块的声音描述 |
| `QC_SOUND_DESIGN_MISSING` | 计划中的音效、环境声或配乐听不见 | 阻断交付，保留证据，不因存在 AAC 音轨而通过 |
| `QC_AUDIO_MIX_FAILURE` | 人声把声音场景全部盖住，或声音场景盖住口播 | 阻断交付，核对声音合同和 AUDIO 混音要求 |

任何付费局部重做仍需新的明确授权；失败码只指定最小修复范围，不自动购买重试。
