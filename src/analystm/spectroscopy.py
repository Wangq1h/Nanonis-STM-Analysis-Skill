from __future__ import annotations

from typing import Any

import numpy as np
from scipy import ndimage, signal
from scipy.interpolate import interp1d
from scipy.optimize import curve_fit


SPECTROSCOPY_SOURCE_MAPPING = (
    "spectroscopy_display.SpectroscopyDisplayWindow.auto_detect_offset, run_pipeline, "
    "update_derivative_plot, _build_nanonis_export_payload"
)


def spectroscopy_algorithm(engine: str = "analystm.spectroscopy.process_spectrum") -> dict[str, str]:
    return {
        "name": "AnalySTM spectroscopy display backend",
        "engine": engine,
        "pysidam_source_mapping": SPECTROSCOPY_SOURCE_MAPPING,
    }


def gaussian_func(x: Any, amp: float, cen: float, wid: float, bg: float) -> np.ndarray:
    xx = np.asarray(x, dtype=float)
    return float(bg) + float(amp) * np.exp(-((xx - float(cen)) ** 2) / (2.0 * float(wid) ** 2))


def auto_detect_offset(x: Any, y: Any) -> dict[str, Any]:
    xx = np.asarray(x, dtype=float).ravel()
    yy = np.asarray(y, dtype=float).ravel()
    n = min(xx.size, yy.size)
    if n < 5:
        raise ValueError("auto offset requires at least five points")
    xx = xx[:n]
    yy = yy[:n]
    y_smooth = ndimage.gaussian_filter1d(yy, sigma=2)
    idx_zero = int(np.argmin(np.abs(xx)))
    if idx_zero < 3 or idx_zero > len(xx) - 3:
        raise ValueError("zero point is too close to the spectrum edge")
    left_x = xx[:idx_zero]
    left_y = y_smooth[:idx_zero]
    right_x = xx[idx_zero:]
    right_y = y_smooth[idx_zero:]
    if len(left_x) == 0 or len(right_x) == 0:
        raise ValueError("spectrum must contain both negative and positive bias sides")
    idx_max_l = int(np.argmax(left_y))
    idx_max_r = int(np.argmax(right_y))
    global_idx_l = idx_max_l
    global_idx_r = idx_zero + idx_max_r

    def fit_peak_pos(idx_center: int) -> float:
        n_points = 5
        start = max(0, int(idx_center) - n_points)
        end = min(len(xx), int(idx_center) + n_points + 1)
        x_sub = xx[start:end]
        y_sub = y_smooth[start:end]
        if len(x_sub) < 3:
            return float(xx[idx_center])
        try:
            p0 = [float(np.max(y_sub) - np.min(y_sub)), float(xx[idx_center]), float((x_sub[-1] - x_sub[0]) / 4.0), float(np.min(y_sub))]
            popt, _ = curve_fit(gaussian_func, x_sub, y_sub, p0=p0, maxfev=1000)
            return float(popt[1])
        except Exception:
            return float(xx[idx_center])

    pos_l = fit_peak_pos(global_idx_l)
    pos_r = fit_peak_pos(global_idx_r)
    offset = (pos_l + pos_r) / 2.0
    return {
        "left_peak": float(pos_l),
        "right_peak": float(pos_r),
        "offset": float(offset),
        "algorithm": spectroscopy_algorithm("analystm.spectroscopy.auto_detect_offset"),
    }


def _smooth_spectrum(y: np.ndarray, method: str, param: float) -> np.ndarray:
    if float(param) <= 0:
        return y
    text = str(method or "").strip()
    if "Gaussian" in text:
        return np.asarray(ndimage.gaussian_filter1d(y, float(param)), dtype=float)
    if "Boxcar" in text:
        return np.asarray(ndimage.uniform_filter1d(y, size=int(max(1, param))), dtype=float)
    if "Savitzky" in text:
        w = int(param)
        if w % 2 == 0:
            w += 1
        w = max(3, w)
        try:
            return np.asarray(signal.savgol_filter(y, w, 2 if w > 2 else 1), dtype=float)
        except Exception:
            return y
    return y


def _normalize_spectrum(x: np.ndarray, y: np.ndarray, mode: str, ref_current: Any = None) -> np.ndarray:
    out = np.asarray(y, dtype=float).copy()
    text = str(mode or "").strip()
    try:
        if "Sum" in text:
            denom = np.sum(np.abs(out))
            out /= denom if denom != 0 else 1.0
        elif "Max" in text:
            denom = np.max(np.abs(out))
            out /= denom if denom != 0 else 1.0
        elif "First" in text:
            out /= out[0] if (len(out) > 0 and out[0] != 0) else 1.0
        elif "Last" in text:
            out /= out[-1] if (len(out) > 0 and out[-1] != 0) else 1.0
        elif "Feenstra" in text and ref_current is not None:
            current = np.asarray(ref_current, dtype=float).ravel()[: out.size]
            factor = np.zeros_like(out)
            mask = (np.abs(current) > 1e-15) & (np.abs(x[: current.size]) > 1e-6)
            segment = factor[: current.size]
            segment[mask] = x[: current.size][mask] / current[mask]
            factor[: current.size] = segment
            out = out * factor
    except Exception:
        pass
    return np.asarray(out, dtype=float)


