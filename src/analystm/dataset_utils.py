from dataclasses import dataclass

import numpy as np

from .bias_utils import normalize_bias_with_divider


@dataclass(frozen=True)
class SXMMapView:
    """An SXM map bound to an explicit coordinate and plotting contract."""

    data_yx: np.ndarray
    frame: str
    plot_origin: str
    scan_dir: str
    direction: str
    x_flip: bool
    y_flip: bool


def get_grid_shape_from_header(header):
    """Best-effort extraction of (nx, ny) grid size from a Nanonis header dict."""
    if not isinstance(header, dict):
        return None
    for key in (
        "dim_px",
        "grid_dim",
        "dim_pixels",
        "grid_dim_px",
        "grid_size",
        "pixels",
        "grid_pixels",
    ):
        val = header.get(key)
        if isinstance(val, (list, tuple, np.ndarray)) and len(val) >= 2:
            try:
                nx = int(val[0])
                ny = int(val[1])
                if nx > 0 and ny > 0:
                    return (nx, ny)
            except Exception:
                pass
    try:
        nx = header.get("nx") or header.get("x_pixels") or header.get("grid_nx")
        ny = header.get("ny") or header.get("y_pixels") or header.get("grid_ny")
        if nx is not None and ny is not None:
            nx = int(nx)
            ny = int(ny)
            if nx > 0 and ny > 0:
                return (nx, ny)
    except Exception:
        pass
    return None


def extract_scan_size_nm(header, default=100.0):
    """Best-effort extraction of lateral scan size in nm from a header dict."""
    try:
        scan_size_nm = float(np.asarray(default).ravel()[0])
    except Exception:
        scan_size_nm = 100.0
    if not isinstance(header, dict):
        return scan_size_nm

    try:
        size_xy = header.get("size_xy")
        if isinstance(size_xy, (list, tuple, np.ndarray)) and len(size_xy) >= 1:
            val = float(size_xy[0]) * 1e9
            if np.isfinite(val) and val > 0:
                return val
    except Exception:
        pass
    try:
        scan_range = header.get("scan_range")
        if isinstance(scan_range, (list, tuple, np.ndarray)) and len(scan_range) >= 1:
            val = float(scan_range[0]) * 1e9
            if np.isfinite(val) and val > 0:
                return val
    except Exception:
        pass
    return scan_size_nm


