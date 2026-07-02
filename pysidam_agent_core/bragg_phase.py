from __future__ import annotations

from typing import Any

import numpy as np


def q_selection_policy(
    user_q: list[float] | tuple[float, float] | None = None,
    user_roi: dict[str, float] | None = None,
    allow_agent_search: bool = False,
) -> dict[str, Any]:
    """Describe the required q-selection path before phase analysis."""
    if user_q is not None:
        return {
            "mode": "user_preapproved_q",
            "message": "Use the user-specified q vector first and record it as user_preapproved.",
        }
    if user_roi is not None:
        return {
            "mode": "user_preferred_roi",
            "message": "Use the user-specified ROI first; only refine peaks inside that ROI before approval.",
        }
    if allow_agent_search:
        return {
            "mode": "agent_proposal_required",
            "message": "Run a bounded quick FFT search and create a q_selection approval proposal before lock-in.",
        }
    return {
        "mode": "ask_user_before_search",
        "message": "Ask whether to use a user-specified q/ROI or let the agent search before starting peak finding.",
    }


def q_axes_cycles_per_nm(shape_yx: tuple[int, int], scan_size_nm_xy: tuple[float, float]) -> tuple[np.ndarray, np.ndarray]:
    """Return fftshifted q axes in cycles/nm for a y,x image."""
    ny, nx = map(int, shape_yx)
    sx_nm, sy_nm = map(float, scan_size_nm_xy)
    if ny <= 0 or nx <= 0:
        raise ValueError("shape_yx must contain positive dimensions")
    if sx_nm <= 0 or sy_nm <= 0:
        raise ValueError("scan_size_nm_xy must contain positive scan sizes")
    qx = np.fft.fftshift(np.fft.fftfreq(nx, d=sx_nm / nx))
    qy = np.fft.fftshift(np.fft.fftfreq(ny, d=sy_nm / ny))
    return qx, qy


def scan_size_nm_xy(header: dict[str, Any], default: float = 100.0) -> tuple[float, float]:
    """Extract scan size from common Nanonis/PySIDAM header fields."""
    for key in ("size_xy", "scan_range"):
        val = header.get(key) if isinstance(header, dict) else None
        if isinstance(val, (list, tuple, np.ndarray)) and len(val) >= 2:
            sx = float(val[0]) * 1e9
            sy = float(val[1]) * 1e9
            if np.isfinite(sx) and np.isfinite(sy) and sx > 0 and sy > 0:
                return sx, sy
    return float(default), float(default)


def selected_sxm_map(signals: dict[str, Any], channel: str, direction: str, header: dict[str, Any]) -> np.ndarray:
    """Select and normalize a 2D SXM direction map through PySIDAM."""
    from pysidam.core.dataset_utils import normalize_sxm_direction_map

    raw = signals[channel]
    if isinstance(raw, dict):
        if direction in raw:
            raw_map = raw[direction]
        elif "forward" in raw:
            raw_map = raw["forward"]
        elif "backward" in raw:
            raw_map = raw["backward"]
        else:
            raw_map = raw[next(iter(raw))]
    else:
        raw_map = raw
    out = normalize_sxm_direction_map(raw_map, direction=direction, header=header)
    arr = np.asarray(out, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"Expected 2D SXM map for {channel}/{direction}, got shape {arr.shape}")
    return arr


def fill_invalid(arr: np.ndarray) -> tuple[np.ndarray, int]:
    data = np.asarray(arr, dtype=float)
    invalid = ~np.isfinite(data)
    count = int(np.count_nonzero(invalid))
    if count == 0:
        return np.array(data, copy=True), 0
    finite = data[np.isfinite(data)]
    fill = float(np.nanmedian(finite)) if finite.size else 0.0
    out = np.array(data, copy=True)
    out[invalid] = fill
    return out, count


