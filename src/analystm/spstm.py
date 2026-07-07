from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from scipy import ndimage, signal
from scipy.interpolate import interp1d
from scipy.optimize import curve_fit

from .fft_windowing import build_windowed_fft_complex


DIDV_SOURCE_MAPPING = "spstm_didv_contrast.SPSTMDidVContrastWindow.auto_detect_offset, SPSTMDidVContrastWindow.run_pipeline, and SPSTMDidVContrastWindow.perform_fit"
MAP_SOURCE_MAPPING = "spstm_map_contrast/SPSTMTopographyContrastWindow._sample_linecut, _normalize_profile, and _apply_background_mode"
QPI_SOURCE_MAPPING = "spstm_qpi_contrast.SPSTMQPIContrastWindow._apply_background_mode, _apply_presymmetry, _rotate_90, SPSTMQPIContrastWindow._build_result, and SPSTMQPIContrastWindow._build_spin_contrast"


def gaussian_func(x: Any, amp: float, cen: float, wid: float, bg: float) -> np.ndarray:
    return bg + amp * np.exp(-((np.asarray(x, dtype=float) - cen) ** 2) / (2 * wid**2))


def spstm_algorithm(engine: str, source_mapping: str) -> dict[str, str]:
    return {"name": "AnalySTM SPSTM backend", "engine": engine, "pysidam_source_mapping": source_mapping}


def auto_detect_offset(x: Any, y: Any, *, smooth_sigma: float = 2.0, fit_points: int = 5) -> dict[str, float]:
    x_arr = np.asarray(x, dtype=float).ravel()
    y_arr = np.asarray(y, dtype=float).ravel()
    if x_arr.size < 5 or x_arr.size != y_arr.size:
        raise ValueError("auto offset requires matching x/y arrays with at least 5 points")
    y_smooth = ndimage.gaussian_filter1d(y_arr, sigma=float(smooth_sigma))
    idx_zero = int(np.argmin(np.abs(x_arr)))
    if idx_zero < 3 or idx_zero > x_arr.size - 3:
        raise ValueError("zero point is too close to edge for SPSTM auto offset")
    left_y = y_smooth[:idx_zero]
    right_y = y_smooth[idx_zero:]
    if left_y.size == 0 or right_y.size == 0:
        raise ValueError("auto offset requires data on both sides of zero")
    idx_l = int(np.argmax(left_y))
    idx_r = int(idx_zero + np.argmax(right_y))

    def fit_peak_pos(idx_center: int) -> float:
        n = int(fit_points)
        start = max(0, idx_center - n)
        end = min(x_arr.size, idx_center + n + 1)
        x_sub = x_arr[start:end]
        y_sub = y_smooth[start:end]
        if x_sub.size < 3:
            return float(x_arr[idx_center])
        try:
            p0 = [float(np.max(y_sub) - np.min(y_sub)), float(x_arr[idx_center]), float((x_sub[-1] - x_sub[0]) / 4.0), float(np.min(y_sub))]
            popt, _ = curve_fit(gaussian_func, x_sub, y_sub, p0=p0, maxfev=1000)
            return float(popt[1])
        except Exception:
            return float(x_arr[idx_center])

    pos_l = fit_peak_pos(idx_l)
    pos_r = fit_peak_pos(idx_r)
    return {"left_peak": pos_l, "right_peak": pos_r, "offset": float((pos_l + pos_r) / 2.0)}


def _process_y(
    y: Any,
    x_used: np.ndarray,
    ref_current: Any = None,
    *,
    symmetrize: bool = False,
    smooth_method: str = "None",
    smooth_param: float = 0.0,
    norm_mode: str = "None",
) -> np.ndarray:
    arr = np.asarray(y, dtype=float).ravel().copy()
    if symmetrize:
        try:
            u_x, u_idx = np.unique(x_used, return_index=True)
            u_y = arr[u_idx]
            f = interp1d(u_x, u_y, kind="linear", bounds_error=False, fill_value=0.0)
            arr = (arr + f(-x_used)) / 2.0
        except Exception:
            pass
    if smooth_param > 0:
        if "Gaussian" in smooth_method:
            arr = ndimage.gaussian_filter1d(arr, smooth_param)
        elif "Boxcar" in smooth_method:
            arr = ndimage.uniform_filter1d(arr, size=int(max(1, smooth_param)))
        elif "Savitzky" in smooth_method:
            w = int(smooth_param)
            w = w + 1 if w % 2 == 0 else w
            w = max(3, w)
            try:
                arr = signal.savgol_filter(arr, w, 2 if w > 2 else 1)
            except Exception:
                pass
    try:
        if "Sum" in norm_mode:
            denom = np.sum(np.abs(arr))
            arr = arr / (denom if denom != 0 else 1)
        elif "Max" in norm_mode:
            denom = np.max(np.abs(arr))
            arr = arr / (denom if denom != 0 else 1)
        elif "First" in norm_mode:
            arr = arr / (arr[0] if arr.size and arr[0] != 0 else 1)
        elif "Last" in norm_mode:
            arr = arr / (arr[-1] if arr.size and arr[-1] != 0 else 1)
        elif "Feenstra" in norm_mode and ref_current is not None:
            current = np.asarray(ref_current, dtype=float).ravel().copy()
            mask = (np.abs(current) > 1e-15) & (np.abs(x_used) > 1e-6)
            factor = np.zeros_like(arr)
            factor[mask] = x_used[mask] / current[mask]
            arr = arr * factor
    except Exception:
        pass
    return np.asarray(arr, dtype=float)