def normalize_3ds_cube(arr, bias_len=None, grid_shape=None, bias_axis_hint=None):
    """Normalize a 3DS channel into internal (x, y, bias) ordering."""
    if arr is None:
        return None
    try:
        cube = np.asarray(arr)
    except Exception:
        return None
    if cube.ndim == 0:
        return None

    hinted_bias_axis = None
    try:
        if bias_axis_hint is not None:
            hinted_bias_axis = int(bias_axis_hint)
    except Exception:
        hinted_bias_axis = None

    if cube.ndim == 1:
        if bias_len is not None and int(cube.size) == int(bias_len):
            cube = cube.reshape(1, 1, int(bias_len))
        else:
            return None
    elif cube.ndim == 2:
        if bias_len is not None and int(bias_len) > 0:
            bias_len = int(bias_len)
            prefer_axis0 = bool(hinted_bias_axis == 0 and cube.shape[0] == bias_len)
            prefer_axis1 = bool(hinted_bias_axis == 1 and cube.shape[1] == bias_len)
            if prefer_axis0:
                n_pix = int(cube.shape[1])
                if grid_shape and n_pix == int(grid_shape[0]) * int(grid_shape[1]):
                    nx, ny = int(grid_shape[0]), int(grid_shape[1])
                    cube = cube.reshape(bias_len, ny, nx)
                    cube = np.moveaxis(cube, 0, 2)
                else:
                    side = int(np.sqrt(n_pix))
                    if side * side == n_pix:
                        cube = cube.reshape(bias_len, side, side)
                        cube = np.moveaxis(cube, 0, 2)
                    else:
                        cube = np.moveaxis(cube, 0, 1)
                        cube = cube.reshape(n_pix, 1, bias_len)
            elif prefer_axis1 or cube.shape[1] == bias_len:
                n_pix = int(cube.shape[0])
                if grid_shape and n_pix == int(grid_shape[0]) * int(grid_shape[1]):
                    nx, ny = int(grid_shape[0]), int(grid_shape[1])
                    cube = cube.reshape(ny, nx, bias_len)
                else:
                    side = int(np.sqrt(n_pix))
                    if side * side == n_pix:
                        cube = cube.reshape(side, side, bias_len)
                    else:
                        cube = cube.reshape(n_pix, 1, bias_len)
            elif cube.shape[0] == bias_len:
                n_pix = int(cube.shape[1])
                if grid_shape and n_pix == int(grid_shape[0]) * int(grid_shape[1]):
                    nx, ny = int(grid_shape[0]), int(grid_shape[1])
                    cube = cube.reshape(bias_len, ny, nx)
                    cube = np.moveaxis(cube, 0, 2)
                else:
                    side = int(np.sqrt(n_pix))
                    if side * side == n_pix:
                        cube = cube.reshape(bias_len, side, side)
                        cube = np.moveaxis(cube, 0, 2)
                    else:
                        cube = np.moveaxis(cube, 0, 1)
                        cube = cube.reshape(n_pix, 1, bias_len)
            else:
                cube = cube[:, :, np.newaxis]
        else:
            cube = cube[:, :, np.newaxis]
    elif cube.ndim > 3:
        cube = cube.reshape(cube.shape[0], cube.shape[1], -1)

    if cube.ndim != 3:
        return None

    if hinted_bias_axis is not None and 0 <= hinted_bias_axis < cube.ndim:
        cube = np.moveaxis(cube, hinted_bias_axis, 2)

    if bias_len is not None and cube.shape[2] != int(bias_len):
        target = int(bias_len)
        axes = [ax for ax, dim in enumerate(cube.shape) if int(dim) == target]
        if axes:
            cube = np.moveaxis(cube, axes[0], 2)

    if grid_shape:
        nx, ny = int(grid_shape[0]), int(grid_shape[1])
        if cube.shape[0] == ny and cube.shape[1] == nx:
            cube = np.transpose(cube, (1, 0, 2))

    cube = np.asarray(cube, dtype=float)
    cube = np.nan_to_num(cube, nan=0.0, posinf=0.0, neginf=0.0)
    return np.ascontiguousarray(cube)


