# STM/SJTM Data Processing Agent Skill

**From raw Nanonis files to paper-ready figures, with an agent that keeps the data contract, asks before sensitive choices, and leaves a reproducible evidence trail.**

[English](#english) | [中文](#中文) | [Tutorial](docs/tutorials/agent-guided-stm-data-analysis.md) | [Wiki](https://github.com/Wangq1h/Nanonis-STM-Analysis-Skill/wiki)

This repository contains a portable agent skill for scanning tunneling microscopy (STM), scanning tunneling spectroscopy (STS), and superconducting-tip STM (SJTM) data processing. It helps agents route work to PySIDAM where available, confirm units and axes, enforce approval gates for scientifically sensitive choices, and package results as figures, tables, scripts, and machine-readable provenance.

---

## English

### STS Figure Extraction in Action

![STS figure extraction chat demo](assets/sts-agent-chat-demo.png)

> **Researcher:**
> “Look at `raw_data/`. The files `001-005.dat` are superconducting spectra taken at different temperatures. The temperatures should be in the headers. Use the STM skill, read the data, and make a clean figure that can go into a paper.”

Seven minutes later, the agent comes back with a compact, auditable result:

- read the temperatures from each file header: `4.2 K`, `1.35 K`, `1.1 K`, `0.92 K`, `0.35 K`;
- selected `LI Demod 1 X (A)`, aligned forward/backward sweeps, converted bias to `mV` and signal to `pA`;
- normalized the main plot by the average signal in `|V| = 8-10 mV`;
- made a vertically offset stacked spectrum figure without smoothing;
- exported paper-facing `PDF`, `SVG`, `PNG`, and `TIFF`;
- saved `processed_spectra.csv`, `paper_figure_provenance.json`, and the rerunnable script;
- reran the script from scratch and verified all outputs were nonempty.

That is the intended feel of this skill: not a black box that says “done”, but a careful lab assistant that shows what it read, what it changed, which choices stayed auditable, and where every output lives.

### What it helps agents do

- **Read raw files safely**: inspect `.3ds`, `.sxm`, `.dat`, `.ibw`, `.csv`, `.tsv`, and text spectra without copying private data into the skill repository.
- **Preserve data contracts**: record shape, axis order, bias units, divider, scan size, coordinate frame, selected channels, flips, transposes, and masks.
- **Use PySIDAM where possible**: route Nanonis IO, gap fitting, Bragg/QPI lock-in, atom detection, and domain-wall masks through existing headless tools or thin bridge scripts.
- **Stop for approval when it matters**: require user approval for agent-selected fit windows, q vectors/filter sigma, and multipeak peak counts.
- **Package evidence**: save `report.json`, NPZ arrays, CSV tables, figures, approval records, warnings, and rerunnable commands.
- **Keep interpretation cautious**: separate measured results from physical claims such as YSR states, topological modes, strain correlations, or phase jumps.

### Quick Start

For a new STM/SJTM analysis thread, start with a prompt like:

```text
Use the stm-sjtm-data-processing skill.

Workspace:
/path/to/stm-workspace

Read:
/path/to/stm-workspace/data_manifest.json
/path/to/stm-workspace/outputs/initial_file_inventory.json

Raw data are referenced through raw_data. Do not copy raw data into the skill repo.

First confirm file shapes, axis order, bias unit/divider, channels, scan size,
pixel size, coordinate frame, and origin convention.

If you need to choose a fit window, q vector/filter sigma, or peak count,
write approval_proposal.json first and wait for my approval before execution.
```

For local runtime checks:

```bash
python3 scripts/resolve_runtime.py --probe
```

If no cached runtime is ready:

```bash
python3 scripts/bootstrap_runtime.py --groups headless
```

Common bridge commands:

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

### Tutorials and references

- [Agent-guided STM Data Analysis](docs/tutorials/agent-guided-stm-data-analysis.md)
- [GitHub Wiki](https://github.com/Wangq1h/Nanonis-STM-Analysis-Skill/wiki)
- [Workflow reference](references/workflow.md)
- [Data contracts](references/data-contracts.md)
- [Quality checks](references/quality-checks.md)
- [Approval gates](references/approval-gates.md)
- [PySIDAM capability map](references/pysidam-capability-map.md)

### Skill Installation

Copy or synchronize this repository root into the skill directory used by your agent runtime.

For local development, prefer:

```bash
python3 scripts/sync_installed_skill.py
```

### Validation

```bash
python3 scripts/validate_package.py
```

Expected:

```text
PASS: stm-sjtm-data-processing package is structurally valid
```

### Developer Reference

- Runtime manifest: `runtime/requirements-core.txt`
- Runtime probe script: `scripts/probe_runtime.py`
- Quick task cards: `references/task-cards/sts-dat-quick.md`, `references/task-cards/gap-fit-quick.md`
- Capability index: `references/pysidam-capability-index.json`
- Other Agent Runtimes: read this README first, then load the workflow, data-contract, and domain references needed for the task.
- GitHub Release: release notes live in `RELEASE_NOTES_v*.md`; the current release line follows the latest versioned release note.

---

## 中文

### STS 论文图提取场景

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

### 它能帮 agent 做什么

- **安全读取原始数据**：检查 `.3ds`、`.sxm`、`.dat`、`.ibw`、`.csv`、`.tsv` 和文本谱线，不把私有原始数据复制进 skill 仓库。
- **固定数据契约**：记录 shape、axis order、bias 单位、divider、scan size、坐标系、通道、flip、transpose、mask 等。
- **优先使用 PySIDAM**：能走 PySIDAM 或 headless bridge 的 Nanonis IO、gap fitting、Bragg/QPI lock-in、原子识别和 DW mask，就不重新造轮子。
- **关键参数先审批**：agent 自己选择 fit window、q vector/filter sigma、peak count 时，先生成 `approval_proposal.json`，等用户确认后再执行。
- **输出 evidence package**：保存 `report.json`、NPZ、CSV、图、审批记录、warnings 和可复现命令。
- **物理解读保持克制**：把测量结果和物理解释分开，避免仅凭 gap filling、相位图或应变 proxy 就做过强结论。

### 快速开始

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

### 教程和参考

- [Agent-guided STM Data Analysis](docs/tutorials/agent-guided-stm-data-analysis.md)
- [GitHub Wiki](https://github.com/Wangq1h/Nanonis-STM-Analysis-Skill/wiki)
- [工作流参考](references/workflow.md)
- [数据契约](references/data-contracts.md)
- [质量检查](references/quality-checks.md)
- [审批门禁](references/approval-gates.md)
- [PySIDAM 能力图](references/pysidam-capability-map.md)

### Skill 安装

复制或同步本仓库到你的 agent runtime 所使用的 skill 目录。

本地开发时推荐：

```bash
python3 scripts/sync_installed_skill.py
```

### 校验

```bash
python3 scripts/validate_package.py
```

期望输出：

```text
PASS: stm-sjtm-data-processing package is structurally valid
```

## Relationship to PySIDAM

`pysidam` is treated as the preferred implementation source. This repository adds agent-facing workflow rules, approval gates, runtime probing, bridge scripts, and reporting conventions around it. The goal is to help an agent use the right scientific tool and preserve enough evidence for another researcher to audit the result.