def process_didv_contrast(
    x_a: Any,
    y_a: Any,
    *,
    x_b: Any = None,
    y_b: Any = None,
    ref_current_a: Any = None,
    ref_current_b: Any = None,
    bias_scale_a: float = 1.0,
    bias_scale_b: float = 1.0,
    offset: float = 0.0,
    symmetrize: bool = False,
    smooth_method_a: str = "None",
    smooth_method_b: str = "None",
    smooth_param_a: float = 0.0,
    smooth_param_b: float = 0.0,
    norm_mode_a: str = "None",
    norm_mode_b: str = "None",
) -> dict[str, Any]:
    x = np.asarray(x_a, dtype=float).ravel() / float(bias_scale_a or 1.0) - float(offset)
    ya = np.asarray(y_a, dtype=float).ravel()
    if x.size != ya.size:
        raise ValueError("x_a and y_a must have matching lengths")
    yb = None
    if y_b is not None:
        yb_raw = np.asarray(y_b, dtype=float).ravel()
        xb = np.asarray(x_b if x_b is not None else x_a, dtype=float).ravel() / float(bias_scale_b or 1.0) - float(offset)
        order = np.argsort(xb)
        yb = np.interp(x, xb[order], yb_raw[order])
        if ref_current_b is not None:
            ib = np.asarray(ref_current_b, dtype=float).ravel()
            ref_current_b = np.interp(x, xb[order], ib[order])

    proc_a = _process_y(
        ya,
        x,
        ref_current_a,
        symmetrize=symmetrize,
        smooth_method=smooth_method_a,
        smooth_param=smooth_param_a,
        norm_mode=norm_mode_a,
    )
    proc_b = (
        _process_y(
            yb,
            x,
            ref_current_b,
            symmetrize=symmetrize,
            smooth_method=smooth_method_b,
            smooth_param=smooth_param_b,
            norm_mode=norm_mode_b,
        )
        if yb is not None
        else None
    )
    return {
        "x": x,
        "y_a": proc_a,
        "y_b": proc_b if proc_b is not None else np.asarray([], dtype=float),
        "algorithm": spstm_algorithm("analystm.spstm.process_didv_contrast", DIDV_SOURCE_MAPPING),
        "parameters": {
            "bias_scale_a": float(bias_scale_a),
            "bias_scale_b": float(bias_scale_b),
            "offset": float(offset),
            "symmetrize": bool(symmetrize),
            "smooth_method_a": str(smooth_method_a),
            "smooth_method_b": str(smooth_method_b),
            "smooth_param_a": float(smooth_param_a),
            "smooth_param_b": float(smooth_param_b),
            "norm_mode_a": str(norm_mode_a),
            "norm_mode_b": str(norm_mode_b),
        },
        "summary": {"points": int(x.size), "has_b": bool(proc_b is not None)},
    }


def finite_or_zero(arr: Any) -> np.ndarray:
    out = np.asarray(arr, dtype=float)
    if out.size == 0:
        return out
    finite = out[np.isfinite(out)]
    fill = float(np.nanmean(finite)) if finite.size else 0.0
    return np.nan_to_num(out, nan=fill, posinf=fill, neginf=fill)