def derive_3ds_sweep_from_params(signals, header=None, target_len=None):
    """Derive a 3DS sweep axis from the params cube using named param columns."""
    if not isinstance(signals, dict):
        return None
    params = signals.get("params")
    if params is None:
        return None
    try:
        arr = np.asarray(params, dtype=float)
    except Exception:
        return None
    if arr.ndim < 1 or arr.shape[-1] < 2:
        return None

    def _norm(text):
        return "".join(ch.lower() for ch in str(text) if ch.isalnum())

    def _find_indices(name_list, ncols):
        if not isinstance(name_list, (list, tuple, np.ndarray)) or len(name_list) != ncols:
            return None
        norm_names = [_norm(v) for v in name_list]
        start_idx = end_idx = None
        exact_start = {"sweepstart", "biasstart", "startbias", "sweepstartv"}
        exact_end = {"sweepend", "biasend", "endbias", "sweependv"}
        for i, name in enumerate(norm_names):
            if start_idx is None and (name in exact_start or ("start" in name and ("sweep" in name or "bias" in name))):
                start_idx = i
            if end_idx is None and (name in exact_end or ("end" in name and ("sweep" in name or "bias" in name))):
                end_idx = i
        if start_idx is None or end_idx is None:
            return None
        return start_idx, end_idx

    ncols = int(arr.shape[-1])
    candidate_name_lists = []
    if isinstance(header, dict):
        fixed_vals = header.get("fixed_parameters")
        exp_vals = header.get("experimental_parameters")
        fixed_list = [str(v) for v in fixed_vals] if isinstance(fixed_vals, (list, tuple, np.ndarray)) else ([str(fixed_vals)] if isinstance(fixed_vals, str) and fixed_vals else [])
        exp_list = [str(v) for v in exp_vals] if isinstance(exp_vals, (list, tuple, np.ndarray)) else ([str(exp_vals)] if isinstance(exp_vals, str) and exp_vals else [])
        if len(exp_list) == ncols:
            candidate_name_lists.append(exp_list)
        if len(fixed_list) == ncols:
            candidate_name_lists.append(fixed_list)
        if len(fixed_list) + len(exp_list) == ncols:
            candidate_name_lists.append(fixed_list + exp_list)

    start_idx = end_idx = None
    for name_list in candidate_name_lists:
        found = _find_indices(name_list, ncols)
        if found is not None:
            start_idx, end_idx = found
            break
    if start_idx is None or end_idx is None:
        return None

    try:
        start_vals = np.asarray(arr[..., start_idx], dtype=float).ravel()
        end_vals = np.asarray(arr[..., end_idx], dtype=float).ravel()
        start_vals = start_vals[np.isfinite(start_vals)]
        end_vals = end_vals[np.isfinite(end_vals)]
        if start_vals.size == 0 or end_vals.size == 0:
            return None
        sweep_start = float(np.nanmedian(start_vals))
        sweep_end = float(np.nanmedian(end_vals))
    except Exception:
        return None
    if not np.isfinite(sweep_start) or not np.isfinite(sweep_end):
        return None

    n = None
    if target_len is not None:
        try:
            n = int(target_len)
        except Exception:
            n = None
    if not n and isinstance(header, dict):
        try:
            n = int(header.get("num_sweep_signal", 0)) or None
        except Exception:
            n = None
    if not n or n <= 1:
        return None
    return np.linspace(sweep_start, sweep_end, n, dtype=float)


def derive_3ds_sweep_from_signal_channels(signals, header=None, target_len=None):
    """Try to recover the sweep axis from bias-like signal channels themselves."""
    if not isinstance(signals, dict):
        return []

    grid_shape = get_grid_shape_from_header(header)
    n_target = None
    if target_len is not None:
        try:
            n_target = int(target_len)
        except Exception:
            n_target = None
    if not n_target and isinstance(header, dict):
        try:
            n_target = int(header.get("num_sweep_signal", 0)) or None
        except Exception:
            n_target = None

    def _norm(text):
        return "".join(ch.lower() for ch in str(text) if ch.isalnum())

    out = []
    for key, raw in signals.items():
        nk = _norm(key)
        if key == "sweep_signal":
            continue
        if "bias" not in nk and "sweep" not in nk:
            continue
        cube = normalize_3ds_cube(raw, bias_len=n_target, grid_shape=grid_shape)
        if cube is None or cube.ndim != 3 or cube.shape[2] <= 1:
            continue
        if n_target is not None and cube.shape[2] != int(n_target):
            continue
        try:
            flat = np.asarray(cube, dtype=float).reshape(-1, cube.shape[2])
            axis = np.nanmedian(flat, axis=0)
        except Exception:
            continue
        if axis.size <= 1 or not np.all(np.isfinite(axis)):
            continue
        diffs = np.diff(axis)
        if not (np.all(diffs >= 0) or np.all(diffs <= 0)):
            continue
        span = float(np.nanmax(axis) - np.nanmin(axis))
        if not np.isfinite(span) or span <= 0:
            continue
        try:
            resid = flat - axis[None, :]
            resid = resid[np.isfinite(resid)]
            scatter = float(np.nanmedian(np.abs(resid))) if resid.size else 0.0
        except Exception:
            scatter = 0.0
        if np.isfinite(scatter) and scatter > max(1e-9, 0.05 * span):
            continue
        out.append((f"signal:{key}", np.asarray(axis, dtype=float)))
    return out


