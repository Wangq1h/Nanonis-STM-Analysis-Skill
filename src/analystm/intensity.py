from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from scipy import ndimage
from scipy.interpolate import interp1d
from scipy.signal import savgol_filter


INTENSITY_SOURCE_MAPPING = (
    "linecutmap_intensity.BaseLinecutDisplayWindow intensity processing, "
    "H/V cut extraction, and Peak Align Zero calibration"
)
Z_RATIO_SOURCE_MAPPING = "qpi_pr_pqi multi-impurity negative/positive z_ratio denominator regularization"


def normalize_intensity_mode(mode: str | None) -> str:
    raw = str(mode or "didv").strip().lower().replace(" ", "")
    aliases = {
        "didv": "didv",
        "di/dv": "didv",
        "dI/dV".lower(): "didv",
        "d2": "d2",
        "d²i/dv²": "d2",
        "d2i/dv2": "d2",
        "d²I/dV²".lower(): "d2",
        "neg_d3": "neg_d3",
        "-d3": "neg_d3",
        "-d³i/dv³": "neg_d3",
        "-d3i/dv3": "neg_d3",
        "-d³I/dV³".lower(): "neg_d3",
    }
    return aliases.get(raw, "didv")


def intensity_algorithm(engine: str, *, source_mapping: str = INTENSITY_SOURCE_MAPPING) -> dict[str, str]:
    return {
        "name": "AnalySTM linecut intensity backend",
        "engine": engine,
        "pysidam_source_mapping": source_mapping,
    }


def apply_intensity_signal_mode(bias_axis: Sequence[float], data: Any, mode: str = "didv") -> np.ndarray:
    arr = np.asarray(data, dtype=float)
    bias = np.asarray(bias_axis, dtype=float).ravel()
    mode_name = normalize_intensity_mode(mode)
    if mode_name == "didv":
        return arr
    if bias.size < 2 or arr.shape[-1] != bias.size:
        return np.zeros_like(arr, dtype=float)
    deriv = np.gradient(arr, bias, axis=-1)
    if mode_name == "d2":
        return np.asarray(deriv, dtype=float)
    return np.asarray(-np.gradient(deriv, bias, axis=-1), dtype=float)


def smooth_intensity_data(
    data: Any,
    *,
    method: str | None = None,
    value: float = 0.0,
    axis: int = -1,
) -> np.ndarray:
    arr = np.asarray(data, dtype=float)
    method_name = str(method or "").strip().lower()
    if not method_name or float(value) <= 0:
        return arr
    if method_name in {"savitzky-golay", "savitzky_golay", "savgol", "sg"}:
        win = int(value)
        if win % 2 == 0:
            win += 1
        if win < 3:
            win = 3
        n_axis = arr.shape[axis]
        if win < n_axis:
            return np.asarray(savgol_filter(arr, win, 2, axis=axis), dtype=float)
        return arr
    if method_name in {"gaussian", "gauss"}:
        return np.asarray(ndimage.gaussian_filter1d(arr, sigma=float(value), axis=axis), dtype=float)
    if method_name in {"moving avg", "moving_avg", "moving-average", "movingaverage"}:
        win = max(1, int(value))
        kernel = np.ones(win, dtype=float) / float(win)
        return np.asarray(np.apply_along_axis(lambda m: np.convolve(m, kernel, mode="same"), axis=axis, arr=arr), dtype=float)
    return arr


