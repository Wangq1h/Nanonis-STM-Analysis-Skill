# Agent-guided STM Data Analysis

This tutorial shows how to use an AI agent as an auditable STM/STS analysis assistant. The goal is not to let the agent jump directly to a physical conclusion. The better pattern is:

1. confirm the data contract;
2. ask the agent to propose sensitive parameters with evidence;
3. approve or modify those parameters;
4. run the analysis through PySIDAM or a headless bridge where possible;
5. save a reproducible evidence package with machine-readable provenance.

The examples below are written generically so the workflow can be reused on new Nanonis `.3ds`, `.sxm`, `.dat`, `.csv`, or `.txt` datasets.

## When to use this workflow

Use this workflow when the task involves:

- reading raw STM/STS files and confirming shape, axes, units, channels, scan size, and pixel size;
- extracting gap maps, peak maps, in-gap intensity maps, or representative spectra from STS cubes;
- extracting Bragg/QPI lock-in phase or lattice-displacement proxies from topography;
- comparing topography, Bragg phase, atom sites, gap maps, in-gap maps, and deformation proxies;
- producing a report with provenance, quality checks, figures, tables, and cautious scientific interpretation.

## Starter prompt

Use a prompt like this when starting a new analysis thread.

```text
Use the stm-sjtm-data-processing skill.

Workspace:
/path/to/stm-workspace

Please read first:
/path/to/stm-workspace/data_manifest.json
/path/to/stm-workspace/outputs/initial_file_inventory.json

Raw data are referenced through the raw_data symlink.
Do not copy raw data into the skill or tutorial repository.

First probe the runtime and confirm:
1. raw file shape, axis order, bias axis, bias unit, and divider;
2. topography and spectroscopy channel choices;
3. scan size, pixel size, coordinate frame, and origin convention;
4. where every quantitative parameter will be recorded in report.json.

If the agent needs to choose a fit window, q vector/filter sigma, or peak count,
create approval_proposal.json and a review figure first.
Wait for user approval before executing.

Prefer PySIDAM, headless bridge scripts, or existing skill adapters.
Do not rewrite routine file readers, gap fitting, or Bragg lock-in algorithms
unless existing tools are unavailable and the user explicitly approves a fallback.
```

## Workflow card

### 1. Confirm the data contract first

The first agent response should not be a physical conclusion. It should confirm the data contract.

Record at least:

- file type and source path;
- array shape and axis order;
- bias axis, bias unit, and divider;
- channel names and selected channel;
- scan size, pixel size, coordinate frame, and origin convention;
- NaN/Inf handling;
- transpose, flip, crop, drift correction, interpolation, window function, and masks.

For report-facing outputs, a good convention is:

- topography maps: `(y, x)`;
- spectroscopy cubes: `(y, x, bias)`;
- PySIDAM internal arrays: record any required `(x, y, bias)` conversion explicitly.

Important lesson: do not guess the `.3ds` divider. A wrong divider changes physical energy scales and can move gap windows by orders of magnitude. If the user corrects the divider, regenerate the inventory and record the correction in provenance.

### 2. Gate sensitive scientific parameters

The agent may inspect enough data to recommend parameters, but it should not silently decide scientifically sensitive parameters.

Use approval gates for:

- `fit_window`: fitting intervals, superconducting coherence-peak windows, peak-search windows;
- `q_selection`: FFT-derived q vectors, q windows, and lock-in filter sigma;
- `peak_count`: the number of peaks in multipeak fitting.

The approval workflow is:

```text
inspect enough -> propose parameters -> save proposal -> user approval
-> save decision -> execute -> link decision in report.json
```

A minimal proposal should include:

- proposed parameter values with units;
- alternatives and tradeoffs;
- evidence figures or candidate tables;
- risks and ambiguity;
- approval options: approve, modify, reject.

### 3. Example: peak-based gap map

A safe agent workflow for gap-map extraction:

1. Confirm the `.3ds` shape, bias axis, divider, scan size, and selected dI/dV channel.
2. Plot average spectra and representative spectra.
3. Propose left and right peak-search windows.
4. Save `approval_proposal.json` and a review figure.
5. Wait for user approval.
6. Save `approval_decision.json`.
7. Run the batch extraction, preferably through a PySIDAM-backed fitter.
8. Save the gap, left peak, right peak, status map, boundary-hit map, and representative diagnostics.

Quality checks should include:

- finite-result fraction;
- strict-valid fraction;
- left/right boundary-hit counts;
- failure modes;
- representative successful, failed, and ambiguous spectra.

When many pixels hit a search-window boundary, label the result as diagnostic or exploratory instead of making a strong physical claim.

### 4. Example: Bragg lock-in phase from SXM topography

A safe agent workflow for Bragg phase:

1. Read the SXM topography channel, usually `Z forward`.
2. Normalize scan direction and record the image frame.
3. Detrend or flatten only as recorded preprocessing.
4. Compute FFT/q-space evidence.
5. Propose q vectors and filter sigma through a `q_selection` approval gate.
6. After approval, extract complex lock-in fields.
7. Save `+q` and `-q` complex fields, amplitude, phase, masks, and threshold sweeps.
8. Report phase distributions and spatial phase maps only after quality checks.

For q selection, do not blindly trust the strongest FFT peak. Low-frequency texture, scan streaks, and vertical/horizontal artifacts can pull automatic peak search away from the real Bragg peak. If the user marks an ROI, restrict refinement to that ROI unless they approve a broader search.

Recommended Bragg phase checks:

- q-axis units and FFT pixel resolution;
- plus/minus q symmetry;
- amplitude correlation between `+q` and `-q`;
- `wrap(phase_plus + phase_minus)` near zero;
- amplitude mask coverage;
- phase circular mean and circular standard deviation;
- sigma/threshold sensitivity.

Do not make phase conclusions from a real-IFFT image alone. Save the complex field.

### 5. Prefer existing scientific engines

The agent can write thin glue scripts, but it should prefer existing scientific tools:

- raw Nanonis IO: PySIDAM/nanonispy or the skill bridge;
- gap map: PySIDAM-backed peak fitting when available;
- atom detection: an existing detector such as `Atom_Identificator_core.AtomDetector`;
- Bragg/QPI lock-in: `pysidam.qpi_analysis.qpi_phase_analysis.lockin_phase_extraction` when available.

Avoid large task-local reimplementations for routine IO, gap fitting, FFT/q selection, lock-in demodulation, or atom detection. If a custom fallback is unavoidable, record why the preferred route failed and mark the result accordingly.

### 6. Naming displacement and deformation quantities

Be careful with terms such as "drift field" and "stress".

A field derived from Bragg phase is usually a lattice-displacement proxy, not automatically a mechanical drift-correction field. A good label is:

```text
Bragg-phase displacement proxy from topographic Z lock-in (u_x, u_y)
```

If strain is computed from the displacement proxy, record the formula. For example:

```text
M = [[du_x/dx, du_x/dy],
     [du_y/dx, du_y/dy]]

epsilon = 0.5 * (M + M^T)

||epsilon||_F^2 = eps_xx^2 + eps_yy^2 + 2 eps_xy^2
```

This quantity is based on spatial derivatives of `u`, so it is not expected to be proportional to `|u|`. A slowly varying displacement can be large while its gradient is small. Conversely, phase noise or column offsets can be amplified by differentiation.

### 7. Handling stripe artifacts

If `u_x`, `u_y`, or `|u|` shows strong vertical or horizontal stripes:

1. trace whether the stripe originates in topography, lock-in phase, unwrapped residual phase, displacement solving, or plotting;
2. quantify row/column median components instead of relying only on visual impression;
3. keep the raw map;
4. save any artifact-suppressed map as display-only unless there is a physical justification;
5. compare correlations before and after suppression.