def preprocess_topography(z_map: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    """Apply the standard lightweight Bragg/FFT topography preprocessing."""
    data, invalid_count = fill_invalid(z_map)
    ny, nx = data.shape
    yy, xx = np.mgrid[0:ny, 0:nx]
    design = np.c_[xx.ravel(), yy.ravel(), np.ones(nx * ny)]
    coeff, _, _, _ = np.linalg.lstsq(design, data.ravel(), rcond=None)
    plane = coeff[0] * xx + coeff[1] * yy + coeff[2]
    out = data - plane
    out = out - np.nanmedian(out, axis=1, keepdims=True)
    out = out - np.nanmedian(out, axis=0, keepdims=True)
    out = out - float(np.nanmedian(out))
    return np.asarray(out, dtype=float), {
        "invalid_pixels_filled": invalid_count,
        "plane_coeff_x": float(coeff[0]),
        "plane_coeff_y": float(coeff[1]),
        "plane_coeff_const": float(coeff[2]),
        "steps": [
            "fill invalid pixels with finite median only if needed",
            "least-squares plane subtraction",
            "row median subtraction",
            "column median subtraction",
            "global median subtraction",
        ],
    }


def roi_mask(qx_grid: np.ndarray, qy_grid: np.ndarray, roi: dict[str, float], sign: int = 1) -> np.ndarray:
    """Build a plus or minus ROI mask from a plus-q ROI definition."""
    required = ("qx_min", "qx_max", "qy_min", "qy_max")
    missing = [key for key in required if key not in roi]
    if missing:
        raise ValueError(f"ROI is missing keys: {', '.join(missing)}")
    if sign >= 0:
        x0, x1 = float(roi["qx_min"]), float(roi["qx_max"])
        y0, y1 = float(roi["qy_min"]), float(roi["qy_max"])
    else:
        x0, x1 = -float(roi["qx_max"]), -float(roi["qx_min"])
        y0, y1 = -float(roi["qy_max"]), -float(roi["qy_min"])
    return (qx_grid >= x0) & (qx_grid <= x1) & (qy_grid >= y0) & (qy_grid <= y1)


def find_peak_in_roi(
    log_amp: np.ndarray,
    qx_axis: np.ndarray,
    qy_axis: np.ndarray,
    roi: dict[str, float],
    sign: int = 1,
) -> dict[str, Any]:
    """Find the strongest finite FFT point inside a plus or mirrored minus ROI."""
    vals = np.asarray(log_amp, dtype=float)
    qx = np.asarray(qx_axis, dtype=float)
    qy = np.asarray(qy_axis, dtype=float)
    if vals.ndim != 2:
        raise ValueError("log_amp must be 2D")
    if vals.shape != (qy.size, qx.size):
        raise ValueError("log_amp shape must match qy_axis x qx_axis")
    qx_grid, qy_grid = np.meshgrid(qx, qy)
    mask = roi_mask(qx_grid, qy_grid, roi, sign=sign)
    finite_mask = mask & np.isfinite(vals)
    if not np.any(finite_mask):
        raise ValueError("ROI does not contain finite FFT pixels")
    masked = np.where(finite_mask, vals, -np.inf)
    iy, ix = np.unravel_index(int(np.nanargmax(masked)), vals.shape)
    roi_vals = vals[finite_mask]
    roi_median = float(np.nanmedian(roi_vals))
    roi_mad = float(np.nanmedian(np.abs(roi_vals - roi_median)))
    robust_sigma = 1.4826 * roi_mad if roi_mad > 0 else float(np.nanstd(roi_vals))
    qx_val = float(qx[ix])
    qy_val = float(qy[iy])
    peak = float(vals[iy, ix])
    return {
        "pixel_yx": [int(iy), int(ix)],
        "offset_px_yx": [int(iy - vals.shape[0] // 2), int(ix - vals.shape[1] // 2)],
        "q_cycles_per_nm_xy": [qx_val, qy_val],
        "q_abs_cycles_per_nm": float(np.hypot(qx_val, qy_val)),
        "angle_deg": float(np.degrees(np.arctan2(qy_val, qx_val))),
        "log_amp": peak,
        "roi_median_log_amp": roi_median,
        "peak_minus_roi_median": float(peak - roi_median),
        "robust_z_vs_roi": float((peak - roi_median) / robust_sigma) if robust_sigma > 0 else None,
    }


def wrap_pi(phi: np.ndarray) -> np.ndarray:
    return (np.asarray(phi, dtype=float) + np.pi) % (2.0 * np.pi) - np.pi


def amp_mask(amp: np.ndarray, threshold_fraction: float) -> np.ndarray:
    arr = np.asarray(amp, dtype=float)
    finite = np.isfinite(arr)
    if not finite.any():
        return np.zeros(arr.shape, dtype=bool)
    max_val = float(np.nanmax(arr[finite]))
    if not np.isfinite(max_val) or max_val <= 0:
        return np.zeros(arr.shape, dtype=bool)
    return finite & (arr >= float(threshold_fraction) * max_val)
