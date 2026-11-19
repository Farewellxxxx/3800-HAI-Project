# JamMate

AIAA 3800 课程项目。JamMate 是一个本地音乐创作工作台，你可以哼一段旋律、拍一段节奏，或用一句话开始创作。三个入口都能单独生成乐队片段，支持浏览器试听、下载 WAV 和导出 MIDI。

本仓库的 `codex/full-workbench-20261118` 分支保留三个输入入口和完整的哼唱对比界面。体验输入编辑可运行 `start-input-lab.cmd`。需要连接已配置的 Harness / MRT2 环境时可运行 `start-input-mrt2.cmd`，详见[集成步骤](docs/integration/INPUT_MRT2_REPORT.md)和[输入输出样例](examples/input_mrt2/README.md)。

## 三种创作方式

| 入口 | 怎么试 | 生成结果 |
| --- | --- | --- |
| **从旋律出发** | 哼一句或载入示例，点「转成 MIDI」。在「对比版本」里切换默认短音过滤与旧版 D。点击音符可改起止时间、音高和力度，也可增删、撤销、试听。 | 点「确认旋律」后可下载本次确认的 MIDI 和 InputEvent。 |
| **从律动出发** | 录一段拍手或载入示例，点「识别节奏」。点击拍点可改时间、力度，也可增删和撤销。 | 试听当前节奏，导出对应的 MIDI 和 InputEvent。 |
| **从一句话出发** | 输入「来一段，慢一点」，生成后再输入「去掉贝斯」。 | 根据要求生成第一段，并沿用作品状态编排下一段。[第一段](examples/reference-creation/text-first.wav) · [调整后](examples/reference-creation/text-adjusted.wav) |

首页也提供独立的风格样段。[Lo-fi](examples/reference-creation/lofi.wav) · [Funk](examples/reference-creation/warm_funk.wav) · [Indie Rock](examples/reference-creation/indie_rock.wav)

## 在 Windows 上运行

已在 Python 3.12、Node.js 24 和 pnpm 11 上验证。装好 Git 和这些工具后，在 PowerShell 运行以下命令。工作台从 Git 历史读取固定版本，请完整克隆。评审 PR 时，把第一行替换为 PR 描述里的分支克隆命令。

```powershell
git clone --branch codex/full-workbench-20261118 https://github.com/Farewellxxxx/3800-HAI-Project.git
cd 3800-HAI-Project
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" -c requirements-input.lock.txt
pnpm --dir web/baseline install --frozen-lockfile
pnpm --dir web/baseline run build
pnpm --dir web/optimized install --frozen-lockfile
pnpm --dir web/optimized run build
.\start-input-lab.cmd
```

启动后在本机打开 [创作工作台](http://127.0.0.1:4188/)。以后可直接双击 `start-input-lab.cmd`。如果要在页面现生成风格样段，或使用 FluidSynth 音色，请先配置 FluidSynth。[音源配置与运行说明](docs/integration/RUN.md#音源与验收)

## 文字入口的大模型选项

本分支新增 FluidSynth / MRT2 执行适配与规则/LLM 共用入口。MRT2 生成试听会明确报告无法保证的保留约束，不提交未经验证的音乐状态；独立输入文件、运行命令和官方接口说明见 [MRT2 后端](docs/MRT2_BACKEND.md)。服务默认加载当前工作目录代码，使用 `--implementation pinned` 可复现历史版本。

文字页默认用本地规则，装好环境后，三个入口都能在本地试用。开启「队友大模型 Agent」后，模型根据文字和作品状态给出编排动作，例如「移除贝斯」。JamMate 校验动作，再生成具体音符和音频。

要启用大模型，在项目目录运行 `.\.venv\Scripts\python.exe -m pip install -e ".[llm]"`，配置自己的 `OPENAI_API_KEY`，或让 `JAMMATE_LLM_CONFIG` 指向仓库外的私有配置。重启服务后，在文字页选择「队友大模型 Agent」。[配置与验证说明](docs/integration/REFERENCE_WORKBENCH.md#大模型配置)

## 实现与来源

哼唱由 Spotify Basic Pitch 提取音符，接上我们的单声部整理和变奏。拍手与文字调用队友 `a63a0f5` 版本的节拍编排和文字 Agent。三种入口都按小节生成乐器音符，拍手使用原版内置合成器，哼唱和文字可以用 Kevin 渲染器及 FluidSynth 发声。[实现与验收](docs/integration/REFERENCE_WORKBENCH.md) · [团队原版命令行和研发记录](https://github.com/3123738092/aiaa3800_jammate/blob/a63a0f5f579cbc36ed0dfa31874c8888e4873cbd/README.md)
