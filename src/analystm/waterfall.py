from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from scipy import ndimage
from scipy.interpolate import interp1d
from scipy.optimize import curve_fit
from scipy.signal import savgol_filter


WATERFALL_SOURCE_MAPPING = (
    "linecutmap_waterfall.BaseMapSpectroscopyWindow._get_linecut_indices, "
    "run_batch_auto_peak_align, perform_spatial_interpolation, _analyze_single_peak, "
    "run_waterfall_fitting, _get_waterfall_export_table, _get_waterfall_points_json_payload, "
    "_apply_baseline_correction"
)


def waterfall_algorithm(engine: str = "analystm.waterfall.run_waterfall_fit") -> dict[str, str]:
    return {
        "name": "AnalySTM waterfall backend",
        "engine": engine,
        "pysidam_source_mapping": WATERFALL_SOURCE_MAPPING,
    }


def gaussian(x: Any, amp: float, cen: float, wid: float, bg: float) -> np.ndarray:
    xx = np.asarray(x, dtype=float)
    return float(bg) + float(amp) * np.exp(-((xx - float(cen)) ** 2) / (2.0 * float(wid) ** 2))


def scale_bias(bias_array: Any, factor: float = 1.0) -> np.ndarray:
    try:
        denom = float(factor)
    except Exception:
        denom = 1.0
    if denom == 0:
        denom = 1.0
    return np.asarray(bias_array, dtype=float) / denom


def unscale_bias_value(value: float, factor: float = 1.0) -> float:
    try:
        fac = float(factor)
    except Exception:
        fac = 1.0
    if fac == 0:
        fac = 1.0
    return float(value) * fac


def linecut_flat_indices(shape_xy: Sequence[int], p1_xy: Sequence[float], p2_xy: Sequence[float]) -> np.ndarray:
    nx, ny = int(shape_xy[0]), int(shape_xy[1])
    if nx <= 0 or ny <= 0:
        return np.array([], dtype=int)
    p1 = np.asarray(p1_xy, dtype=float).ravel()
    p2 = np.asarray(p2_xy, dtype=float).ravel()
    if p1.size < 2 or p2.size < 2:
        return np.array([], dtype=int)
    x0, y0 = float(p1[0]), float(p1[1])
    x1, y1 = float(p2[0]), float(p2[1])
    n = int(np.hypot(x1 - x0, y1 - y0)) + 1
    if n < 2:
        return np.array([], dtype=int)
    xs = np.linspace(x0, x1, n)
    ys = np.linspace(y0, y1, n)
    ix = np.clip(np.round(xs).astype(int), 0, nx - 1)
    iy = np.clip(np.round(ys).astype(int), 0, ny - 1)
    indices: list[int] = []
    last: int | None = None
    for a, b in zip(ix, iy):
        idx = int(a * ny + b)
        if idx != last:
            indices.append(idx)
            last = idx
    return np.asarray(indices, dtype=int)


def infer_3ds_is_2d(data_cubes: dict[str, Any]) -> bool:
    for cube in (data_cubes or {}).values():
        try:
            arr = np.asarray(cube)
        except Exception:
            continue
        if arr.ndim == 3:
            nx, ny = int(arr.shape[0]), int(arr.shape[1])
            return bool(nx > 1 and ny > 1)
    return False


def spatial_interpolate_grid(grid: Any, scale: float = 1.0) -> np.ndarray:
    arr = np.asarray(grid, dtype=float)
    if arr.ndim != 3:
        raise ValueError("waterfall grid expects (x, y, bias)")
    factor = float(scale)
    if factor == 1.0:
        return np.asarray(arr.copy(), dtype=float)
    nx, ny, _ = arr.shape
    sx = factor if nx > 1 else 1.0
    sy = factor if ny > 1 else 1.0
    return np.asarray(ndimage.zoom(arr, (sx, sy, 1), order=1), dtype=float)


