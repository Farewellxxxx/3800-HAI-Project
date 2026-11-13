# 可复用的三路输入与输出

2026-11-14 本机实际运行产物。解释及启动步骤见 [完整报告](../../docs/integration/INPUT_MRT2_REPORT.md)。

| 目录 | 内容 |
|---|---|
| `inputs/` | 两段合成录音以及带首尾空白/换行的文字原文；没有个人麦克风录音 |
| `real/` | 官方 MRT2 实际生成；每一路有 `.input-event.json`、`.trace.json`、conditioning `.mid`、生成 `.wav`、网页 `.png`；report.json 包含浏览器解码/播放结果 |
| `precise/` | 相同示例走真实 NumPy 合成器的独立运行；事件 ID 不同，receipt=null，不冒充 MRT2 |
| `benchmark/` | 12 个合成节奏 WAV、对应标准事件、预期 pattern/BPM 与实测结果；并非人类准确率 |
| `model-verification.json` | 本机模型文件与团队提供的 SHA-256 清单逐项核对 |
| `windows-packages.json` / `wsl-packages.json` | 本次安装环境版本快照 |
| `validation.json` | Python JUnit 汇总、10 组 JS/浏览器日志和第二轮真实 MRT2 播放结果；第二轮强制断言播放时钟前进 |

可先试听：[文字](real/text.wav) · [节奏](real/rhythm.wav) · [哼唱](real/humming.wav)。这些是模型生成的 preview；MIDI 表示条件，不表示 WAV 被逐音符验证。

每个 InputEvent 可用 `jammate.contracts.InputEvent.from_dict(...)` 校验；下游使用 `event_id` 与 trace.plan.trigger_event_ids 对照。哼唱是 1.2.0 契约，节奏和文字是 1.0.0，均由同一团队 schema 支持。不要把 `confidence=null` 转成 1，也不要把节奏网格启发分数当成正确率。

重跑会产生新的 ID、时间戳、耗时，MRT2 音频也不保证逐字节相同。现存样例是一次运行的证据，测试应检查结构、来源、非静音及 receipt 语义，不应断言音频二进制固定。