def _bias_axis_source_priority(label):
    text = str(label or "")
    if text == "explicit":
        return 3.5
    if text == "grid.bias":
        return 3.25
    if text == "sweep_signal":
        return 3.0
    if text.startswith("signal:"):
        return 2.0
    if text == "params":
        return 0.75
    return 0.0


def choose_best_bias_axis(candidates, target_len=None):
    """Pick the most plausible bias axis from multiple normalized candidates."""
    best = None
    best_score = None

    for label, arr in candidates:
        if arr is None:
            continue
        try:
            vals = np.asarray(arr, dtype=float).ravel()
        except Exception:
            continue
        if vals.size <= 1:
            continue
        finite = vals[np.isfinite(vals)]
        if finite.size != vals.size:
            continue

        diffs = np.diff(vals)
        monotonic = np.all(diffs >= 0) or np.all(diffs <= 0)
        if not monotonic:
            continue
        span = float(np.nanmax(vals) - np.nanmin(vals))
        step = float(np.nanmedian(np.abs(diffs))) if diffs.size else 0.0
        if not np.isfinite(span) or span <= 0 or not np.isfinite(step):
            continue

        score = 0.0
        if target_len is not None:
            try:
                score += 8.0 if int(vals.size) == int(target_len) else -8.0
            except Exception:
                pass
        crosses_zero = bool(np.nanmin(vals) <= 0.0 <= np.nanmax(vals))
        if crosses_zero:
            score += 6.0
        center_offset = abs(float(np.nanmean(vals))) / max(span, 1e-12)
        score += max(0.0, 3.0 - 6.0 * center_offset)
        score += _bias_axis_source_priority(label)
        score += min(2.0, max(0.0, np.log10(max(span, 1e-12) + 1.0)))

        if best is None or score > best_score:
            best = vals
            best_score = score

    return best