def apply_waterfall_baseline(x_axis: Any, y: Any, *, subtract_left_baseline: bool = False) -> np.ndarray:
    yy = np.asarray(y, dtype=float).ravel()
    if yy.size == 0:
        return yy
    if not subtract_left_baseline:
        return yy
    x = np.asarray(x_axis, dtype=float).ravel()
    n = min(x.size, yy.size)
    if n < 4:
        return yy[:n]
    x = x[:n]
    y0 = yy[:n]
    out = y0.copy()
    finite = np.isfinite(x) & np.isfinite(y0)
    if np.sum(finite) < 4:
        return out
    x_f = x[finite]
    y_f = y0[finite]
    order = np.argsort(x_f)
    x_sorted = x_f[order]
    y_sorted = y_f[order]
    m = x_sorted.size
    n_edge = max(3, int(np.ceil(0.12 * m)))
    n_edge = min(n_edge, max(3, m // 2))
    idx = np.r_[0:n_edge, m - n_edge : m]
    try:
        k, b = np.polyfit(x_sorted[idx], y_sorted[idx], 1)
        out[finite] = y0[finite] - (k * x_f + b)
        return out
    except Exception:
        return out


def smooth_waterfall_spectrum(y: Any, *, method: str = "Gaussian", value: float = 0.0) -> np.ndarray:
    yy = np.asarray(y, dtype=float)
    if float(value) <= 0:
        return yy
    if method == "Savitzky-Golay":
        win = int(value)
        if win % 2 == 0:
            win += 1
        if win < 3:
            win = 3
        if win < yy.shape[0]:
            return np.asarray(savgol_filter(yy, win, 2), dtype=float)
        return yy
    if method == "Gaussian":
        return np.asarray(ndimage.gaussian_filter1d(yy, float(value)), dtype=float)
    if method == "Moving Avg":
        win = max(1, int(value))
        kernel = np.ones(win) / float(win)
        return np.asarray(np.convolve(yy, kernel, mode="same"), dtype=float)
    return yy


def analyze_single_peak(x_full: Any, y_full: Any, limit_range: Sequence[float], use_fit: bool = False) -> tuple[float, float]:
    x = np.asarray(x_full, dtype=float).ravel()
    y = np.asarray(y_full, dtype=float).ravel()
    n = min(x.size, y.size)
    if n == 0:
        return np.nan, np.nan
    x = x[:n]
    y = y[:n]
    min_v, max_v = sorted((float(limit_range[0]), float(limit_range[1])))
    mask = (x >= min_v) & (x <= max_v)
    if not np.any(mask):
        return np.nan, np.nan
    x_sub = x[mask]
    y_sub = y[mask]
    idx_max = int(np.argmax(y_sub))
    res_v = float(x_sub[idx_max])
    res_i = float(y_sub[idx_max])
    if bool(use_fit) and len(x_sub) >= 4:
        try:
            p_min = float(np.min(y_sub))
            p_max = float(np.max(y_sub))
            p_amp = p_max - p_min
            p_cen = res_v
            p_wid = (max_v - min_v) / 4.0
            popt, _ = curve_fit(gaussian, x_sub, y_sub, p0=[p_amp, p_cen, p_wid, p_min], maxfev=600)
            fit_v = float(popt[1])
            fit_i = float(popt[0] + popt[3])
            if min_v <= fit_v <= max_v:
                return fit_v, fit_i
        except Exception:
            pass
    return res_v, res_i


def auto_waterfall_offset(grid: Any, selected_indices: Any) -> float:
    arr = np.asarray(grid, dtype=float)
    if arr.ndim != 3:
        return 0.0
    nx, ny, nz = arr.shape
    flat = arr.reshape(nx * ny, nz)
    indices = np.asarray(selected_indices, dtype=int).ravel()
    if indices.size == 0:
        return 0.0
    indices = indices[(indices >= 0) & (indices < flat.shape[0])]
    if indices.size == 0:
        return 0.0
    selected = flat[indices]
    if selected.shape[0] > 200:
        idx = np.linspace(0, selected.shape[0] - 1, 200).astype(int)
        selected = selected[idx]
    try:
        amp = float(np.nanmedian(np.nanmax(selected, axis=1) - np.nanmin(selected, axis=1)))
    except Exception:
        amp = float(np.nanmax(selected) - np.nanmin(selected))
    if not np.isfinite(amp) or amp <= 0:
        return 0.0
    return float(amp * 1.2)


def peak_align_zero_grid(grid: Any, bias: Any, *, neg_range: Sequence[float], pos_range: Sequence[float]) -> dict[str, Any]:
    arr = np.asarray(grid, dtype=float)
    bias_axis = np.asarray(bias, dtype=float).ravel()
    if arr.ndim != 3:
        raise ValueError("waterfall peak alignment expects grid (x, y, bias)")
    if arr.shape[2] != bias_axis.size:
        raise ValueError("bias length must match grid spectral axis")
    r1_min, r1_max = sorted((float(neg_range[0]), float(neg_range[1])))
    r2_min, r2_max = sorted((float(pos_range[0]), float(pos_range[1])))
    idx1 = np.where((bias_axis >= r1_min) & (bias_axis <= r1_max))[0]
    idx2 = np.where((bias_axis >= r2_min) & (bias_axis <= r2_max))[0]
    if len(idx1) == 0 or len(idx2) == 0:
        raise ValueError("Selected peak-align ranges are out of bias range.")

    nx, ny, nz = arr.shape
    cube1 = arr[:, :, idx1]
    cube2 = arr[:, :, idx2]
    max_idx1 = np.argmax(np.abs(cube1), axis=2)
    max_idx2 = np.argmax(np.abs(cube2), axis=2)
    v_minus = bias_axis[idx1[0] + max_idx1]
    v_plus = bias_axis[idx2[0] + max_idx2]
    off_v_map = (v_plus + v_minus) / 2.0

    flat_grid = arr.reshape(-1, nz)
    flat_off_v = off_v_map.ravel()
    flat_new = np.zeros_like(flat_grid)
    for k in range(flat_new.shape[0]):
        y_raw = flat_grid[k]
        v_query = bias_axis + flat_off_v[k]
        f = interp1d(bias_axis, y_raw, kind="linear", bounds_error=False, fill_value=np.nan)
        flat_new[k] = f(v_query)

    temp_grid = flat_new.reshape(nx, ny, nz)
    valid_z_mask = ~np.isnan(temp_grid).any(axis=(0, 1))
    if not np.any(valid_z_mask):
        proc_grid = np.nan_to_num(temp_grid, nan=0.0)
        proc_bias = bias_axis
    else:
        proc_grid = temp_grid[:, :, valid_z_mask]
        proc_bias = bias_axis[valid_z_mask]
    return {
        "aligned_grid": np.asarray(proc_grid, dtype=float),
        "aligned_bias_mV": np.asarray(proc_bias, dtype=float),
        "offset_map_mV": np.asarray(off_v_map, dtype=float),
        "algorithm": waterfall_algorithm("analystm.waterfall.peak_align_zero_grid"),
        "parameters": {"neg_range": [r1_min, r1_max], "pos_range": [r2_min, r2_max]},
    }


def run_waterfall_fit(
    grid: Any,
    bias: Any,
    *,
    selected_indices: Sequence[int],
    neg_range: Sequence[float],
    pos_range: Sequence[float],
    offset: float | None = None,
    use_fit: bool = False,
    subtract_left_baseline: bool = False,
    smooth_method: str | None = None,
    smooth_value: float = 0.0,
    bias_scale_factor: float = 1.0,
) -> dict[str, Any]:
    arr = np.asarray(grid, dtype=float)
    bias_raw = np.asarray(bias, dtype=float).ravel()
    if arr.ndim != 3:
        raise ValueError("waterfall fit expects grid (x, y, bias)")
    if arr.shape[2] != bias_raw.size:
        raise ValueError("bias length must match grid spectral axis")
    nx, ny, nz = arr.shape
    flat_grid = arr.reshape(nx * ny, nz)
    indices = np.asarray(selected_indices, dtype=int).ravel()
    indices = indices[(indices >= 0) & (indices < flat_grid.shape[0])]
    if indices.size == 0:
        raise ValueError("No waterfall spectra selected.")
    waterfall_offset = auto_waterfall_offset(arr, indices) if offset is None else float(offset)
    bias_scaled = scale_bias(bias_raw, bias_scale_factor)
    neg_unscaled = (unscale_bias_value(float(neg_range[0]), bias_scale_factor), unscale_bias_value(float(neg_range[1]), bias_scale_factor))
    pos_unscaled = (unscale_bias_value(float(pos_range[0]), bias_scale_factor), unscale_bias_value(float(pos_range[1]), bias_scale_factor))

    selected_spectra = flat_grid[indices]
    res_neg_v: list[float] = []
    res_neg_yvis: list[float] = []
    res_pos_v: list[float] = []
    res_pos_yvis: list[float] = []
    for i in range(selected_spectra.shape[0]):
        y_data = selected_spectra[i, :]
        y_data = smooth_waterfall_spectrum(y_data, method=str(smooth_method or ""), value=float(smooth_value))
        y_data = apply_waterfall_baseline(bias_scaled, y_data, subtract_left_baseline=subtract_left_baseline)
        v_n, amp_n = analyze_single_peak(bias_raw, y_data, neg_unscaled, use_fit)
        y_vis_n = (amp_n + i * waterfall_offset) if not np.isnan(amp_n) else np.nan
        v_p, amp_p = analyze_single_peak(bias_raw, y_data, pos_unscaled, use_fit)
        y_vis_p = (amp_p + i * waterfall_offset) if not np.isnan(amp_p) else np.nan
        res_neg_v.append(v_n)
        res_neg_yvis.append(y_vis_n)
        res_pos_v.append(v_p)
        res_pos_yvis.append(y_vis_p)

    results = {
        "indices": np.asarray(indices, dtype=int),
        "neg": {"v": np.asarray(res_neg_v, dtype=float), "y_vis": np.asarray(res_neg_yvis, dtype=float)},
        "pos": {"v": np.asarray(res_pos_v, dtype=float), "y_vis": np.asarray(res_pos_yvis, dtype=float)},
    }
    return {
        "results": results,
        "algorithm": waterfall_algorithm(),
        "parameters": {
            "neg_range": [float(neg_range[0]), float(neg_range[1])],
            "pos_range": [float(pos_range[0]), float(pos_range[1])],
            "bias_scale_factor": float(bias_scale_factor),
            "offset": float(waterfall_offset),
            "use_fit": bool(use_fit),
            "subtract_left_baseline": bool(subtract_left_baseline),
            "smooth_method": str(smooth_method or ""),
            "smooth_value": float(smooth_value),
        },
        "summary": {
            "grid_shape": [int(v) for v in arr.shape],
            "trace_count": int(indices.size),
            "offset": float(waterfall_offset),
            "neg_valid_count": int(np.count_nonzero(np.isfinite(results["neg"]["v"]))),
            "pos_valid_count": int(np.count_nonzero(np.isfinite(results["pos"]["v"]))),
        },
    }


def export_waterfall_table(results: dict[str, Any]) -> np.ndarray | None:
    indices = np.asarray(results.get("indices", []), dtype=int)
    neg = results.get("neg", {})
    pos = results.get("pos", {})
    neg_v = np.asarray(neg.get("v", []), dtype=float)
    neg_y = np.asarray(neg.get("y_vis", []), dtype=float)
    pos_v = np.asarray(pos.get("v", []), dtype=float)
    pos_y = np.asarray(pos.get("y_vis", []), dtype=float)
    n = len(indices)
    if n == 0 or len(neg_v) != n or len(neg_y) != n or len(pos_v) != n or len(pos_y) != n:
        return None
    return np.column_stack([indices, neg_v, neg_y, pos_v, pos_y])


def waterfall_set_tag(set_idx: int | None = None) -> str:
    if set_idx is None or int(set_idx) < 0:
        return "Set"
    return f"Set{int(set_idx) + 1:02d}"


def waterfall_points_payload(
    results: dict[str, Any],
    *,
    set_index: int | None = None,
    name: str = "",
    offset: float = 0.0,
    neg_range: Sequence[float] | None = None,
    pos_range: Sequence[float] | None = None,
    use_fit: bool = False,
    bias_scale_factor: float = 1.0,
    point_style: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    table = export_waterfall_table(results)
    if table is None:
        return None
    style = {
        "neg_color": "#d81b60",
        "pos_color": "#00acc1",
        "neg_symbol": "o",
        "pos_symbol": "o",
        "size": 8,
    }
    if point_style:
        style.update(dict(point_style))
    indices = np.asarray(results.get("indices", []), dtype=int)
    neg = results.get("neg", {})
    pos = results.get("pos", {})
    neg_v = scale_bias(neg.get("v", []), bias_scale_factor)
    neg_y = np.asarray(neg.get("y_vis", []), dtype=float)
    pos_v = scale_bias(pos.get("v", []), bias_scale_factor)
    pos_y = np.asarray(pos.get("y_vis", []), dtype=float)
    points = []
    n_rows = min(len(indices), len(neg_v), len(neg_y), len(pos_v), len(pos_y))
    for i in range(n_rows):
        points.append(
            {
                "trace_index": int(i),
                "global_index": int(indices[i]),
                "neg_bias_scaled": float(neg_v[i]) if np.isfinite(neg_v[i]) else None,
                "neg_y_vis": float(neg_y[i]) if np.isfinite(neg_y[i]) else None,
                "pos_bias_scaled": float(pos_v[i]) if np.isfinite(pos_v[i]) else None,
                "pos_y_vis": float(pos_y[i]) if np.isfinite(pos_y[i]) else None,
            }
        )
    return {
        "set_index": (int(set_index) + 1) if set_index is not None and int(set_index) >= 0 else None,
        "set_tag": waterfall_set_tag(set_index),
        "name": str(name),
        "offset": float(offset),
        "neg_range": [float(v) for v in neg_range] if neg_range is not None else [],
        "pos_range": [float(v) for v in pos_range] if pos_range is not None else [],
        "use_fit": bool(use_fit),
        "point_style": style,
        "points": points,
    }
