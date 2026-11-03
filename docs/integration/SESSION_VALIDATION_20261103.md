# 会话工作台验收记录 · 2026-11-03

基础版本 `1c7dc7a`；本轮依次提交生命周期/样例、会话执行服务、网页/重放，以及独立审查修复。工作分支 `integration/input-band`，没有合并 main 或修改 upstream。

## 已运行的自动验证

- 修改前：Python 424、JavaScript 30 通过。
- 最终审查修复后：Python **456 passed，26.97 s**；JavaScript **30 passed**。Python 命令覆盖 `tests` 与 `renderer_experiments/tests`，本次没有排除测试；没有真实 LLM 请求。
- 哼唱固定样例：持续音、重复音、换音、休止、短音、轻声、背景噪声共七组。优化版音序均符合预期；最大匹配音符边界误差约 58.4 ms。对照与参数见 [humming-20261103.json](humming-20261103.json)。
- 网页构建：baseline 和 optimized 的 pnpm build 成功。
- 最终用户服务 `127.0.0.1:4185` 上六组浏览器脚本全部通过：`input-navigation`、`input-async-browser`、`input-lifecycle`、`input-browser`、`session-browser`、`session-edge-browser`。
- 旧网页完整链路：真实 Basic Pitch、节拍识别、原录音/MIDI/伴奏互斥播放、重复转换、音色切换、失败重试、MIDI/JSON 对应、WAV 解码和移动宽度。
- 导航/生命周期：权限待定与拒绝、虚拟麦克风停止、实际 MediaRecorder 意外停止、坏文件恢复、缓存页面媒体保留、旧权限不解锁新申请。
- 新会话：真实识别后的节拍+哼唱组合、显式 C 大调、采用节拍速度、加强鼓、关闭/恢复贝斯、未知指令原子拒绝、手动 120 BPM 与 0.1 秒/2 拍偏移、未知调性无贝斯和键盘、新会话保留输入页原录音、移动页面无横向溢出。
- 新会话边界：真实请求成功后故意丢弃响应，再以原 request_id 重试，状态版本不重复递增；迟到响应不展示；旧结果文字标记为历史；输入区域在手机宽度完整显示。
- 新异步回归：持有真实 rhythm API 响应，模拟页面离开/返回并替换音频，释放旧响应不能重新发布旧素材；三个输入页均测试延迟解码不能恢复已移除音频。
- 保存记录重放：从 FluidSynth 生成的下载 JSON，用内置合成器重放累积的鼓力度调整；完整状态相同，按乐器角色核对每个音符的音高、力度和起止，误差小于 3 ms。两套渲染器的轨名/音色不同，未以文件字节相同作为判据。
- 最终真实 HTTP/FluidSynth 补查：20 秒、120 BPM 的组合输入生成十小节；再执行“主旋律保持”和“节奏保持”，所有乐器音符、力度和起止不变。MIDI 结束事件为 20.0 秒，WAV 含尾音为 22.372 秒。初次探针用 `pretty_midi.get_end_time()` 得到最后音符结束 19.875 秒，改用包含 `end_of_track` 的 `mido.MidiFile.length` 核对文件完整时长；无需修改渲染代码。

## 独立审查及修复

独立只读审查覆盖 `1c7dc7a..0603eb2`，给出三个 Important 和一个 Minor；没有 Critical。随后一次修复批次补齐失败回归并通过上述完整 Python/JS 回归：

| 发现 | 修复与证据 |
|---|---|
| 返回页面后旧异步识别覆盖新输入 | 操作代次、输入快照、发布/清理校验；真实响应/解码延迟浏览器用例先失败后通过 |
| 组合节拍的 preserve 与临时默认节奏冲突 | 保留已提交的节奏作参照；四种保持/增强文字用例核对实际音符 |
| 长尾休止被四小节默认长度截断 | 按映射后的原录音结束时间确定小节数；20 秒/120 BPM 用例为十小节，WAV/MIDI 均覆盖 20 秒；超限拒绝 |
| 主旋律保持被过宽的动作过滤拒绝 | 依据用户要求将其视为应修复的指令行为；允许 PRESERVE，并与 canonical 输入旋律比较，音高/起止/力度保持 |

没有安排重复独立审查；修复以新增失败回归转绿和完整回归为依据。

## 可检查的产物

- [组合输入 WAV](../../examples/session_band/combined.wav)、[MIDI](../../examples/session_band/combined.mid)、[记录 JSON](../../examples/session_band/combined.json)。
- [加强鼓 WAV](../../examples/session_band/strong-drums.wav)、[MIDI](../../examples/session_band/strong-drums.mid)、[记录 JSON](../../examples/session_band/strong-drums.json)。
- [会话浏览器结果](../../examples/session_band/browser-report.json)。所有提交音频都是合成示例，不含私人录音。
- [操作、重放和真人验收步骤](SESSION.md)。

## 实施取舍与证据边界

- 使用现有独立 worktree 和原生 PowerShell 执行/记录任务；临时台账位于忽略目录，不要求安装 bash 工具链。
- 每版从第 0 小节重新导出，并沿用上次成功的声部状态；这是可比较的离线修订，未构建实时 transport。
- 规则文本能力有明确范围；没有配置或调用真实 LLM。已有模拟 API 回归不等于真实 API 验收。
- 浏览器返回场景通过合成 PageTransitionEvent 构造；未证明每种浏览器都会让该页面进入 BFCache。
- 未提供真人录音，也未做物理声卡、真实麦克风、音乐听感或现场延迟验收。合成样例不能用于声称真人准确率；调性阈值不是校准置信度。默认规则和弦仍需听感评价。
