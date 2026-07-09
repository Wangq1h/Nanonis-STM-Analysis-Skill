<div align="center">
  <img src="assets/stm-agent-icon.png" alt="STM Analysis Agent icon" width="132">

  <h1>STM/SJTM 数据处理 Agent Skill</h1>

  <p><strong>从 Nanonis 原始文件到论文级 STM 图：数据契约、审批门禁和可复现 evidence package 都内置在工作流里。</strong></p>

  <p>
    <a href="README.md"><img alt="Language: English" src="https://img.shields.io/badge/lang-English-2563eb"></a>
    <a href="README.zh-CN.md"><img alt="Language: Simplified Chinese" src="https://img.shields.io/badge/lang-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-c2410c"></a>
    <img alt="Release v3.0.1" src="https://img.shields.io/badge/release-v3.0.1-64748b">
    <img alt="STM STS SJTM" src="https://img.shields.io/badge/domain-STM%20%2F%20STS%20%2F%20SJTM-0f766e">
    <img alt="AnalySTM backend" src="https://img.shields.io/badge/backend-AnalySTM-7c3aed">
    <img alt="Evidence package" src="https://img.shields.io/badge/output-evidence%20package-0369a1">
  </p>

  <p>
    <a href="docs/tutorials/agent-guided-stm-data-analysis.md">教程</a>
    · <a href="https://github.com/Wangq1h/Nanonis-STM-Analysis-Skill/wiki">Wiki</a>
    · <a href="references/workflow.md">工作流</a>
    · <a href="references/data-contracts.md">数据契约</a>
    · <a href="references/approval-gates.md">审批门禁</a>
  </p>
</div>

---

![STS 论文图提取对话示例](assets/sts-agent-chat-demo.png)

这个仓库提供一个可移植的 agent skill，以及 public installable 的 AnalySTM 3.0 后端，用于扫描隧道显微镜（STM）、扫描隧道谱（STS）和 superconducting-tip STM（SJTM）数据处理。它帮助 agent 读取原始数据、确认单位和坐标轴、运行公开可安装的 headless 后端、给关键科学参数加审批门禁，并把结果打包成图、表、脚本和机器可读的 provenance。

## 为什么需要这个 Skill

STM 数据分析里很多小选择都会影响结果：通道名、bias 单位、扫向、gap window、q vector、mask、归一化区间。这个 skill 让 agent 先建立数据契约，再对敏感参数提出建议，最后返回另一个研究者可以审计和复跑的图与证据包。

## STS 论文图提取场景

> **研究者：**
> “看一下 `raw_data/`。`001-005.dat` 是不同温度下测的超导谱，温度应该写在 header 里。使用 STM skill 读取数据，并画一张可以放进论文的高清图。”

大约几分钟后，agent 返回的不是一句空泛的“已完成”，而是一组可追溯的结果：

- 从每个文件 header 读出温度：`4.2 K`、`1.35 K`、`1.1 K`、`0.92 K`、`0.35 K`；
- 使用 `LI Demod 1 X (A)`，对齐 forward/backward sweep，将 bias 转成 `mV`，信号转成 `pA`；
- 主图按 `|V| = 8-10 mV` 的平均值归一化；
- 输出一张垂直错开的 stacked spectrum 图，没有平滑；
- 导出论文图常用的 `PDF`、`SVG`、`PNG`、`TIFF`；
- 同时保存 `processed_spectra.csv`、`paper_figure_provenance.json` 和可复跑脚本；
- fresh rerun 验证通过，输出文件非空。

这就是这个 skill 希望提供的体验：它不是一个直接替你下结论的黑盒，而是一个谨慎的实验助理。它会告诉你读了什么、改了什么、哪些选择保留为可审计参数、图和数据保存在哪里，以及这次结果怎样复现。

## 审批门禁场景

同样的工作模式在 Bragg/QPI 分析里更关键。像“红框里的 qB 峰可能更像 Bragg peak”这种模糊指令，不能直接等价为“开始跑 phase analysis”。agent 会先把它解析成 `q_selection` gate：提出从 ROI 得到的 q vector，展示 FFT 证据，列出风险，然后等用户批准或修改关键科学参数。

<p align="center">
  <img src="assets/scenario-qb-red-peak-correction.png" alt="Bragg lock-in 的 q-vector approval 工作流" width="920">
</p>

在这个场景里，用户可以用很自然的方式确认选择：接受红框局部最大、直接给出 q vector，或者修改 lock-in filter。只有在这些选择写入 `approval_decision.json` 后，agent 才继续执行 qB lock-in 并输出 phase maps、masked distributions 和 plus/minus consistency。

## 相位显示场景

相位图也有自己的陷阱。当 continuous display profile 看起来像接近 `2π` 的跳变时，这个 skill 会要求 agent 把显示伪影和物理解释分开：绘图时可以断开 branch-cut bins，避免画出误导性的尖峰；但底层 phase data 和左右 domain 的圆统计仍然保留为可审计结果。

<p align="center">
  <img src="assets/scenario-phase-branch-cut.png" alt="branch-cut aware Bragg phase display" width="920">