def normalize_3ds_signal_dict(signals, bias=None, header=None, spectral_only=False, bias_already_mv=False, divider=1.0):
    """Normalize all channels in a 3DS signals dict to (x, y, bias)."""
    if not isinstance(signals, dict):
        return {}, None

    target_len = None
    if isinstance(header, dict):
        try:
            target_len = int(header.get("num_sweep_signal", 0)) or None
        except Exception:
            target_len = None

    bias_arr = None
    candidate_axes = []
    if bias is not None:
        try:
            arr = normalize_bias_with_divider(
                bias,
                divider=divider,
                already_mv=bias_already_mv,
            )
            if arr is not None and arr.size > 1:
                candidate_axes.append(("explicit", arr))
        except Exception:
            pass
    try:
        derived = derive_3ds_sweep_from_params(signals, header=header, target_len=target_len)
        if derived is not None and np.asarray(derived).size > 1:
            arr = normalize_bias_with_divider(
                derived,
                force=True,
                divider=divider,
                already_mv=False,
            )
            if arr is not None and arr.size > 1:
                candidate_axes.append(("params", arr))
    except Exception:
        pass
    try:
        for label, arr_raw in derive_3ds_sweep_from_signal_channels(signals, header=header, target_len=target_len):
            arr = normalize_bias_with_divider(
                arr_raw,
                force=True,
                divider=divider,
                already_mv=False,
            )
            if arr is not None and arr.size > 1:
                candidate_axes.append((label, arr))
    except Exception:
        pass
    if "sweep_signal" in signals:
        try:
            arr = normalize_bias_with_divider(
                signals["sweep_signal"],
                force=True,
                divider=divider,
                already_mv=False,
            )
            if arr is not None and arr.size > 1:
                candidate_axes.append(("sweep_signal", arr))
        except Exception:
            pass

    bias_arr = choose_best_bias_axis(candidate_axes, target_len=target_len)

    bias_len = int(bias_arr.size) if bias_arr is not None else None
    grid_shape = get_grid_shape_from_header(header)
    bias_axis_hint = None
    if isinstance(header, dict):
        try:
            raw_hint = header.get("ibw_bias_axis_index")
        except Exception:
            raw_hint = None
        try:
            if raw_hint is not None:
                bias_axis_hint = int(raw_hint)
        except Exception:
            bias_axis_hint = None

    out = {}
    spec_lengths = []
    for key, arr in signals.items():
        if key == "sweep_signal":
            continue
        cube = normalize_3ds_cube(
            arr,
            bias_len=bias_len,
            grid_shape=grid_shape,
            bias_axis_hint=bias_axis_hint,
        )
        if cube is None:
            continue
        if bias_len is not None and cube.shape[2] == bias_len * 2:
            cube = cube[:, :, :bias_len]
        if spectral_only and cube.shape[2] <= 1:
            continue
        out[key] = cube
        if cube.shape[2] > 1:
            spec_lengths.append(int(cube.shape[2]))

    if not out:
        return {}, bias_arr

    target_nz = None
    if spec_lengths:
        try:
            target_nz = max(set(spec_lengths), key=spec_lengths.count)
        except Exception:
            target_nz = spec_lengths[0]
    else:
        try:
            target_nz = next(iter(out.values())).shape[2]
        except Exception:
            target_nz = None

    if target_nz is not None:
        if bias_arr is None or bias_arr.size <= 1:
            bias_arr = np.linspace(0.0, float(target_nz - 1), int(target_nz), dtype=float)
        elif bias_arr.size == int(target_nz) * 2:
            bias_arr = bias_arr[:int(target_nz)]
        elif bias_arr.size != int(target_nz):
            bias_arr = np.linspace(float(bias_arr[0]), float(bias_arr[-1]), int(target_nz), dtype=float)

    return out, bias_arr


def is_topo_like_channel_name(name):
    lowered = str(name or "").lower()
    normalized = "".join(ch for ch in lowered if ch.isalnum())
    return (
        any(tag in lowered for tag in ("topo", "height", "topography", "deflection"))
        or normalized == "z"
        or normalized.startswith("zchannel")
        or normalized.startswith("height")
        or normalized.startswith("topo")
    )


def is_param_like_channel_name(name):
    normalized = "".join(ch.lower() for ch in str(name or "") if ch.isalnum())
    return normalized in ("param", "params", "parameter", "parameters") or normalized.startswith("params")


def is_qpi_spectral_channel(name, value):
    if is_param_like_channel_name(name):
        return False
    try:
        arr = np.asarray(value)
    except Exception:
        return False
    return arr.ndim == 3 and int(arr.shape[2]) > 1


def coerce_prepared_3ds_cubes(signals, spectral_only=False, spatial_order="xy"):
    """Coerce already-prepared 3DS cube dicts to internal (x, y, bias) ordering."""
    if not isinstance(signals, dict):
        return {}

    order = str(spatial_order or "xy").strip().lower()
    out = {}
    for key, value in signals.items():
        try:
            arr = np.asarray(value, dtype=float)
        except Exception:
            continue
        if arr.ndim == 2:
            arr = arr[:, :, np.newaxis]
        elif arr.ndim > 3:
            arr = arr.reshape(arr.shape[0], arr.shape[1], -1)
        if arr.ndim != 3:
            continue
        if order in ("row-major", "row_major", "yx", "y,x", "prepared-row-major", "prepared_row_major"):
            arr = np.transpose(arr, (1, 0, 2))
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
        if spectral_only and arr.shape[2] <= 1:
            continue
        out[key] = np.ascontiguousarray(arr, dtype=float)
    return out


