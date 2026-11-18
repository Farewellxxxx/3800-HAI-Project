# 三个现有输入到 MRT2：流程对比与本地验证

2026-11-14。工作分支 `feature/input-event-mrt2`。对比基线：本地 `3d32fcd`、团队 `3123738092/aiaa3800_jammate` 的 `codex/jammate-workbench@5dc9fb8`。本次在独立检出中合并团队实现并修改；原来的工作目录和有未提交改动的 `JamMate-mrt2-inputs` 保留。

**结论：团队已经有 InputEvent、Harness、BandPlan 和 MRT2 runtime，值得直接复用。原来的三个网页尚未全部走这一条链。本次接通了三个现有入口，并在这台 RTX 4050 6 GB 机器上实际生成、下载、解码和播放了三段 MRT2 音频。**

这里的“播放通过”指自动化浏览器的 `play()` 成功、播放器时间前进、音频可解码且非静音。没有进行人耳音质评分或物理扬声器验收。MRT2 输出保留团队的 **preview** 定义：是真实模型生成，但不保证逐音符、节奏、音色和原有声部精确保留，因此不提交虚假的演奏状态。

### 2026-11-16 重启与 Notion 核对

工作台已从现有 `27fcad3` 重新启动到 `http://127.0.0.1:4197/`；三个主页面均 HTTP 200，workspace backend 和 MRT2 安装检查通过。本次没有重新跑完整测试或模型推理，下文测试与耗时仍是 11 月 14 日的证据。当前 WSL 服务未配置文字 LLM 或 FluidSynth，使用本地 RuleAgent；精确对照可用 NumPy。