</p>

这个区分是刻意的。agent 可以改进图的呈现方式，让它不暗示虚假的 spike；但不能把 wrapped-phase branch cut 直接包装成物理 phase jump。

## 它能帮 Agent 做什么

- **安全读取原始数据**：检查 `.3ds`、`.sxm`、`.dat`、`.ibw`、`.csv`、`.tsv` 和文本谱线，不把私有原始数据复制进 skill 仓库。
- **固定数据契约**：记录 shape、axis order、bias 单位、divider、scan size、坐标系、通道、flip、transpose、mask 等。
- **优先使用 AnalySTM**：新分析默认走 `analystm` headless 后端；PySIDAM 保留为开发参考、source mapping 和 legacy fallback。
- **关键参数先审批**：agent 自己选择 fit window、q vector/filter sigma、peak count 时，先生成 `approval_proposal.json`，等用户确认后再执行。
- **输出 evidence package**：保存 `report.json`、NPZ、CSV、图、审批记录、warnings 和可复现命令。
- **物理解读保持克制**：把测量结果和物理解释分开，避免仅凭 gap filling、相位图或应变 proxy 就做过强结论。

## 快速开始

新的 STM/SJTM 分析线程可以这样开头：

```text
使用 stm-sjtm-data-processing skill。

实验工作区：
/path/to/stm-workspace

请先读取：
/path/to/stm-workspace/data_manifest.json
/path/to/stm-workspace/outputs/initial_file_inventory.json

原始数据通过 raw_data 引用，不要复制进 skill 仓库。

先确认文件 shape、axis order、bias unit/divider、通道、scan size、
pixel size、coordinate frame 和 origin convention。

如果需要由 agent 选择 fit window、q vector/filter sigma 或 peak count，
必须先写 approval_proposal.json，等我确认后再执行。
```

运行环境检查：

```bash
python3 scripts/resolve_runtime.py --probe
```

默认检查只覆盖 AnalySTM/headless 运行时：`analystm`、数值依赖、`nanonispy` 和 `igorwriter`。它不会把 PySIDAM、PyQt5 或 pyqtgraph 当成缺失依赖；AI 原子识别 detector 目前显示为 planned integration。

如果没有可用缓存环境：

```bash
python3 scripts/bootstrap_runtime.py --groups headless
```

这个 headless 环境只安装 `core + nanonis + ibw`。只有显式测试未来 AI detector 接入时才使用 `--groups headless,ai`；只有显式做 PySIDAM regression 时才使用 `--pysidam-mode auto --pysidam-root /path/to/pysidam`。

## AnalySTM Backend

AnalySTM 是这个 skill 的公开 headless 后端。安装后可以通过 Python API `import analystm` 使用，也可以通过 `analystm` CLI 运行 agent workflow。

本地开发检查：

```bash
python3 -m analystm --help
```

常用 `analystm` 后端命令：

```bash
analystm read data/example.dat --quick --output-json outputs/read_summary.json
analystm plot-spectrum data/example.dat --output outputs/spectrum.png --summary-json outputs/spectrum.json
analystm fit-gap data/example.dat --model "Two Band s-wave" --output-dir outputs/gap_fit
analystm bragg policy --output-json outputs/q_policy.json
analystm phase-lockin data/topo.npy --scan-size-nm 20 20 --q q1=1.5,0.0 --output-dir outputs/phase_lockin
analystm gap-map data/cube.npz --left-window -2.5 -0.5 --right-window 0.5 2.5 --output-dir outputs/gap_map
analystm intensity process data/linecut.npz --mode neg_d3 --bias-range -2 2 --output-dir outputs/intensity
analystm waterfall fit data/linecut_cube.npz --linecut 0 64 127 64 --neg-range -1.2 -0.4 --pos-range 0.4 1.2 --output-dir outputs/waterfall
analystm qpi symmetry data/qpi_stack.npz --order 4 --output-dir outputs/qpi_symmetry
analystm qpi 1d-fft data/qpi_cube.npz --scan-size-nm 20 20 --p1 2 10 --p2 18 10 --cube-order xyb --output-dir outputs/qpi_1d_fft
analystm qpi fft-filter data/qpi_cube.npz --scan-size-nm 20 20 --circle 1.5 0.0 0.2 --output-dir outputs/qpi_fft_filter
analystm spectroscopy process data/spec.npz --x-key bias --y-key didv --auto-offset --norm-mode Max --output-dir outputs/spectroscopy
analystm topography lf-drift data/topo.npz --q1 1.0 0.0 --q2 0.0 1.0 --output-dir outputs/topography_lf
analystm topography display-fft data/topo.npz --scan-size-nm 20 --window Hanning --scale-mode Log --output-dir outputs/topography_display_fft
analystm topography fft-filter data/topo.npz --scan-size-nm 20 20 --circle 1.5 0.0 0.2 --output-dir outputs/topography_fft_filter
analystm histogram data/map.npz --data-key topo --background-mode "Sub Plane (Global)" --output-dir outputs/histogram
analystm crop map data/grid.npz --data-key cube --kind 3ds --center-px 128 128 --side-px 96 --scan-size-nm 20 20 --output-dir outputs/crop
analystm path-viz build path_batches.json --output-dir outputs/path_viz
analystm publication payload data/figure_payload.npz --image-key image --x-key x --y-key y --output-dir outputs/publication
analystm export spec-dat data/spectrum.npz --column "Bias calc (V)=bias" --column "LI Demod 1 X (A)=didv" --output outputs/spectrum.dat
analystm sjtm data/sjtm_cube.npz --neg-window -1.1 -0.35 --pos-window 0.35 1.1 --rn-window 1.2 2.2 --g0-window -0.2 0.2 --ic-fit-mode accurate --output-dir outputs/sjtm
analystm deconvolve data/sis_point.npz --mode sis --temperature-k 0.4 --tip-delta-mev 1.2 --tip-gamma-mev 0.03 --output-dir outputs/deconvolution
analystm atom recommend-scale --shape-yx 512 512 --scan-size-nm 20 20 --resize-ratio 1.5 --expected-spacing-nm 0.3515625
analystm domain-wall build-masks --shape-yx 128 128 --scan-size-nm 30 30 --regions-json dw_regions.json --near-width-nm 1.0 --output-dir outputs/domain_wall
```