def coerce_prepared_bias_axis(bias, target_nz=None):
    try:
        arr = np.asarray(bias, dtype=float).ravel() if bias is not None else None
    except Exception:
        arr = None

    if target_nz is None:
        return None if arr is None else np.asarray(arr, dtype=float)

    nz = max(0, int(target_nz))
    if nz <= 0:
        return np.asarray([], dtype=float)
    if arr is None or arr.size == 0:
        return np.arange(nz, dtype=float)
    if arr.size == nz:
        return np.asarray(arr, dtype=float)
    if arr.size >= 2:
        return np.linspace(float(arr[0]), float(arr[-1]), nz, dtype=float)
    return np.full(nz, float(arr[0]), dtype=float)


def extract_3ds_topography_candidates(cubes):
    """Extract topo-like 2D maps from normalized 3DS cubes."""
    if not isinstance(cubes, dict):
        return {}

    topo_candidates = {}
    for key, value in cubes.items():
        if not is_topo_like_channel_name(key):
            continue
        try:
            arr = np.asarray(value, dtype=float)
        except Exception:
            continue
        if arr.ndim == 2:
            topo = arr
        elif arr.ndim == 3:
            if arr.shape[2] <= 1:
                topo = arr[:, :, 0]
            else:
                topo = np.nanmean(arr, axis=2)
        else:
            continue
        topo = np.nan_to_num(topo, nan=0.0, posinf=0.0, neginf=0.0)
        topo_candidates[key] = np.ascontiguousarray(topo, dtype=float)
    return topo_candidates


def prepare_3ds_dataset(
    signals,
    header=None,
    bias=None,
    spectral_only=False,
    prepared=False,
    spatial_order="xy",
    bias_already_mv=False,
    divider=1.0,
):
    """Normalize a 3DS dataset through one shared code path."""
    raw_signals = signals or {}
    if bias is None and isinstance(raw_signals, dict):
        bias = raw_signals.get("sweep_signal")

    if prepared:
        cubes = coerce_prepared_3ds_cubes(
            raw_signals,
            spectral_only=False,
            spatial_order=spatial_order,
        )
        spec_lengths = [
            int(arr.shape[2])
            for arr in cubes.values()
            if np.asarray(arr).ndim == 3 and int(np.asarray(arr).shape[2]) > 1
        ]
        target_nz = None
        if spec_lengths:
            try:
                target_nz = max(set(spec_lengths), key=spec_lengths.count)
            except Exception:
                target_nz = spec_lengths[0]
        bias_norm = normalize_bias_with_divider(
            bias,
            divider=divider,
            already_mv=bias_already_mv,
        )
        bias_arr = coerce_prepared_bias_axis(bias_norm, target_nz=target_nz)
        if spectral_only:
            cubes = {
                k: v for k, v in cubes.items()
                if v is not None and np.asarray(v).ndim == 3 and np.asarray(v).shape[2] > 1
            }
    else:
        cubes, bias_arr = normalize_3ds_signal_dict(
            raw_signals,
            bias=bias,
            header=header,
            spectral_only=spectral_only,
            bias_already_mv=bias_already_mv,
            divider=divider,
        )

    topo_candidates = extract_3ds_topography_candidates(cubes)
    scan_size_nm = extract_scan_size_nm(header, default=100.0)
    return cubes, bias_arr, scan_size_nm, topo_candidates


def extract_sxm_scan_dir(header=None, default="down"):
    if header is None:
        return str(default or "down").strip().lower()
    if isinstance(header, str):
        text = header.strip().lower()
        return text or str(default or "down").strip().lower()
    if isinstance(header, dict):
        for key in ("scan_dir", "SCAN_DIR", ":SCAN_DIR:"):
            try:
                value = header.get(key)
            except Exception:
                value = None
            if value is None:
                continue
            text = str(value).strip().lower()
            if text:
                return text
    return str(default or "down").strip().lower()


