# STS DAT Quick Card

Use this quick card for simple `.dat` spectroscopy inspection, channel summaries, and overview plots. It is intentionally short so agents do not load the full STM/SJTM reference set for routine file reading.

## Fast Path

1. From the skill root, run `python3 scripts/resolve_runtime.py --probe`.
2. If the resolver reports no ready runtime, inspect `python3 scripts/resolve_runtime.py --bootstrap-command` and bootstrap only into the user-writable cache.
3. Read files through `python3 scripts/pysidam_agent/read_file.py INPUT.dat --output-json outputs/read_summary.json`.
4. Make diagnostic spectra through `python3 scripts/pysidam_agent/plot_spectrum.py INPUT.dat --output outputs/spectra.png --summary-json outputs/spectra.json`.

For two common Nanonis STS channels, the bridge defaults to:

- x axis: `Bias calc (V)`, displayed as mV when appropriate.
- y axis: `LI Demod 1 X`, displayed as pA when requested.

Use `--channel`, `--bias-channel`, and `--average-bwd` when the requested observable differs from the default.

## Boundaries

- This card is for diagnostic reading and plotting only, with no scientific conclusion.
- Do not dump full Nanonis headers unless the user explicitly requests that private metadata be serialized.
- For gap fitting, deconvolution, QPI, SJTM maps, phase claims, or quantitative interpretation, read the relevant deeper references before acting.