def background_2d(data: Any, mode: str = "Raw") -> np.ndarray:
    out = np.asarray(data, dtype=float).copy()
    if out.ndim != 2:
        raise ValueError("background_2d expects a 2D map")
    mode = str(mode or "Raw").strip()
    ny, nx = out.shape
    if mode in {"Sub Global Mean"}:
        out -= np.nanmean(out)
    elif mode in {"Sub Line Mean (0-order)", "Sub Line Mean (Row)"}:
        out -= np.nanmean(out, axis=1, keepdims=True)
    elif mode == "Sub Line Mean (Row+Col)":
        out -= np.nanmean(out, axis=1, keepdims=True)
        out -= np.nanmean(out, axis=0, keepdims=True)
    elif mode == "Sub Line Linear (1-order)":
        x = np.arange(nx, dtype=float)
        for i in range(ny):
            fit = np.polyfit(x, out[i], 1)
            out[i] -= np.polyval(fit, x)
    elif mode in {"Sub Plane (Global)", "Sub Plane"}:
        xg, yg = np.meshgrid(np.arange(nx, dtype=float), np.arange(ny, dtype=float))
        a = np.c_[xg.ravel(), yg.ravel(), np.ones(xg.size)]
        c, _, _, _ = np.linalg.lstsq(a, out.ravel(), rcond=None)
        out -= c[0] * xg + c[1] * yg + c[2]
    elif mode == "Sub Parabolic (Global)":
        xg, yg = np.meshgrid(np.arange(nx, dtype=float), np.arange(ny, dtype=float))
        xf = xg.ravel()
        yf = yg.ravel()
        a = np.c_[xf**2, yf**2, xf * yf, xf, yf, np.ones(xf.size)]
        c, _, _, _ = np.linalg.lstsq(a, out.ravel(), rcond=None)
        out -= c[0] * xg**2 + c[1] * yg**2 + c[2] * xg * yg + c[3] * xg + c[4] * yg + c[5]
    elif mode == "Differentiate (X-deriv)":
        out = np.gradient(out, axis=1)
    return np.asarray(out, dtype=float)


