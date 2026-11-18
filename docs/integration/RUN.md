# 运行 JamMate 创作工作台

在已准备好的 Windows 工作区，双击根目录的 `start-input-lab.cmd`，打开 [创作工作台](http://127.0.0.1:4188)。三张卡片可以各自开始一次创作。默认启动当前工作区的实现。[工作台验收步骤](REFERENCE_WORKBENCH.md)

1. 打开「从旋律出发」。载入示例、导入短录音，或哼一句后点「转成 MIDI」。先试听识别结果，再点「生成音乐」，比较乐队怎样变奏。此入口以 100 BPM 和 C 大调开始编排。
2. 打开「从律动出发」。自由拍手、敲击或打口技，录制或导入 0.5–30 秒的音频，也可以载入示例。点「识别节奏」，在秒轴上选择拍点，修改起音时间或相对力度后保存，也可以添加、删除或撤销。点「听 MIDI」试听，下载当前 MIDI 和 InputEvent JSON。需要伴奏时，再展开「用当前节奏生成音乐」，选择跟随、加花或简化，让乐队编排整段输入。
3. 打开「从一句话出发」。先用「来一段，慢一点」生成第一段，再用「去掉贝斯」继续调整。配置模型时可选择队友大模型 Agent，也可显式选择队友本地规则。

每次生成使用当前输入。在「听创作结果」中播放、下载 WAV 或 MIDI。哼唱页的单轨旋律和自由节奏页的单轨打击乐可以直接试听、下载。作品 MIDI 在生成结果下方。想保留录音或结果时，在离开页面前下载。

要把旋律、当前编辑后的节奏或原文交给 MRT2 接入端，请使用页面的导出按钮。旧版交接流程图和调用示例见 [MRT2 输入交接](MRT2_INPUT_HANDOFF.md)。

## 新电脑安装

本次在 Windows、Python 3.12、Node 24 和 pnpm 11.25 上验证。克隆仓库后，在仓库根目录打开 PowerShell 并运行以下命令。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" -c requirements-input.lock.txt
pnpm --dir web/baseline install --frozen-lockfile
pnpm --dir web/baseline run build
pnpm --dir web/optimized install --frozen-lockfile
pnpm --dir web/optimized run build
.\start-input-lab.cmd
```

服务只监听 `127.0.0.1`，启动器默认用 4188 端口。需要在终端查看日志时可运行 `.\.venv\Scripts\python.exe -m jammate.input_server --port 4188`。本地规则、自由节奏和哼唱可离线使用。

## 音源与验收

内置 NumPy 合成器可直接生成声音。要使用 Kevin 的 MIDI / FluidSynth 渲染，在启动服务前将 FluidSynth 放入 PATH，或将 `JAMMATE_FLUIDSYNTH` 设置为其可执行文件的完整路径。默认音色库为 pretty_midi 附带的 TimGM6mb，可通过 `JAMMATE_SOUNDFONT` 指定其他 SF2。本机启动器也会使用工作区内已准备好的 FluidSynth 2.6.1。更换配置后需重新启动服务。

[新版示例](../../examples/reference-creation/)与[验收记录](REFERENCE_WORKBENCH.md)说明实际验证过的行为和待验项。[上一版样例](../../examples/creation/)仍可回看。

运行浏览器验收需要 Edge 和 Playwright。如果 Playwright 安装在其他目录，设置 `PLAYWRIGHT_MODULE_PATH` 为其 npm 包路径。运行完整渲染器测试还需要 Python 的 `google-genai` 和 `python-dotenv`。以下命令从仓库根目录执行，先启动工作台：

```powershell
$env:PYTHONPATH = ".;src;renderer_experiments"
$env:INPUT_LAB_URL = "http://127.0.0.1:4188"
.\.venv\Scripts\python.exe -m pytest tests renderer_experiments/tests --basetemp=tmp/pytest-review
node --test tests/*.test.mjs web/baseline/tests/*.test.mjs web/optimized/tests/*.test.mjs
node tests/input-browser.mjs
node tests/input-lifecycle.mjs
node tests/input-navigation.mjs
node tests/input-async-browser.mjs
node tests/creation-text-browser.mjs
```

浏览器验收使用合成音频和模拟录音权限。脚本回读 MIDI 和 WAV，检查编辑后的起音和相对力度、编排是否覆盖整段节奏、旋律变化、文字改变速度，以及切换入口和失败重试。真人麦克风效果和音乐听感需另行试听。

10 月 28 日的[旧输入格式](INPUT_EVENT.md)、[优化记录](ITERATIONS.md)和[识别对比附录](http://127.0.0.1:4188/appendix.html)可供回溯。当前传给乐队的文档按[新版契约](../INPUT_EVENT_V1.md)校验。
