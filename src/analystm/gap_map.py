from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from scipy import ndimage, signal
from scipy.interpolate import interp1d
from scipy.optimize import curve_fit


def gaussian_peak(x: np.ndarray, amp: float, cen: float, wid: float, bg: float) -> np.ndarray:
    return bg + amp * np.exp(-((x - cen) ** 2) / (2.0 * wid**2))


def fit_single_peak(
    bias: Sequence[float],
    spectrum: Sequence[float],
    search_range: tuple[float, float] | Sequence[float],
    *,
    interp_factor: int = 5,
    interp_kind: str = "cubic",
    smooth_param: float = 0.0,
    smooth_method: str = "Gaussian",
) -> float:
    min_b, max_b = sorted([float(search_range[0]), float(search_range[1])])
    if spectrum is None:
        return float("nan")
    spectrum_arr = np.asarray(spectrum, dtype=float).ravel()
    bias_arr = np.asarray(bias, dtype=float).ravel()
    if spectrum_arr.size != bias_arr.size:
        raise ValueError("bias and spectrum must have the same length")

    mask = (bias_arr >= min_b) & (bias_arr <= max_b)
    if np.count_nonzero(mask) < 3:
        return float("nan")

    b_region = bias_arr[mask]
    s_region = spectrum_arr[mask]
    finite = np.isfinite(b_region) & np.isfinite(s_region)
    if np.count_nonzero(finite) < 3:
        return float("nan")
    b_region = b_region[finite]
    s_region = s_region[finite]
    order = np.argsort(b_region)
    b_region = b_region[order]
    s_region = s_region[order]

    smooth = float(max(0.0, smooth_param))
    if smooth > 0:
        try:
            method = str(smooth_method or "Gaussian")
            if "Gaussian" in method:
                s_region = ndimage.gaussian_filter1d(s_region, smooth)
            elif "Boxcar" in method:
                s_region = ndimage.uniform_filter1d(s_region, size=int(max(1, smooth)))
            elif "Savitzky" in method:
                width = int(smooth)
                width = width + 1 if width % 2 == 0 else width
                width = max(3, width)
                if width <= s_region.size:
                    s_region = signal.savgol_filter(s_region, width, 2 if width > 2 else 1)
        except Exception:
            pass

    interp_factor = int(max(1, interp_factor))
    if interp_factor <= 1 or b_region.size < 4:
        b_interp = b_region
        s_interp = s_region
    else:
        kind = str(interp_kind or "cubic")
        if kind == "cubic" and b_region.size < 4:
            kind = "linear"
        interpolator = interp1d(b_region, s_region, kind=kind, bounds_error=False, fill_value="extrapolate")
        b_interp = np.linspace(float(b_region[0]), float(b_region[-1]), int(len(b_region) * interp_factor))
        s_interp = interpolator(b_interp)

    peaks, _ = signal.find_peaks(s_interp, prominence=1e-13, width=1)
    if len(peaks) > 0:
        best_idx = peaks[int(np.argmax(s_interp[peaks]))]
        target_bias = float(b_interp[best_idx])
    else:
        target_bias = float(b_interp[int(np.argmax(s_interp))])

    fit_window = (max_b - min_b) * 0.3
    fit_mask = (b_interp >= target_bias - fit_window) & (b_interp <= target_bias + fit_window)
    if np.count_nonzero(fit_mask) < 5:
        return float(target_bias)

    try:
        p0 = [
            float(np.max(s_interp[fit_mask]) - np.min(s_interp[fit_mask])),
            float(target_bias),
            float((max_b - min_b) * 0.1),
            float(np.min(s_interp[fit_mask])),
        ]
        popt, _ = curve_fit(gaussian_peak, b_interp[fit_mask], s_interp[fit_mask], p0=p0, maxfev=1000)
        center = float(popt[1])
        if min_b <= center <= max_b:
            return center
        return float(target_bias)
    except Exception:
        return float(target_bias)


def _as_yxb_cube(cube: Any, bias_size: int) -> np.ndarray:
    arr = np.asarray(cube, dtype=float)
    if arr.ndim != 3:
        raise ValueError("gap-map cube must be a 3D spectral cube")
    if arr.shape[-1] == bias_size:
        return np.ascontiguousarray(arr, dtype=float)
    if arr.shape[0] == bias_size:
        return np.ascontiguousarray(np.moveaxis(arr, 0, -1), dtype=float)
    raise ValueError("could not identify the bias axis in the gap-map cube")


def extract_gap_map(
    bias: Sequence[float],
    cube: Any,
    *,
    left_range: tuple[float, float],
    right_range: tuple[float, float],
    interp_factor: int = 5,
    interp_kind: str = "cubic",
    smooth_param: float = 0.0,
    smooth_method: str = "Gaussian",
) -> dict[str, Any]:
    bias_arr = np.asarray(bias, dtype=float).ravel()
    cube_yxb = _as_yxb_cube(cube, bias_arr.size)
    h, w, _n_bias = cube_yxb.shape
    left = np.full((h, w), np.nan, dtype=float)
    right = np.full((h, w), np.nan, dtype=float)
    status = np.zeros((h, w), dtype=np.int16)

    for y in range(h):
        for x in range(w):
            spectrum = cube_yxb[y, x, :]
            left_peak = fit_single_peak(
                bias_arr,
                spectrum,
                left_range,
                interp_factor=interp_factor,
                interp_kind=interp_kind,
                smooth_param=smooth_param,
                smooth_method=smooth_method,
            )
            right_peak = fit_single_peak(
                bias_arr,
                spectrum,
                right_range,
                interp_factor=interp_factor,
                interp_kind=interp_kind,
                smooth_param=smooth_param,
                smooth_method=smooth_method,
            )
            left[y, x] = left_peak
            right[y, x] = right_peak
            if not (np.isfinite(left_peak) and np.isfinite(right_peak)):
                status[y, x] = 1

    gap = (right - left) / 2.0
    valid = np.isfinite(gap) & (status == 0)
    status[~valid] = 1
    summary = {
        "shape_yx": [int(h), int(w)],
        "valid_count": int(np.count_nonzero(valid)),
        "failed_count": int(gap.size - np.count_nonzero(valid)),
        "failure_fraction": float(1.0 - np.count_nonzero(valid) / max(gap.size, 1)),
        "gap_mean_mV": float(np.nanmean(gap[valid])) if np.any(valid) else np.nan,
        "gap_median_mV": float(np.nanmedian(gap[valid])) if np.any(valid) else np.nan,
    }
    return {
        "left_peak_mV": left,
        "right_peak_mV": right,
        "gap_map_mV": gap,
        "status_map": status,
        "summary": summary,
        "parameters": {
            "left_range_mV": [float(min(left_range)), float(max(left_range))],
            "right_range_mV": [float(min(right_range)), float(max(right_range))],
            "interp_factor": int(max(1, interp_factor)),
            "interp_kind": str(interp_kind or "cubic"),
            "smooth_param": float(max(0.0, smooth_param)),
            "smooth_method": str(smooth_method or "Gaussian"),
        },
        "algorithm": {
            "name": "AnalySTM gap-map peak extraction",
            "engine": "analystm.gap_map.extract_gap_map",
            "pysidam_source_mapping": "PeakFitter.fit_single_pixel and batch gap-map extraction",
            "pysidam_mapping": "PeakFitter.fit_single_pixel and batch gap-map extraction",
            "contract": "Fit left and right peak windows per pixel; gap=(right_peak-left_peak)/2.",
        },
    }