已通过浏览器读取最新可见的 [产品 SPEC](https://app.notion.com/p/SPEC-403c92b8f6c5802689a9c2af142d7a49) 和 [多模态输入任务](https://app.notion.com/p/InputEvent-403c92b8f6c58059ac46c4375274b583)。Notion connector 对项目返回 404，但已登录网页可以访问；没有修改 Notion 内容或任务状态。

- **已对齐**：perception 只产生 InputEvent；团队 Harness 决策；MIDI/MRT2 条件属于 renderer 内部表示；不虚构未知置信度；保留可追踪样例。
- **用户模块仍有缺口**：键盘文字不等于真实 speech/ASR；自然 phrase segmentation、BPM range、真实 clap/snap/tapping/口技标注测试与置信度校准尚未完成。当前完整任务应继续为 In progress。
- **明确暂缓**：Start Jam 一次、自然 verbal priming 和自动 modality routing 按本次约定暂不实现，仍是正式产品要求。
- **团队联合缺口**：跨入口唯一会话/共享时钟、连续播放/下一小节调度、八类 Golden Scenarios 和音乐体验验收尚未由这次三个独立短片段的测试证明。
- **契约细节**：`rhythm_seed` 本来就在 SPEC；实际 schema 增加 `source=text` 区分键盘，支持哼唱 1.2，但尚无 SPEC 提到的 `instrument` / `instrument_phrase`。这些需作为版本范围说明，不能宣称所有 modality 已支持。
- **交接缺口**：本次成果仍是本地分支；正式团队交接还需对应 GitHub branch/PR 和 Notion 实验结论，不能仅靠本地文档标记完成。

人工验收建议先用三路自带示例确认事件，再用自己的短录音检查识别，最后启用 MRT2 preview 判断生成是否与输入有可感知联系。持续单音不应被大量切碎，真重复音不应全部合并；节奏先四拍定速再录一小节；文字先用 RuleAgent 支持的“来一段，慢一点”。下载事件与 trace 应对应同一 event_id，preview receipt 应保持 state_committed=false。主观听感验收与结构/API 验收分别记录。

## 1. 原来的本地流程

```mermaid
flowchart TD
  H[哼唱网页：录音或导入] --> BP[Basic Pitch 帧输出]
  BP --> DEC[连续音解码 / 平滑 / 清理]
  DEC --> M[MelodyDocument：原始证据和选定音符]
  M --> HEX[旧下载按钮：未带 schema_version 的 notes 结构]
  M --> HPOST[另行组装 InputEvent 1.2 / payload.melody]
  HPOST --> HC[/api/create]
  HC --> HA[本地 StateManager / RuleAgent]
  HA --> HB[BandPlan]
  HB --> HR[NumPy 或 Kevin / FluidSynth]
  HR --> HW[WAV / MIDI]

  R[节奏网页：四拍定速加一小节] --> RA[onset 检测 / BPM / 16 分网格]
  RA --> RE[标准 rhythm InputEvent]
  RE --> RC[/api/reference/rhythm/create]
  RC --> RJ[jam_rhythm 直接编排；绕过 Harness]
  RJ --> RW[WAV / MIDI]

  T[文字网页] --> TR[前端 trim 原文]
  TR --> TT[/api/reference/text/turn]
  TT --> TE[from_text / InputEvent]
  TE --> TH[独立文字作品的 StateManager / RuleAgent 或 LLM]
  TH --> TB[BandPlan]
  TB --> TW[NumPy 或 Kevin / FluidSynth]

  M -.-> EX[额外 MRT2 导出按钮：prompt + midi_base64 + duration_s]
  RE -.-> EX
  T -.-> EX
  EX --> FILE[下载 handoff JSON；没有运行 MRT2]
```

这条基线已经有不少正确部件，尤其哼唱清理、节奏识别、团队 contracts 和文字 Harness。真正需要改的接缝是：

1. 哼唱的“下载 InputEvent”与用于生成的 InputEvent 不是同一份结构。下游拿下载样例联调时会遇到不一致。
2. 节奏识别能产生标准事件，但生成路径直接调用旧的节奏编排函数，无法证明它经过 Wyman 的 Harness。
3. 文字页在提交之前 `.trim()`，原文中的首尾空白丢失；原来的响应也没有把实际接受的事件完整暴露给前端下载。
4. `web/mrt2-input.js` 的 JSON 是 renderer 的直接输入包，包含 prompt 和 MIDI，不是公共 `InputEvent`。下载成功不能证明模型已经运行。
5. 旧 reference 路由的默认加载方式是固定团队快照 `a63a0f5`，不能仅因本地更新了文件就假设后台使用了新实现。

主要代码：`web/optimized/src/app.js`、`web/optimized/src/input-event.js`、`web/rhythm.js`、`web/text-creation.js`、`src/jammate/input_band.py`、`scripts/reference_worker.py`。

## 2. 团队仓库当时的流程

```mermaid
flowchart TD
  HS[哼唱 InputEvent] --> OLDH[/api/create / 原有精确合成链]
  RS[节奏 InputEvent] --> OLDR[/rhythm/create / 直接 jam_rhythm]
  TS[文字输入] --> AD[from_text]
  AD --> EV[InputEvent]
  EV --> SM[StateManager 接收事件]
  SM --> AG[RuleAgent 或 LLMAgent / Harness]
  AG --> PLAN[BandPlan：策略、Actions、preserve、版本与触发事件]
  PLAN --> FACT[create_runtime]
  FACT --> PRECISE[OfflineRuntime 或 KevinRuntime]
  FACT --> MRT[MRT2Runtime 能力检查]
  MRT --> STRICT[严格模式：不能保证 preserve 时明确拒绝]
  MRT --> PREVIEW[明确允许 preview]
  PREVIEW --> MIDI[团队 scheduler / 编排生成标准 MIDI]
  MIDI --> TOK[25 Hz 音高集合与二值鼓条件]
  TOK --> GEN[官方 Magenta RT 2 / JAX 或 MLX]
  GEN --> AUDIO[WAV + ExecutionReceipt]
  AUDIO --> UNCOMMITTED[preview / artifact_generated=true / state_committed=false]
```

团队已有的核心文件如下，本次直接沿用：

| 边界 | 团队实现 | 本次处理 |
|---|---|---|
| 标准事件 | `src/jammate/contracts/input_event.schema.json`、adapters | 使用现有 schema，不发明另一套中间协议 |
| 事件与决策状态 | `src/jammate/state.py`、`orchestration/manager.py` | 复用，不在 perception 中维护另一个 JamState |
| 策略与动作 | `src/jammate/orchestration/` | 复用 RuleAgent/LLMAgent；输入模块不输出 BUILD/PRESERVE 等决策 |
| 渲染器选择 | `src/jammate/render/runtime.py` 的 `create_runtime` | 让音频输入也使用该工厂 |
| MRT2 执行边界 | `renderer_experiments/app/mrt2.py` | 保留 capability 检查和 preview receipt |
| 官方模型包装 | `src/jammate/render/mrt2.py` | 保留 MIDI→25 Hz 条件和官方推理 |

因此，“团队已经接好了从 InputEvent 到 MRT2”对**后端组件和文字入口**成立；它不意味着三个网页已经都调用这些组件，也不意味着 MRT2 实现了所有精确执行要求。

## 3. 现在的流程

```mermaid
flowchart TD
  H[保留哼唱网页] --> HP[预处理 / Basic Pitch / 连续音解码]
  HP --> HE[InputEvent 1.2：payload.melody]
  R[保留节奏网页] --> RP[onset / BPM / pattern]
  RP --> RE[InputEvent 1.0：payload.rhythm]
  T[保留文字网页] --> TP[原文逐字保留 / from_text]
  TP --> TE[InputEvent 1.0：payload.text]
  HE --> AUDIO[/api/reference/input/render]
  RE --> AUDIO
  TE --> TEXT[/api/reference/text/turn]
  AUDIO --> HARNESS[共享团队 StateManager / RuleAgent / BandPlan 实现]
  TEXT --> HARNESS
  HARNESS --> FACT[同一个 renderer 工厂]
  FACT --> EXACT[NumPy 或 FluidSynth]
  FACT --> M[MRT2 capability gate]
  M --> REJECT[严格模式不满足约束：返回错误]
  M --> PREVIEW[用户勾选 preview：真实 MRT2 生成]
  EXACT --> RETURN[音频 / MIDI / 原事件 / Plan / State / Receipt]
  PREVIEW --> RETURN
  RETURN --> PAGE[原网页播放与下载 / trace.json]
```

**统一的是事件契约和下游模块，不是这一阶段的收音入口或跨页会话。** 音频演示每次生成一个独立短片段；文字页仍按团队原实现维护自己的作品会话。没有增加 Start Jam、常开麦克风、ASR、自动分类、跨页长期状态或共享 session clock。

音频生成与文字生成共用一个后台 worker，从而共用已加载的 MRT2 模型，避免三路各占一份 GPU 显存。节奏分析仍在另一个 worker 中，不必排在模型推理之后。哼唱/节奏页切换输入或 renderer 后，旧音频和下载链接立即失效；文字页允许在编辑下一句时回听上一段，在提交新要求时清除旧结果。请求失败时不会把上一次的音频呈现为本次结果。

## 4. InputEvent 到底统一了什么

| 项目 | 文字 | 节奏 | 哼唱 |
|---|---|---|---|
| schema_version | `1.0.0` | `1.0.0` | `1.2.0` |
| source | `text` | `rhythm` | `humming` |
| event_type | `speech` | `rhythm_seed` | `musical_phrase` |
| 内容 | `payload.text` 原文 | `payload.rhythm` 中 BPM、onset_beats、accents | `payload.melody` 中选择后的 notes、原始模型证据、预处理信息 |
| 顶层 confidence | `null` | `null` | `null` |
| 时间含义 | 未知时 `null` | 当前录音的秒数；beat_origin_s 定位节奏起点 | 当前录音的秒数；保留裁剪偏移 |

这是同一个支持版本演进的 InputEvent 契约，并非要求三个 payload 长得一样。哼唱必须用已被团队支持的 1.2 版，以保留所选 motif 和原始证据。下载、提交及响应中的事件现已逐字段相等；BandPlan.trigger_event_ids 指向该事件。

与粘贴的产品 SPEC 的差异有明确边界：团队实际 schema 增加 `source=text`，并将哼唱 1.2 的 `payload.melody` 具体化；`event_type=rhythm_seed` 原本就在 SPEC 中，不是新增扩展。本次按已落地契约接入，没有把键盘文字冒称为语音识别。后续 Wyman 若要收紧为另一版字段，需要一起做版本迁移。

节奏里的 `confidence` 是 **grid_alignment_heuristic**，不等于识别正确率。没有捏造 ASR 概率、BPM 区间或 pitch 精确度。当前节奏契约没有单独携带完整原始 onset 列表、tempo 候选区间；哼唱也仍以一段录音作为一次 phrase，并未声称完成自然多句切分。这些是下一阶段可扩展的感知字段。

`state_before` 是**事件已经 intake、计划已经形成、渲染尚未执行**时的快照；不是输入到达之前。preview 的 `state_after` 与它相等，表示渲染没有假装成功提交。MIDI 是 renderer 的 conditioning，不能当作生成 WAV 的反向转录。

## 5. 实际修改

- **哼唱 canonical event**：`web/optimized/src/input-event.js` 生成符合 1.2 的事件；页面下载与渲染共用该对象。沿用已有连续音解码、音高稳定和真实重新起音处理，不把旧清理算法当作本次新发明。
- **音频统一下游**：`input_band.render_clip` 支持 backend / preview，接入 `create_runtime`；新增 `/api/reference/input/render`。节奏 UI 的模式、力度、小节数作为明确的演示编排设置传入，没有写回 perception 结果冒充观测事实。
- **文字原文与证据**：只用 trim 判断是否空白，实际提交保留原文。响应和网页下载包含接受的 InputEvent、BandPlan、状态和 receipt。原有重试幂等逻辑继续通过测试。
- **现有页面控件**：哼唱和节奏结果面板增加 MRT2 backend 和 preview 开关；文字使用团队已有 backend 控件。保留录音、导入、示例、MIDI 试听及历史 handoff 导出。
- **本机运行**：新增 `start-input-mrt2.cmd` / `.ps1` 与 WSL 启动脚本，使用隔离的 WSL Python 环境及本机模型缓存。

历史 baseline 哼唱页面、`/rhythm/create` 和直接 MRT2 JSON 导出仍可用于旧实验复现；本报告验收的是 optimized 哼唱、rhythm、text-creation 三个主入口。

## 6. 验证和测量

完整证据在 [examples/input_mrt2](../../examples/input_mrt2/README.md)。各 JSON、MIDI 和 WAV 都来自实际测试，不是手工伪造成功样例。

| 检查 | 结果 | 证明范围 |
|---|---|---|
| Python 全套 | 466 passed | contracts、orchestration、runtime、错误路径、bridge 等；部分单测明确使用 `injected_test_double` |
| Node 单测 | 33 passed | 两个哼唱页面的处理/导出及历史 MRT2 handoff |
| 真实浏览器 NumPy 全链路 | 三入口通过 | 真实 perception/API/音频编码与播放，无模型替身 |
| 真实浏览器 MRT2 全链路 | 三入口通过 | 真实官方模型、CUDA 推理、事件来源、preview receipt、立体声 WAV 解码和播放时间前进 |
| 旧网页回归 | lifecycle、navigation、async、input-browser、creation-text、mrt2-input 均通过 | 录音释放、导航/延迟响应、原文/丢响应重试、MIDI 对齐与历史导出 |
| 模型资源 | 10/10 SHA-256 与团队清单一致 | 权重及依赖模型未拿错；见 model-verification.json |

首次 lifecycle 回归曾超时，补充诊断后重跑通过，没有改动录音逻辑；它使用虚拟麦克风，不代表真实设备覆盖。原有 creation-text 回归要求 FluidSynth，初次在不带该依赖的服务上无法选择 acoustic；用本机已有 FluidSynth 启动独立服务后通过。它的旧断言要求失败后继续显示旧音频，已随本次“清除旧结果”的明确行为更新。

最终由独立审查者检查代码、样例一致性、MIDI 哈希和状态语义，无 Critical/Important 问题。审查提到的播放时钟断言在最终验收中补齐，文档也明确区分了文字编辑与提交时的旧结果行为。人工麦克风、主观听感和物理扬声器不在此验收证据之内。

### 真实 MRT2 数据

硬件为 NVIDIA RTX 4050 Laptop，显存 6141 MiB；WSL Ubuntu，Python 3.12，`magenta-rt==2.0.3`，JAX / jaxlib / CUDA12 plugin `0.12.0.1`。启用 `XLA_PYTHON_CLIENT_PREALLOCATE=false`。三路复用一份模型，完成后一次观测显存占用约 4787 MiB；这不是精确峰值。包版本完整记录在环境 JSON 中。

| 输入 | 可核对的感知结果 | MRT2 调用耗时 | WAV |
|---|---|---:|---|
| 文字 `  来一段，慢一点\n` | 原文及空白保留；RuleAgent 生成 92 BPM 计划 | 62.94 s（首次，包括加载/编译） | 10.435 s、48 kHz、双声道 |
| 节奏示例 | 100.446 BPM；拍点 `[0,1,1.5,3]` | 5.69 s（已加载） | 9.557 s、48 kHz、双声道 |
| 哼唱示例 | MIDI `[60,64,67,64,62]`；旧碎片归并成 5 音 motif | 5.29 s（已加载） | 9.600 s、48 kHz、双声道 |

时间来自真实 receipt.elapsed_s，是模型调用，不含用户录音和全部 HTTP/前端时间。哼唱该次浏览器识别记录为 9.803 s；节奏合成 benchmark 的识别耗时见下。没有把不同设备、冷启动和热运行的数字拼成一个虚假的端到端平均延迟。

目前使用团队默认风格 prompt `a warm instrumental band`。文字先经 Harness 生成编排/MIDI，再作为 MRT2 条件；并非把任意原句直接交给 MRT2 理解。本次用 RuleAgent 完成，LLM 需要已有合法配置，未为它新增云调用。可用的文字命令受当前 Agent 支持范围限制。

### Perception benchmark 与失败模式

`scripts/benchmark_input_perception.py` 生成 4 类**合成**瞬态（clap-like、snap-like、tap-like、beatbox-like），各取 80/100/140 BPM。每例四拍定速加完整一小节，预期拍点 `[0,1,1.5,3]`。成功标准：事件合法、BPM 绝对误差 ≤3、16 分网格 pattern 完全一致。

- 12/12 通过；BPM 平均绝对误差 0.499、最大 0.750；网格 onset F1=1.0。
- Windows 识别冷启动首例 3.579 s；其余中位数 0.018 s、最大 0.046 s。这里没有 MRT2 推理。
- 静音、缺少完整小节两例均拒绝；低置信节奏在生成入口也被拒绝。另有 4 例 Unicode/换行/空白文字逐字保留。
- 哼唱单测覆盖持续音、短暂 dropout、抖动、同音真实重起音、八度变化及停顿；真实浏览器 Basic Pitch 对合成五音示例输出 5 音，对持续音示例输出 1 音。

**这不是人声、真实拍手、响指或口技的准确率。** 目前没有标注的人类录音集，不能用上述 100% 宣称真实输入成功率。下一批可复用评测应记录每位参与者/设备/噪声条件，并独立报告：哼唱 note precision/recall、音高误差、碎片数、误合并数及 phrase 边界误差；节奏原始 onset 容差 F1、倍速/半速错误率、pattern 稳定性；未来 ASR 的 CER/WER 与原文保留率。暂时不设置没有数据依据的上线准确率承诺。

当前主要失败边界：

| 模块 | 已知边界 | 当前行为/推荐 |
|---|---|---|
| 哼唱 | 噪声、复音、强颤音/滑音、呼吸与真实重起音难区分 | 保留源音频与原始帧证据；清理后可试听/下载，未知 confidence 为 null；短单声部 motif 最可靠 |
| phrase | 一段 capture 是一个 phrase；内部休止不等于多次自然轮次 | 后续再扩展自然 phrase segmentation，暂不加假边界 |
| 节奏 | 默认四拍定速、60–180 BPM、完整 4/4 小节；16 分网格无法完整表达 swing | 明确 UI 约束；提供原有手动 BPM/起点；低质量/不完整输入报错 |
| 文字 | 当前是键盘原文；没有 ASR 或自动 modality routing | source=text；保留原文；用现有 RuleAgent，未知指令明确失败 |
| MRT2 | 音高集合丢失声部/velocity/program，鼓条件是二值；每段模型上下文重建 | 保留 preview 标签，不声称精确复现；要检查精确 MIDI 用 NumPy/FluidSynth 路径 |
| 执行 | 单 GPU worker 串行；前端中止请求不会中止已开始的 GPU 运算 | 已处理旧响应覆盖问题；长推理仍可能等待，需查看日志或重启该服务 |

## 7. 现在怎么打开

在本次工作目录双击 **`start-input-mrt2.cmd`**。当前配置使用 WSL Ubuntu `/home/wenhan/jammate-mrt2-venv`，模型缓存放在 `E:\study documents\2026 Fall\AIAA 3800 HAI\runtime\Magenta`，不用重新下载。

打开 [本地工作台](http://127.0.0.1:4197/)，任选三个原入口：

1. 哼唱：载入示例 → 转成 MIDI → 结果面板选 MRT2、勾选 preview → 生成。
2. 节奏：载入示例 → 识别 → 结果面板选 MRT2、勾选 preview → 生成。
3. 文字：展开设置 → 选 MRT2、勾选 preview → 输入“来一段，慢一点”→ 生成。

首次模型生成需要约一分钟。生成后可下载 WAV、MIDI、标准事件与完整 trace；严格模式下的拒绝是能力检查结果。想要精确合成对照可切回原版合成器。

服务日志为 `tmp/mrt2-server.log`、`tmp/mrt2-server-errors.log`；`/api/ready` 返回当前检出根目录，启动器会拒绝误连其他目录占用的同一端口。该阶段只提供本机 loopback 服务。

### 可复跑命令

以下 PowerShell 命令在本次仓库根目录执行。已构建的网页和虚拟环境在本机准备好；不要在别的检出中直接运行相对命令。

```powershell
# 常规验证，不加载 MRT2
.\.venv\Scripts\python.exe -m pytest --basetemp=tmp/pytest-final
node --test web/baseline/tests/*.test.mjs web/optimized/tests/*.test.mjs tests/mrt2-input.test.mjs
.\.venv\Scripts\python.exe scripts/benchmark_input_perception.py

# 真实模型网页验收
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-input-mrt2.ps1 -NoBrowser
$env:INPUT_LAB_URL='http://127.0.0.1:4197'
$env:PLAYWRIGHT_MODULE_PATH="$PWD\tmp\browser-deps\node_modules\playwright"
$env:MRT2_REAL='1'
node tests/input-mrt2-browser.mjs
```

如果换一台机器，需要先构建 `web/baseline`、`web/optimized`，安装 Playwright/Edge，并在 Linux/WSL 安装官方运行环境。当前使用的包版本记录在 `examples/input_mrt2/wsl-packages.json`；Python 环境路径可由 `JAMMATE_MRT2_PYTHON` 覆盖，模型目录由 `MAGENTA_HOME` 覆盖。官方安装参考：[Magenta RT 安装说明](https://github.com/magenta/magenta-realtime/blob/694a545e4ba0b88bf1150137b129582166d3e07f/docs/installation.md)。本次安装使用 `magenta-rt==2.0.3` 和 `jax[cuda12]`，再执行 `mrt models init`、`mrt checkpoints download mrt2_small`；无需把权重提交到 Git。

## 8. 交接给 Wyman

直接复用 `examples/input_mrt2/real/*.input-event.json`；同名 trace 中有触发事件 ID、状态版本、BandPlan 与真实 receipt。需要重放 raw input 时使用 `inputs/`；节奏 benchmark 的 WAV、期望 pattern 和事件在 `benchmark/`。

下一轮对接的重点应是统一 schema 的正式版本和 session clock、跨输入共享会话、真实录音标注评测，以及 MRT2 preview 与可提交执行结果的产品边界。此次已完成现有三个入口到真实 MRT2 的本地接线，未把这些后续能力伪装成已经实现。