def remove_linear_baseline_1d(x_axis: Sequence[float], y: Sequence[float]) -> np.ndarray:
    yy = np.asarray(y, dtype=float).ravel()
    if yy.size == 0:
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
    m = x_f.size
    n_edge = max(3, int(np.ceil(0.12 * m)))
    n_edge = min(n_edge, max(3, m // 2))
    idx = np.r_[0:n_edge, m - n_edge : m]
    try:
        k, b = np.polyfit(x_f[idx], y_f[idx], 1)
        out[finite] = y0[finite] - (k * x_f + b)
        return out
    except Exception:
        return out


def remove_linear_baseline_2d(x_axis: Sequence[float], data2d: Any) -> np.ndarray:
    arr = np.asarray(data2d, dtype=float)
    if arr.ndim != 2 or arr.size == 0:
        return arr
    x = np.asarray(x_axis, dtype=float).ravel()
    n = min(arr.shape[1], x.size)
    if n < 4:
        return arr[:, :n]
    x = x[:n]
    out = np.asarray(arr[:, :n], dtype=float).copy()
    for i in range(out.shape[0]):
        out[i, :] = remove_linear_baseline_1d(x, out[i, :])
    return out


def select_bias_indices_in_range(bias: Sequence[float], lo: float, hi: float) -> np.ndarray:
    b = np.asarray(bias, dtype=float).ravel()
    if b.size == 0:
        return np.array([], dtype=int)
    low, high = sorted([float(lo), float(hi)])
    mask = (b >= low) & (b <= high)
    idx = np.where(mask)[0]
    if idx.size >= 2:
        return idx.astype(int, copy=False)
    if b.size <= 1:
        return np.array([0], dtype=int)
    center = 0.5 * (low + high)
    i0 = int(np.argmin(np.abs(b - center)))
    i1 = i0 - 1 if i0 > 0 else i0 + 1
    i1 = int(np.clip(i1, 0, b.size - 1))
    return np.array(sorted(set([i0, i1])), dtype=int)


def scale_bias(bias_array: Sequence[float], scale_factor: float = 1.0) -> np.ndarray:
    try:
        factor = float(scale_factor)
    except Exception:
        factor = 1.0
    if factor == 0:
        factor = 1.0
    return np.asarray(bias_array, dtype=float) / factor


def unscale_bias_value(scaled_value: float, scale_factor: float = 1.0) -> float:
    try:
        factor = float(scale_factor)
    except Exception:
        factor = 1.0
    if factor == 0:
        factor = 1.0
    return float(scaled_value) * factor


def process_intensity_matrix(
    bias_axis: Sequence[float],
    spectra_data: Any,
    *,
    signal_mode: str = "didv",
    smooth_method: str | None = None,
    smooth_value: float = 0.0,
    line_interp_factor: float = 1.0,
    bias_interp_factor: float = 1.0,
    bias_range: tuple[float, float] | None = None,
    remove_linear_baseline: bool = False,
    h_axis: Sequence[float] | None = None,
    bias_scale_factor: float = 1.0,
) -> dict[str, Any]:
    data = np.asarray(spectra_data, dtype=float)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    if data.ndim != 2:
        raise ValueError("intensity spectra_data must be a 1D spectrum or a 2D spectra-by-bias matrix")
    bias = np.asarray(bias_axis, dtype=float).ravel()
    if bias.size == 0:
        raise ValueError("intensity bias axis is empty")
    if data.shape[1] != bias.size:
        raise ValueError("intensity data must have bias on axis 1 with the same length as bias_axis")

    data = smooth_intensity_data(data, method=smooth_method, value=float(smooth_value), axis=1)
    data = apply_intensity_signal_mode(bias, data, mode=signal_mode)

    line_factor = float(line_interp_factor)
    if line_factor > 1:
        data = np.asarray(ndimage.zoom(data, (line_factor, 1), order=1), dtype=float)

    bias_factor = float(bias_interp_factor)
    if bias_factor > 1:
        data = np.asarray(ndimage.zoom(data, (1, bias_factor), order=1), dtype=float)
        bias = np.linspace(float(bias[0]), float(bias[-1]), int(data.shape[1]), dtype=float)

    if bias_range is not None:
        idx = select_bias_indices_in_range(bias, float(bias_range[0]), float(bias_range[1]))
        data = data[:, idx]
        bias = bias[idx]

    if remove_linear_baseline:
        data = remove_linear_baseline_2d(bias, data)
        bias = bias[: data.shape[1]]

    h_arr = np.asarray(h_axis, dtype=float).ravel() if h_axis is not None else np.array([], dtype=float)
    if h_arr.size != data.shape[0]:
        h_arr = np.arange(data.shape[0], dtype=float)

    return {
        "processed_data": np.asarray(data, dtype=float),
        "processed_bias": np.asarray(bias, dtype=float),
        "processed_bias_scaled": scale_bias(bias, bias_scale_factor),
        "h_axis": h_arr,
        "algorithm": intensity_algorithm("analystm.intensity.process_intensity_matrix"),
        "parameters": {
            "signal_mode": normalize_intensity_mode(signal_mode),
            "smooth_method": str(smooth_method or ""),
            "smooth_value": float(smooth_value),
            "line_interp_factor": float(line_interp_factor),
            "bias_interp_factor": float(bias_interp_factor),
            "bias_range_mV": [float(bias_range[0]), float(bias_range[1])] if bias_range is not None else [],
            "remove_linear_baseline": bool(remove_linear_baseline),
            "bias_scale_factor": float(bias_scale_factor),
        },
    }


def nearest_bias_index(bias_axis: Sequence[float], target_mV: float) -> int:
    bias = np.asarray(bias_axis, dtype=float).ravel()
    if bias.size == 0:
        raise ValueError("bias axis is empty")
    return int(np.clip(np.abs(bias - float(target_mV)).argmin(), 0, bias.size - 1))


def extract_bias_slice(bias_axis: Sequence[float], cube: Any, target_mV: float) -> dict[str, Any]:
    bias = np.asarray(bias_axis, dtype=float).ravel()
    arr = np.asarray(cube, dtype=float)
    if arr.ndim < 1 or arr.shape[-1] != bias.size:
        raise ValueError("cube must have bias on the last axis")
    idx = nearest_bias_index(bias, target_mV)
    return {
        "map": np.asarray(arr[..., idx], dtype=float),
        "bias_index": idx,
        "bias_mV": float(bias[idx]),
        "requested_bias_mV": float(target_mV),
        "algorithm": intensity_algorithm("analystm.intensity.extract_bias_slice"),
    }


def extract_h_cut(
    data2d: Any,
    bias_axis: Sequence[float],
    *,
    h_value: float,
    h_axis: Sequence[float] | None = None,
    integrate_range: tuple[float, float] | None = None,
) -> dict[str, Any]:
    data = np.asarray(data2d, dtype=float)
    if data.ndim != 2:
        raise ValueError("H-cut data must be a 2D matrix")
    bias = np.asarray(bias_axis, dtype=float).ravel()
    if bias.size != data.shape[1]:
        raise ValueError("bias axis length must match H-cut data axis 1")
    axis = np.asarray(h_axis, dtype=float).ravel() if h_axis is not None else np.arange(data.shape[0], dtype=float)
    if axis.size != data.shape[0]:
        axis = np.arange(data.shape[0], dtype=float)
    idx_i = int(np.clip(np.abs(axis - float(h_value)).argmin(), 0, data.shape[0] - 1))
    if integrate_range is not None:
        lo, hi = sorted([float(integrate_range[0]), float(integrate_range[1])])
        mask = (axis >= lo) & (axis <= hi)
        if not np.any(mask):
            mask = np.zeros_like(axis, dtype=bool)
            mask[idx_i] = True
        trace = data[mask].sum(axis=0)
    else:
        mask = np.zeros_like(axis, dtype=bool)
        mask[idx_i] = True
        trace = data[idx_i]
    return {
        "x": bias,
        "y": np.asarray(trace, dtype=float),
        "selected_index": idx_i,
        "selected_h": float(axis[idx_i]),
        "integrated_count": int(max(1, np.count_nonzero(mask))),
        "algorithm": intensity_algorithm("analystm.intensity.extract_h_cut"),
    }


def extract_v_cut(
    data2d: Any,
    bias_axis: Sequence[float],
    *,
    target_mV: float,
    h_axis: Sequence[float] | None = None,
    integrate_bias_range: tuple[float, float] | None = None,
) -> dict[str, Any]:
    data = np.asarray(data2d, dtype=float)
    if data.ndim != 2:
        raise ValueError("V-cut data must be a 2D matrix")
    bias = np.asarray(bias_axis, dtype=float).ravel()
    if bias.size != data.shape[1]:
        raise ValueError("bias axis length must match V-cut data axis 1")
    axis = np.asarray(h_axis, dtype=float).ravel() if h_axis is not None else np.arange(data.shape[0], dtype=float)
    if axis.size != data.shape[0]:
        axis = np.arange(data.shape[0], dtype=float)
    idx_b = nearest_bias_index(bias, target_mV)
    if integrate_bias_range is not None:
        lo, hi = sorted([float(integrate_bias_range[0]), float(integrate_bias_range[1])])
        mask = (bias >= lo) & (bias <= hi)
        if not np.any(mask):
            mask = np.zeros_like(bias, dtype=bool)
            mask[idx_b] = True
        profile = data[:, mask].sum(axis=1)
    else:
        mask = np.zeros_like(bias, dtype=bool)
        mask[idx_b] = True
        profile = data[:, idx_b]
    return {
        "x": axis,
        "y": np.asarray(profile, dtype=float),
        "selected_index": idx_b,
        "selected_bias_mV": float(bias[idx_b]),
        "integrated_count": int(max(1, np.count_nonzero(mask))),
        "algorithm": intensity_algorithm("analystm.intensity.extract_v_cut"),
    }


def peak_align_zero_cube(
    bias_axis: Sequence[float],
    cube: Any,
    *,
    neg_window: tuple[float, float],
    pos_window: tuple[float, float],
) -> dict[str, Any]:
    bias = np.asarray(bias_axis, dtype=float).ravel()
    grid = np.asarray(cube, dtype=float)
    if grid.ndim < 2:
        raise ValueError("peak-align-zero cube must include at least one spatial axis and one bias axis")
    if bias.size != grid.shape[-1]:
        raise ValueError("cube last axis must match bias_axis length")
    r1_min, r1_max = sorted([float(neg_window[0]), float(neg_window[1])])
    r2_min, r2_max = sorted([float(pos_window[0]), float(pos_window[1])])
    idx1 = np.where((bias >= r1_min) & (bias <= r1_max))[0]
    idx2 = np.where((bias >= r2_min) & (bias <= r2_max))[0]
    if len(idx1) == 0 or len(idx2) == 0:
        raise ValueError("selected peak-align-zero ROI is out of bias range")

    nz = int(grid.shape[-1])
    spatial_shape = grid.shape[:-1]
    cube1 = grid[..., idx1]
    cube2 = grid[..., idx2]
    max_idx1 = np.argmax(np.abs(cube1), axis=-1)
    max_idx2 = np.argmax(np.abs(cube2), axis=-1)
    v_minus = bias[idx1[0] + max_idx1]
    v_plus = bias[idx2[0] + max_idx2]
    off_v_map = (v_plus + v_minus) / 2.0

    target_bias = bias
    flat_grid = grid.reshape(-1, nz)
    flat_off_v = off_v_map.ravel()
    flat_new = np.zeros_like(flat_grid)
    for k in range(flat_new.shape[0]):
        y_raw = flat_grid[k]
        v_query = target_bias + flat_off_v[k]
        interpolator = interp1d(bias, y_raw, kind="linear", bounds_error=False, fill_value=np.nan)
        flat_new[k] = interpolator(v_query)

    temp_grid = flat_new.reshape(*spatial_shape, nz)
    spatial_axes = tuple(range(temp_grid.ndim - 1))
    valid_z_mask = ~np.isnan(temp_grid).any(axis=spatial_axes)
    if not np.any(valid_z_mask):
        aligned_cube = np.nan_to_num(temp_grid, nan=0.0)
        aligned_bias = target_bias
    else:
        aligned_cube = temp_grid[..., valid_z_mask]
        aligned_bias = target_bias[valid_z_mask]

    return {
        "aligned_cube": np.asarray(aligned_cube, dtype=float),
        "aligned_bias_mV": np.asarray(aligned_bias, dtype=float),
        "offset_map_mV": np.asarray(off_v_map, dtype=float),
        "v_minus_map_mV": np.asarray(v_minus, dtype=float),
        "v_plus_map_mV": np.asarray(v_plus, dtype=float),
        "valid_z_mask": np.asarray(valid_z_mask, dtype=bool),
        "algorithm": intensity_algorithm("analystm.intensity.peak_align_zero_cube"),
        "parameters": {
            "neg_window_mV": [r1_min, r1_max],
            "pos_window_mV": [r2_min, r2_max],
        },
    }


def compute_z_ratio_map(
    bias_axis: Sequence[float],
    cube: Any,
    *,
    energy_mV: float,
    numerator: str = "negative",
    eps_rel: float = 1e-6,
) -> dict[str, Any]:
    bias = np.asarray(bias_axis, dtype=float).ravel()
    arr = np.asarray(cube)
    if arr.ndim < 2:
        raise ValueError("Z-ratio cube must include at least one spatial axis and one bias axis")
    if arr.shape[-1] != bias.size:
        raise ValueError("cube last axis must match bias_axis length")
    energy = abs(float(energy_mV))
    idx_pos = nearest_bias_index(bias, energy)
    idx_neg = nearest_bias_index(bias, -energy)
    g_pos = np.asarray(arr[..., idx_pos])
    g_neg = np.asarray(arr[..., idx_neg])
    num_mode = str(numerator or "negative").strip().lower()
    if num_mode in {"positive", "pos", "+", "positive_over_negative"}:
        num = g_pos
        den = g_neg
        numerator_label = "positive"
        denominator_label = "negative"
    else:
        num = g_neg
        den = g_pos
        numerator_label = "negative"
        denominator_label = "positive"

    denom_abs = np.abs(den)
    max_den = float(np.max(denom_abs)) if denom_abs.size else 0.0
    if max_den <= 0.0:
        mask_zero = np.ones_like(denom_abs, dtype=bool)
        z_ratio = np.zeros_like(denom_abs, dtype=float)
    else:
        mask_zero = denom_abs < (1e-12 * max_den)
        eps_floor = max(1e-12 * max_den, np.finfo(float).eps * max_den)
        eps_map = np.maximum(eps_floor, float(eps_rel) * denom_abs)
        phase = np.exp(1j * np.angle(den + 1e-30))
        denom_safe = den + phase * eps_map
        with np.errstate(divide="ignore", invalid="ignore"):
            z_ratio = np.real(num / denom_safe)
        z_ratio = np.asarray(np.nan_to_num(z_ratio, nan=0.0, posinf=0.0, neginf=0.0), dtype=float)
        z_ratio[mask_zero] = 0.0

    return {
        "z_ratio_map": np.asarray(z_ratio, dtype=float),
        "numerator_map": np.asarray(num),
        "denominator_map": np.asarray(den),
        "mask_zero": np.asarray(mask_zero, dtype=bool),
        "positive_bias_mV": float(bias[idx_pos]),
        "negative_bias_mV": float(bias[idx_neg]),
        "positive_index": int(idx_pos),
        "negative_index": int(idx_neg),
        "algorithm": intensity_algorithm(
            "analystm.intensity.compute_z_ratio_map",
            source_mapping=Z_RATIO_SOURCE_MAPPING,
        ),
        "parameters": {
            "energy_mV": float(energy_mV),
            "abs_energy_mV": energy,
            "numerator": numerator_label,
            "denominator": denominator_label,
            "eps_rel": float(eps_rel),
        },
    }