Useful display variants:

- raw displacement proxy;
- reliable-amplitude-mask-only map;
- moderate column-artifact-suppressed display;
- aggressive column-normalized diagnostic display.

Never replace the original data silently.

### 8. Evidence package layout

Each substantial analysis should produce a folder like:

```text
outputs/<analysis_name>/
  report.json
  approval_proposal.json        # when applicable
  approval_decision.json        # when applicable
  data/*.npz
  tables/*.csv
  figures/*.png
  notes.md                      # optional
```

`report.json` should include:

- `inputs`: source files, channels, metadata sources, user assumptions;
- `data_contract`: shape, axis order, units, coordinate frame, scan size, pixel size;
- `preprocessing`: background correction, smoothing, normalization, calibration, interpolation, masks;
- `analysis`: workflow, model family, fitting method, q selection, lock-in method;
- `parameters`: numerical settings with units;
- `quality`: residuals, boundary hits, mask coverage, threshold sweeps, diagnostic summaries;
- `approval`: proposal path, decision path, approved parameters, approval source;
- `warnings`: missing metadata, weak assumptions, failed fits, coordinate uncertainty;
- `outputs`: NPZ, CSV, PNG, PDF, and auxiliary files;
- `software`: packages, versions, source paths, commit hashes when available;
- `interpretation`: measured results and physical interpretation kept separate.

### 9. Scientific conclusion style

Separate measured results from interpretation.

Measured result examples:

- a q vector and its uncertainty or FFT pixel offset;
- a phase-jump estimate and its mask/sigma sensitivity;
- a gap-map median and boundary-hit fraction;
- an in-gap intensity ratio between two regions;
- a Spearman correlation between a displacement proxy and an in-gap map.

Interpretation examples:

- a line defect is consistent with a local lattice phase kink;
- a broad high-Z region is more consistent with continuous warping than a sharp domain wall;
- low-energy gap filling is observed, but evidence is insufficient for a YSR-like impurity state;
- a displacement proxy correlates with in-gap weight more plausibly than a local strain-tensor norm.

Strong claims such as YSR states, topological line modes, Majorana modes, or pair-density-wave signatures require stronger evidence than low-energy spectral weight alone. State the missing evidence explicitly.

## Minimal transcript pattern

```text
User:
Run Bragg phase analysis on three SXM topographs.

Agent:
I will first inspect FFT/q candidates and data contracts.
Because this requires q_selection, I will prepare an approval proposal
before extracting phase maps.

Agent output:
- approval_proposal.json
- q-candidate review figure
- q-candidate table
- risks and recommended q/sigma

User:
Approve qA only.

Agent:
I will save approval_decision.json and run only qA.
I will save +q/-q complex fields, amplitude, phase, masks,
threshold sweeps, and report.json.

Agent final:
- report.json linked to the decision
- phase maps
- phase distribution table
- plus/minus consistency table
- measured result and limitations
```

## Guardrails

Stop and correct the workflow if:

- the agent starts fitting or interpreting before confirming shape, bias unit, divider, and scan size;
- the agent chooses fit windows, q vectors, sigma, or peak count and runs without approval;
- the agent rewrites routine IO, gap fitting, or Bragg lock-in without checking PySIDAM or bridge capabilities;
- the agent reports phase from a real-IFFT image without saving complex fields, amplitude, phase, and masks;
- the agent calls `u_x/u_y` a real drift field or stress field when provenance only supports a Bragg-phase displacement proxy;
- the agent provides only PNG files without `report.json`, NPZ, and CSV outputs;
- the agent tells a physical story without quality checks, warnings, and failure modes.

## One-sentence summary

Treat the agent as an auditable experimental assistant, not a black box for automatic conclusions: confirm the data contract, gate sensitive parameters, use PySIDAM or bridge tools, save evidence packages, and make cautious interpretations.
