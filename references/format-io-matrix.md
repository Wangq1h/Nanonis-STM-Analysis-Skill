# Format IO Matrix

Use this reference before opening STM/SJTM files. It records the current PySIDAM-backed reader coverage and the object contract each format should produce.

## Supported Now

| Format | PySIDAM route | Dependency | Contract |
| --- | --- | --- | --- |
| `.3ds` | `pysidam.core.nanonis_io.read_nanonis_file` -> `prepare_3ds_dataset` | `nanonispy` | grid `signals`, `header`, optional `bias`; cubes become `(x, y, bias)` |
| `.sxm` | raw reader -> `analystm.prepare_sxm_map` | `nanonispy` | scan `signals` with 2D maps or forward/backward maps; explicit frame and plot origin |
| `.dat` | `pysidam.core.nanonis_io.read_nanonis_file` | `nanonispy` | spectroscopy `signals`; select bias-like axis and signal columns |
| `.txt/.csv/.tsv` | `pysidam.core.import_io.read_imported_file` | core Python/NumPy | dtype `dat`, `signals["Bias calc (V)"]` plus signal columns |
| `.ibw` | `pysidam.core.import_io.read_imported_file` | PySIDAM built-in parser | dtype depends on wave: `dat`, `sxm`, `ibw`, or spectral cube metadata |
| PySIDAM `.npz` archive | PySIDAM archive schema in `main_dashboard._load_pysidam_archive_npz` | NumPy | `signals`, `header`, `bias`, `archive_type`, `entry_meta` |
| multipeak `.npz` | `linecutmap_multipeak_fitting` viewer schema | NumPy | keys include `raw_data`, `bias`, `pos`, `amps`, `centers`, `sigmas` |

## Not Supported Now

PXP is not a current PySIDAM-backed supported format. Do not claim PXP support until a PySIDAM reader or documented converter is added. If the user provides exported PXP-derived `.npz`, `.csv`, `.txt`, or `.ibw`, process the exported file and record the converter provenance.

## Raw Nanonis

For `.3ds`, `.sxm`, and `.dat`:

```python
from pysidam.core.nanonis_io import read_nanonis_file

nf = read_nanonis_file(path)
obj = nf.obj
dtype = nf.dtype
channels = nf.channels
```

If this raises `NanonisUnavailableError`, `nanonispy` is missing. Stop the raw Nanonis path and report the dependency gap.

## SXM Maps

Prepare each map through the structured AnalySTM API. The report-facing default is physical x-right/y-up coordinates:

```python
import matplotlib.pyplot as plt
from analystm import prepare_sxm_map
from analystm.dataset_utils import extract_scan_size_nm

header = getattr(scan, "header", {})
signals = getattr(scan, "signals", {})
raw = signals[channel]

if isinstance(raw, dict) and "forward" in raw:
    view = prepare_sxm_map(raw["forward"], direction="forward", header=header, frame="physical_xy")
elif isinstance(raw, dict) and "backward" in raw:
    view = prepare_sxm_map(raw["backward"], direction="backward", header=header, frame="physical_xy")
else:
    view = prepare_sxm_map(raw, direction="forward", header=header, frame="physical_xy")

scan_size_nm = extract_scan_size_nm(header, default=100.0)
plt.imshow(view.data_yx, origin=view.plot_origin)
```

For raw nanonispy array order, the orientation truth table is:

| Target frame | `scan_dir` | Y transform | Backward additional transform | Required plot origin |
| --- | --- | --- | --- | --- |
| `physical_xy` | `down` | `flipud` | `fliplr` | `lower` |
| `physical_xy` | `up` | none | `fliplr` | `lower` |
| `nanonis_display` | `down` | none | `fliplr` | `upper` |
| `nanonis_display` | `up` | `flipud` | `fliplr` | `upper` |

Use `physical_xy` for report-facing maps and coordinate-dependent analysis. Use `nanonis_display` only when reproducing the Nanonis screen convention. `normalize_sxm_direction_map()` remains a compatibility helper that returns this legacy Nanonis-display array order and must be plotted with `origin="upper"`.

Record selected channel, scan size, `scan_dir`, acquisition direction, target frame, x/y flips, plot origin, and orientation validation. Do not average forward/backward maps until both have been transformed into the same verified frame.

## DAT And 1D Spectroscopy

Raw `.dat` through `nanonispy` and imported `.txt/.csv/.tsv/.ibw` should yield a spectroscopy-like `signals` dict. For imported text files, PySIDAM uses `Bias calc (V)` as the x axis. For raw `.dat`, select a bias-like channel using channel names and record the chosen x axis.

For deconvolution or point fitting, convert to a numeric two-column table:

```python
from pysidam.core.import_io import imported_file_to_numeric_table

table, header_text, encoding, columns = imported_file_to_numeric_table(imported_file)
```

For raw `.dat`, build the same contract manually from `signals`: one bias axis plus one selected y channel.

## IBW

PySIDAM's `.ibw` reader does not require `igor2`. It reads Igor Binary Wave v5/v7 numeric waves and infers:

- 1D spectrum -> dtype `dat`.
- 2D spectral-like linecut -> dtype `sxm`, `import_role="generic_linecut_map_2d"`, `ibw_promotable_spectral=True`.
- 2D real-space or FFT map -> dtype `sxm`, `import_role="generic_map_2d"` or `generic_fft_map_2d`.
- 3D spectral cube -> dtype `ibw`, `import_role="generic_spectral_cube_3d"`, `ibw_promotable_spectral=True`.
- Unknown ND wave -> dtype `ibw`, `import_role="generic_nd_wave"`.

For spectral `.ibw`, pass `obj.signals`, `obj.header`, and `obj.bias` to `prepare_3ds_dataset`; use `bias_already_mv=True` when `header["ibw_bias_already_mv"]` is set.

## Export

Use `analystm export spec-dat` for Nanonis-style spectroscopy `.dat` files and `analystm export grid-3ds` for Nanonis-style grid `.3ds` files. The `.3ds` writer follows PySIDAM's internal `(x, y, bias)` cube contract. Use `analystm export ibw` only when optional `igorwriter` is available, and record the wave name, source key, and units.

## NPZ

PySIDAM archives require:

- `pysidam_archive_version`
- `signals`
- `archive_type`

Optional keys:

- `header`
- `bias`
- `entry_meta`

Only treat `.npz` as a PySIDAM archive when these schema keys exist. Only treat `.npz` as multipeak fit output when the expected multipeak keys exist. Unknown `.npz` files need schema inspection before analysis.

## Reporting

For every file, report:

- Source path and format.
- Reader route and dependency state.
- Channels and selected channel.
- Object type and import role.
- Axis order and units.
- Scan size, bias axis, divider, and coordinate transforms.
- Unsupported or inferred fields.
