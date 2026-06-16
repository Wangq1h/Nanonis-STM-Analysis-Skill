# Nanonis And 3DS Ingest

Use this reference for raw Nanonis `.3ds`, `.sxm`, `.dat`, topography extraction from grids, bias divider handling, and target-energy LDOS slices. For the full file-format matrix, read `references/format-io-matrix.md`.

## Required Reader

Raw Nanonis files should use PySIDAM's Nanonis route:

```python
from pysidam.core.nanonis_io import read_nanonis_file, NanonisUnavailableError
from pysidam.core.dataset_utils import prepare_3ds_dataset
```

`read_nanonis_file()` calls `nanonispy`:

- `.3ds` -> `nanonispy.read.Grid`
- `.sxm` -> `nanonispy.read.Scan`
- `.dat` -> `nanonispy.read.Spec`

If `nanonispy` is unavailable, stop the raw Nanonis path and report the dependency gap. Do not hand-roll a `.3ds` binary parser unless the user explicitly approves that fallback.

## 3DS Recipe

```python
from pathlib import Path
import numpy as np

from pysidam.core.nanonis_io import read_nanonis_file
from pysidam.core.dataset_utils import prepare_3ds_dataset

path = Path("example.3ds")
nf = read_nanonis_file(path)
grid = nf.obj

cubes_xyb, bias_mv, scan_size_nm, topo_xy = prepare_3ds_dataset(
    grid.signals,
    header=getattr(grid, "header", None),
    bias=getattr(grid, "bias", None),
    divider=100.0,
)
```

PySIDAM normalizes grid cubes to `(x, y, bias)`. For report-facing images or Matplotlib-style display, explicitly convert:

```python
channel = next(k for k, v in cubes_xyb.items() if np.asarray(v).ndim == 3 and np.asarray(v).shape[2] > 1)
cube_xyb = np.asarray(cubes_xyb[channel], dtype=float)
target_mev = 3.8
idx = int(np.argmin(np.abs(np.asarray(bias_mv, dtype=float) - target_mev)))
ldos_yx = cube_xyb[:, :, idx].T
```

For topography:

```python
topo_key, topo_map_xy = next(iter(topo_xy.items()))
topo_yx = np.asarray(topo_map_xy, dtype=float).T
```

If no topography candidate is returned, inspect `grid.signals` for names such as `topo`, `Topography`, `Topography (m)`, `Z`, `Height`, or `Height (m)`.

## Bias Divider

PySIDAM bias normalization:

- Treats small-magnitude axes as volts and converts to mV.
- Applies `bias_mv / divider`.
- Chooses among explicit bias, `grid.bias`, `sweep_signal`, bias-like channels, and `params`.

Always record:

- Raw bias source.
- Whether the axis was already mV.
- Divider value.
- Final bias axis min, max, length, and selected index.

For an STS energy target in meV, use the same numeric value on the final mV axis after divider handling.

## Channel Selection

Before choosing a channel, list available channels and shapes. Prefer spectral channels with `ndim == 3` and `shape[2] == len(bias_mv)`. Exclude parameter-like and topography-like channels unless the task explicitly targets them.

## Output Contract

Report:

- `source_file`, `reader`, `pysidam_source`, `pysidam_commit` when available.
- `nanonispy_available` and import error if unavailable.
- `channels` and selected channel.
- PySIDAM internal shape `(x, y, bias)`.
- Report-facing shape `(y, x, bias)` after any transpose.
- `scan_size_nm`, `pixel_size_nm`, bias axis details, divider, and target-energy index.