def compute_spectrum_derivative(x: Any, y: Any, *, derivative_order: int = 1, smooth_sigma: float = 0.0) -> np.ndarray:
    xx = np.asarray(x, dtype=float).ravel()
    yy = np.asarray(y, dtype=float).ravel()
    if xx.size < 2 or yy.size != xx.size:
        return np.zeros_like(xx, dtype=float)
    d1 = np.gradient(yy, xx)
    if int(derivative_order) == 2:
        d1 = -np.gradient(d1, xx)
    if float(smooth_sigma) > 0:
        d1 = ndimage.gaussian_filter1d(d1, float(smooth_sigma))
    return np.asarray(d1, dtype=float)


def process_spectrum(
    x: Any,
    y: Any,
    *,
    offset: float = 0.0,
    x_scale: float = 1.0,
    symmetrize: bool = False,
    smooth_method: str = "",
    smooth_param: float = 0.0,
    norm_mode: str = "",
    ref_current: Any = None,
    derivative_order: int = 1,
    derivative_smooth: float = 0.0,
) -> dict[str, Any]:
    xx = np.asarray(x, dtype=float).ravel().copy()
    yy = np.asarray(y, dtype=float).ravel().copy()
    n = min(xx.size, yy.size)
    if n == 0:
        raise ValueError("spectrum is empty")
    xx = xx[:n]
    yy = yy[:n]
    scale = float(x_scale)
    if scale == 0:
        scale = 1.0
    xx = xx / scale
    xx = xx - float(offset)
    if bool(symmetrize):
        try:
            u_x, u_idx = np.unique(xx, return_index=True)
            u_y = yy[u_idx]
            f = interp1d(u_x, u_y, kind="linear", bounds_error=False, fill_value=0.0)
            yy = (yy + f(-xx)) / 2.0
        except Exception:
            pass
    yy = _smooth_spectrum(yy, smooth_method, smooth_param)
    yy = _normalize_spectrum(xx, yy, norm_mode, ref_current=ref_current)
    derivative = compute_spectrum_derivative(xx, yy, derivative_order=derivative_order, smooth_sigma=derivative_smooth)
    return {
        "processed_x": np.asarray(xx, dtype=float),
        "processed_y": np.asarray(yy, dtype=float),
        "derivative_y": derivative,
        "algorithm": spectroscopy_algorithm(),
        "parameters": {
            "offset": float(offset),
            "x_scale": float(scale),
            "symmetrize": bool(symmetrize),
            "smooth_method": str(smooth_method),
            "smooth_param": float(smooth_param),
            "norm_mode": str(norm_mode),
            "derivative_order": int(derivative_order),
            "derivative_smooth": float(derivative_smooth),
        },
        "summary": {
            "points": int(n),
            "processed_min": float(np.nanmin(yy)) if yy.size else np.nan,
            "processed_max": float(np.nanmax(yy)) if yy.size else np.nan,
        },
    }


def derivative_export_column_name(derivative_order: int = 1) -> str:
    return "d2I/dV2 (a.u.)" if int(derivative_order) == 1 else "-d3I/dV3 (a.u.)"


def build_spectroscopy_export_payload(
    processed_x_mV: Any,
    processed_y: Any,
    *,
    derivative_y: Any | None = None,
    derivative_order: int = 1,
    export_kind: str = "spectrum",
    channel_name: str = "Signal",
    header: dict[str, Any] | None = None,
) -> dict[str, Any]:
    x = np.asarray(processed_x_mV, dtype=float).ravel()
    y = np.asarray(processed_y, dtype=float).ravel()
    bias_v = x / 1e3
    if str(export_kind or "spectrum").strip().lower().startswith("der"):
        deriv = np.asarray(derivative_y if derivative_y is not None else np.zeros_like(x), dtype=float).ravel()
        columns = [("Bias calc (V)", bias_v), (derivative_export_column_name(derivative_order), deriv)]
        comments = [f"Exported by PySIDAM dIdV Display (Derivative order={int(derivative_order)})."]
    else:
        channel = str(channel_name or "Signal").strip() or "Signal"
        columns = [("Bias calc (V)", bias_v), (channel, y)]
        comments = [f"Exported by PySIDAM dIdV Display (Spectrum, channel={channel})."]
    return {
        "header": dict(header or {}),
        "columns": columns,
        "comments": comments,
        "algorithm": spectroscopy_algorithm("analystm.spectroscopy.build_spectroscopy_export_payload"),
    }