def _coerce_sxm_map(data_obj):
    try:
        data = np.asarray(data_obj, dtype=float)
    except Exception:
        return None
    data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)

    if data.ndim == 3:
        if data.shape[2] == 1:
            data = data[:, :, 0]
        elif data.shape[0] == 1:
            data = data[0, :, :]
        elif data.shape[1] == 1:
            data = data[:, 0, :]
        else:
            data = data[:, :, 0]
    if data.ndim != 2:
        return data
    return data


def prepare_sxm_map(
    data_obj,
    direction="forward",
    header=None,
    scan_dir=None,
    frame="physical_xy",
):
    """Prepare an SXM map with explicit frame, flip, and plot-origin metadata.

    ``physical_xy`` returns a report-facing map for ``origin="lower"``:
    down scans flip vertically, up scans do not. ``nanonis_display`` returns
    scan-normalized display order for ``origin="upper"``. Backward data flips
    horizontally in both frames to align retrace pixels with forward pixels.
    """
    data = _coerce_sxm_map(data_obj)
    if data is None:
        return None
    if data.ndim != 2:
        raise ValueError("SXM map must be 2D after coercion")

    direction_text = str(direction or "forward").strip().lower()
    if direction_text not in {"forward", "backward"}:
        raise ValueError("direction must be 'forward' or 'backward'")

    if scan_dir is not None:
        scan_dir_text = str(scan_dir).strip().lower()
    else:
        scan_dir_text = extract_sxm_scan_dir(header=header, default="down")
    if scan_dir_text not in {"down", "up"}:
        raise ValueError("scan_dir must be 'down' or 'up'")

    frame_text = str(frame or "physical_xy").strip().lower()
    if frame_text not in {"physical_xy", "nanonis_display"}:
        raise ValueError("frame must be 'physical_xy' or 'nanonis_display'")

    y_flip = (
        scan_dir_text == "down"
        if frame_text == "physical_xy"
        else scan_dir_text == "up"
    )
    x_flip = direction_text == "backward"

    if y_flip:
        data = np.flipud(data)
    if x_flip:
        data = np.fliplr(data)

    return SXMMapView(
        data_yx=data,
        frame=frame_text,
        plot_origin="lower" if frame_text == "physical_xy" else "upper",
        scan_dir=scan_dir_text,
        direction=direction_text,
        x_flip=x_flip,
        y_flip=y_flip,
    )


def normalize_sxm_direction_map(data_obj, direction="forward", header=None, scan_dir=None):
    """Return legacy scan-normalized display order; pair it with origin='upper'."""
    data = _coerce_sxm_map(data_obj)
    if data is None or data.ndim != 2:
        return data
    scan_dir_text = extract_sxm_scan_dir(header=header, default=scan_dir or "down")
    if scan_dir_text not in {"down", "up"}:
        scan_dir_text = "down"
    direction_text = (
        "backward" if str(direction).strip().lower() == "backward" else "forward"
    )
    view = prepare_sxm_map(
        data,
        direction=direction_text,
        header=None,
        scan_dir=scan_dir_text,
        frame="nanonis_display",
    )
    if view is None:
        return None
    return view.data_yx


__all__ = [
    "SXMMapView",
    "get_grid_shape_from_header",
    "extract_scan_size_nm",
    "normalize_3ds_cube",
    "derive_3ds_sweep_from_params",
    "derive_3ds_sweep_from_signal_channels",
    "choose_best_bias_axis",
    "normalize_3ds_signal_dict",
    "is_topo_like_channel_name",
    "is_param_like_channel_name",
    "is_qpi_spectral_channel",
    "coerce_prepared_3ds_cubes",
    "coerce_prepared_bias_axis",
    "extract_3ds_topography_candidates",
    "prepare_3ds_dataset",
    "extract_sxm_scan_dir",
    "prepare_sxm_map",
    "normalize_sxm_direction_map",
]
