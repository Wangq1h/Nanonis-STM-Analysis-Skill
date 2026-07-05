<div align="center">
  <img src="assets/stm-agent-icon.png" alt="STM Analysis Agent icon" width="132">

  <h1>STM/SJTM 数据处理 Agent Skill</h1>

  <p><strong>从 Nanonis 原始文件到论文级 STM 图：数据契约、审批门禁和可复现 evidence package 都内置在工作流里。</strong></p>

  <p>
    <a href="README.md"><img alt="Language: English" src="https://img.shields.io/badge/lang-English-2563eb"></a>
    <a href="README.zh-CN.md"><img alt="Language: Simplified Chinese" src="https://img.shields.io/badge/lang-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-c2410c"></a>
    <img alt="Release v0.2.4" src="https://img.shields.io/badge/release-v0.2.4-64748b">
    <img alt="STM STS SJTM" src="https://img.shields.io/badge/domain-STM%20%2F%20STS%20%2F%20SJTM-0f766e">
    <img alt="PySIDAM backed" src="https://img.shields.io/badge/PySIDAM-backed-7c3aed">
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

这个仓库提供一个可移植的 agent skill，用于扫描隧道显微镜（STM）、扫描隧道谱（STS）和 superconducting-tip STM（SJTM）数据处理。它帮助 agent 在可用时调用 PySIDAM，确认单位和坐标轴，给关键科学参数加审批门禁，并把结果打包成图、表、脚本和机器可读的 provenance。

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

## 它能帮 Agent 做什么

- **安全读取原始数据**：检查 `.3ds`、`.sxm`、`.dat`、`.ibw`、`.csv`、`.tsv` 和文本谱线，不把私有原始数据复制进 skill 仓库。
- **固定数据契约**：记录 shape、axis order、bias 单位、divider、scan size、坐标系、通道、flip、transpose、mask 等。
- **优先使用 PySIDAM**：能走 PySIDAM 或 headless bridge 的 Nanonis IO、gap fitting、Bragg/QPI lock-in、原子识别和 DW mask，就不重新造轮子。
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

如果没有可用缓存环境：

```bash
python3 scripts/bootstrap_runtime.py --groups headless
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
- GitHub Release: release notes 位于 `RELEASE_NOTES_v*.md`，当前 release line 跟随最新版本 release note。

## 与 PySIDAM 的关系

`pysidam` 是优先使用的实现来源。这个仓库围绕它补充 agent-facing 工作流规则、审批门禁、运行环境探测、bridge 脚本和报告约定。目标是让 agent 用对科学工具，并留下足够证据，让另一个研究者可以审计结果。