常用 bridge 命令：

```bash
python3 scripts/pysidam_agent/read_file.py --quick data/example.dat --output-json outputs/read_summary.json
python3 scripts/pysidam_agent/plot_spectrum.py data/example.dat --output outputs/spectrum.png --summary-json outputs/spectrum.json
python3 scripts/pysidam_agent/fit_gap.py data/example.dat --model "Two Band s-wave" --output-dir outputs/gap_fit
python3 scripts/pysidam_agent/bragg_phase.py policy
python3 scripts/pysidam_agent/bragg_phase.py inspect-roi data/topo.sxm --roi -0.5 0.5 2.0 3.0 --output-json outputs/q_roi.json
python3 scripts/pysidam_agent/phase_lockin.py run data/topo.npy --scan-size-nm 20 20 --q q1=1.5,0.0 --output-dir outputs/phase_lockin
python3 scripts/pysidam_agent/atom_ai.py recommend-scale --shape-yx 512 512 --scan-size-nm 20 20 --resize-ratio 1.5 --expected-spacing-nm 0.3515625
python3 scripts/pysidam_agent/domain_wall.py build-masks --shape-yx 128 128 --scan-size-nm 30 30 --regions-json dw_regions.json --near-width-nm 1.0 --output-dir outputs/domain_wall
```

## Skill 安装

复制或同步本仓库到你的 agent runtime 所使用的 skill 目录。

本地开发时推荐：

```bash
python3 scripts/sync_installed_skill.py
```

## 校验

```bash
python3 scripts/validate_package.py
```

期望输出：

```text
PASS: stm-sjtm-data-processing package is structurally valid
```

## Other Agent Runtimes

不支持 Codex skill 的 agent 可以直接读取这个仓库：先读 `README.md` 或 `README.zh-CN.md`，再按任务加载 `references/workflow.md`、`references/data-contracts.md` 和具体领域参考。新工作优先调用 `analystm`，只有做 PySIDAM regression 或历史兼容检查时才使用 `scripts/pysidam_agent/*`。

## GitHub Release

Release notes 位于 `docs/releases/`，当前 release line 跟随最新版本 release note。

## 参考

- [Agent-guided STM Data Analysis](docs/tutorials/agent-guided-stm-data-analysis.md)
- [GitHub Wiki](https://github.com/Wangq1h/Nanonis-STM-Analysis-Skill/wiki)
- [工作流参考](references/workflow.md)
- [数据契约](references/data-contracts.md)
- [质量检查](references/quality-checks.md)
- [审批门禁](references/approval-gates.md)
- [PySIDAM 能力图](references/pysidam-capability-map.md)

## 开发者参考

- Runtime manifest: `runtime/requirements-core.txt`
- Runtime probe script: `scripts/probe_runtime.py`
- Quick task cards: `references/task-cards/sts-dat-quick.md`, `references/task-cards/gap-fit-quick.md`
- Capability index: `references/pysidam-capability-index.json`
- Other Agent Runtimes: 先读 README，再按任务加载 workflow、data-contract 和领域参考。
- GitHub Release: release notes 位于 `docs/releases/`，当前 release line 跟随最新版本 release note。

## 与 PySIDAM 的关系

`pysidam` 现在是开发参考和 legacy fallback，而不是公开运行时硬依赖。默认 probe 和 bootstrap 都不再检查、安装或克隆 PySIDAM，也不需要 PyQt5/pyqtgraph。新报告应把执行引擎记录为 `analystm.*`；PySIDAM 函数名只应出现在 `pysidam_source_mapping` 等审计字段里。这个仓库保留 `pysidam_agent_core/` 和 `scripts/pysidam_agent/`，用于历史兼容、source mapping 和显式 regression 对比。AI detector 是待接入项；当前公开能力是 `analystm atom` 的 scale guidance、lattice QC 和 wipe-region 工具。