def sample_linecut(data: Any, *, scan_size_nm: float, p1_nm: Sequence[float], p2_nm: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    arr = np.asarray(data, dtype=float)
    if arr.ndim != 2 or float(scan_size_nm) <= 0:
        raise ValueError("sample_linecut expects a 2D map and positive scan size")
    ny, nx = arr.shape
    x0 = float(np.clip(p1_nm[0], 0.0, scan_size_nm)) / float(scan_size_nm) * max(0, nx - 1)
    x1 = float(np.clip(p2_nm[0], 0.0, scan_size_nm)) / float(scan_size_nm) * max(0, nx - 1)
    y0 = float(np.clip(p1_nm[1], 0.0, scan_size_nm)) / float(scan_size_nm) * max(0, ny - 1)
    y1 = float(np.clip(p2_nm[1], 0.0, scan_size_nm)) / float(scan_size_nm) * max(0, ny - 1)
    length_nm = float(np.hypot(float(p2_nm[0]) - float(p1_nm[0]), float(p2_nm[1]) - float(p1_nm[1])))
    n_samples = max(2, int(np.ceil(max(np.hypot(x1 - x0, y1 - y0), 2))))
    xs = np.linspace(x0, x1, n_samples)
    ys = np.linspace(y0, y1, n_samples)
    zi = ndimage.map_coordinates(arr, np.vstack((ys, xs)), order=1, mode="nearest")
    return np.linspace(0.0, length_nm, n_samples), np.asarray(zi, dtype=float)


def normalize_profile(values: Any) -> np.ndarray:
    arr = np.asarray(values, dtype=float).ravel().copy()
    finite = np.isfinite(arr)
    if not np.any(finite):
        return arr
    arr[~finite] = np.nan
    arr = arr - np.nanmean(arr)
    scale = float(np.nanmax(np.abs(arr))) if np.any(np.isfinite(arr)) else 0.0
    if not np.isfinite(scale) or scale <= 0:
        return np.zeros_like(arr)
    return arr / scale


def center_crop(arr: Any, shape: Sequence[int]) -> np.ndarray:
    data = np.asarray(arr)
    target_y, target_x = int(shape[0]), int(shape[1])
    y0 = max(0, (data.shape[0] - target_y) // 2)
    x0 = max(0, (data.shape[1] - target_x) // 2)
    return data[y0 : y0 + target_y, x0 : x0 + target_x]


def matched_pair(a: Any, b: Any) -> tuple[np.ndarray, np.ndarray]:
    arr_a = np.asarray(a, dtype=float)
    arr_b = np.asarray(b, dtype=float)
    if arr_a.ndim != 2 or arr_b.ndim != 2:
        raise ValueError("matched_pair expects 2D maps")
    target = (min(arr_a.shape[0], arr_b.shape[0]), min(arr_a.shape[1], arr_b.shape[1]))
    if target[0] <= 0 or target[1] <= 0:
        raise ValueError("matched maps have empty overlap")
    return center_crop(arr_a, target), center_crop(arr_b, target)


def apply_presymmetry(data: Any, code: str = "none") -> np.ndarray:
    arr = np.asarray(data, dtype=float)
    code = str(code or "none")
    if code == "mirror_x":
        return 0.5 * (arr + np.flip(arr, axis=1))
    if code == "mirror_y":
        return 0.5 * (arr + np.flip(arr, axis=0))
    if code == "mirror_xy":
        return 0.25 * (arr + np.flip(arr, axis=1) + np.flip(arr, axis=0) + np.flip(np.flip(arr, axis=0), axis=1))
    if code == "c2":
        return 0.5 * (arr + np.rot90(arr, 2))
    return arr


def bragg_normalization_value(reference: Any) -> float:
    arr = np.asarray(reference, dtype=float)
    if arr.ndim != 2 or arr.size <= 0:
        return 1.0
    mag = np.abs(arr)
    finite_mask = np.isfinite(mag)
    if not np.any(finite_mask):
        return 1.0
    mag = np.nan_to_num(mag, nan=0.0, posinf=0.0, neginf=0.0)
    ny, nx = mag.shape
    yy, xx = np.indices((ny, nx), dtype=float)
    cy = 0.5 * float(ny - 1)
    cx = 0.5 * float(nx - 1)
    rr = np.hypot(yy - cy, xx - cx)
    max_r = max(float(np.nanmax(rr)), 1.0)
    min_r = max(3.0, 0.12 * max_r)
    mask = finite_mask & (rr >= min_r) & (rr <= 0.95 * max_r)
    peak_vals = np.asarray([], dtype=float)
    if ny >= 3 and nx >= 3:
        center = mag[1:-1, 1:-1]
        local_max = np.ones_like(center, dtype=bool)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                local_max &= center > mag[1 + dy : ny - 1 + dy, 1 + dx : nx - 1 + dx]
        peak_vals = center[mask[1:-1, 1:-1] & local_max]
    if peak_vals.size > 0:
        top_n = min(8, int(peak_vals.size))
        top = np.partition(peak_vals, peak_vals.size - top_n)[-top_n:]
        value = float(np.nanmedian(top))
    else:
        vals = mag[mask]
        if vals.size <= 0:
            vals = mag[finite_mask]
        value = float(np.nanpercentile(vals, 99.5)) if vals.size > 0 else 1.0
    return value if np.isfinite(value) and value > 0 else 1.0


def build_qpi_input_map(data: Any, *, domain: str = "direct", background_mode: str = "Raw", window_name: str = "Hanning", presymmetry: str = "none") -> np.ndarray:
    arr = background_2d(finite_or_zero(data), background_mode)
    if str(domain).lower().startswith("fft"):
        arr = np.abs(build_windowed_fft_complex(arr, window_name=window_name))
    return finite_or_zero(apply_presymmetry(arr, presymmetry))


def build_qpi_r90_contrast(data: Any, *, operation: str = "diff", rotation: str = "ccw") -> dict[str, Any]:
    input_map = np.asarray(data, dtype=float)
    rotated = np.rot90(input_map, k=-1 if str(rotation).lower().startswith("clock") else 1)
    a, b = matched_pair(input_map, rotated)
    diff = a - b
    summ = a + b
    op = str(operation or "diff")
    if op == "sym":
        result = 0.5 * summ
        norm = 1.0
    else:
        norm = bragg_normalization_value(a)
        result = diff / max(float(norm), 1e-12)
    return {
        "result": finite_or_zero(result),
        "input_map": a,
        "rotated_map": b,
        "bragg_norm": float(norm),
        "algorithm": spstm_algorithm("analystm.spstm.build_qpi_r90_contrast", QPI_SOURCE_MAPPING),
        "parameters": {"operation": op, "rotation": str(rotation)},
        "summary": {"shape": [int(v) for v in result.shape]},
    }


def build_qpi_spin_contrast(pos_map: Any, neg_map: Any) -> dict[str, Any]:
    a, b = matched_pair(pos_map, neg_map)
    contrast = a - b
    average = a + b
    return {
        "contrast": finite_or_zero(contrast),
        "average": finite_or_zero(average),
        "matched_pos": a,
        "matched_neg": b,
        "algorithm": spstm_algorithm("analystm.spstm.build_qpi_spin_contrast", QPI_SOURCE_MAPPING),
        "parameters": {},
        "summary": {"shape": [int(v) for v in contrast.shape]},
    }
