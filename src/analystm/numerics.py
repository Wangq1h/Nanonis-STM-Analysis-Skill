from __future__ import annotations

import time
from typing import Optional, Sequence

import numpy as np
from scipy.ndimage import gaussian_filter1d


def normalize_xy_arrays(v_bias: Sequence[float], y: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    vv = np.asarray(v_bias, dtype=float).ravel()
    yy = np.asarray(y, dtype=float).ravel()
    mask = np.isfinite(vv) & np.isfinite(yy)
    vv = vv[mask]
    yy = yy[mask]
    if vv.size < 2:
        raise ValueError("Trace has fewer than 2 finite points.")
    order = np.argsort(vv)
    vv = vv[order]
    yy = yy[order]
    uniq, inv = np.unique(vv, return_inverse=True)
    if uniq.size != vv.size:
        counts = np.bincount(inv).astype(float)
        sums = np.bincount(inv, weights=yy)
        yy = sums / np.maximum(counts, 1.0)
        vv = uniq
    return np.asarray(vv, dtype=float), np.asarray(yy, dtype=float)


def ensure_odd_grid_size(n_value: Optional[int], minimum: int = 9) -> int:
    try:
        n_int = int(n_value)
    except Exception:
        n_int = int(minimum)
    n_int = max(int(minimum), n_int)
    if n_int % 2 == 0:
        n_int += 1
    return int(n_int)


def median_bias_step(v_bias: Sequence[float]) -> float:
    vv = np.asarray(v_bias, dtype=float).ravel()
    if vv.size < 2:
        return np.nan
    dv = np.diff(vv)
    dv = dv[np.isfinite(dv) & (np.abs(dv) > 0)]
    if dv.size == 0:
        return np.nan
    return float(np.nanmedian(np.abs(dv)))


def _fit_edge_line(x_edge: np.ndarray, y_edge: np.ndarray) -> tuple[float, float]:
    xx = np.asarray(x_edge, dtype=float).ravel()
    yy = np.asarray(y_edge, dtype=float).ravel()
    if xx.size < 2 or yy.size != xx.size:
        return 0.0, float(yy[0]) if yy.size else 0.0
    if np.nanmax(xx) - np.nanmin(xx) <= 0:
        return 0.0, float(np.nanmean(yy))
    coef = np.polyfit(xx, yy, 1)
    return float(coef[0]), float(coef[1])


def resample_trace(
    v_bias: Sequence[float],
    y: Sequence[float],
    target_bias: Sequence[float],
    *,
    extrapolation: str = "constant",
    edge_points: int = 7,
) -> np.ndarray:
    vv, yy = normalize_xy_arrays(v_bias, y)
    target = np.asarray(target_bias, dtype=float).ravel()
    out = np.interp(target, vv, yy)
    if target.size == 0:
        return out

    mode = str(extrapolation or "constant").strip().lower()
    left_mask = target < float(vv[0])
    right_mask = target > float(vv[-1])
    if mode == "linear":
        n_edge = int(np.clip(int(edge_points), 2, max(2, vv.size)))
        m_left, b_left = _fit_edge_line(vv[:n_edge], yy[:n_edge])
        m_right, b_right = _fit_edge_line(vv[-n_edge:], yy[-n_edge:])
        if np.any(left_mask):
            out[left_mask] = m_left * target[left_mask] + b_left
        if np.any(right_mask):
            out[right_mask] = m_right * target[right_mask] + b_right
    else:
        if np.any(left_mask):
            out[left_mask] = float(yy[0])
        if np.any(right_mask):
            out[right_mask] = float(yy[-1])
    return np.asarray(out, dtype=float)


def gaussian_broaden_uniform_trace(v_bias: Sequence[float], y: Sequence[float], sigma_mV: float) -> np.ndarray:
    vv = np.asarray(v_bias, dtype=float).ravel()
    yy = np.asarray(y, dtype=float).ravel()
    if vv.size < 3 or yy.size != vv.size:
        return np.asarray(yy, dtype=float)
    sigma = float(max(0.0, sigma_mV))
    if sigma <= 0:
        return np.asarray(yy, dtype=float)
    step = median_bias_step(vv)
    if (not np.isfinite(step)) or step <= 0:
        return np.asarray(yy, dtype=float)
    return gaussian_filter1d(np.asarray(yy, dtype=float), sigma=max(sigma / step, 1e-9), mode="nearest")


def estimate_fit_abs_max(v_bias: Sequence[float], rho_sample_norm: Sequence[float]) -> float:
    vv = np.asarray(v_bias, dtype=float).ravel()
    yy = np.asarray(rho_sample_norm, dtype=float).ravel()
    finite = np.isfinite(vv) & np.isfinite(yy)
    vv = vv[finite]
    yy = yy[finite]
    if vv.size < 9:
        return np.nan
    order = np.argsort(vv)
    vv = vv[order]
    yy = yy[order]
    max_abs = float(np.nanmax(np.abs(vv)))
    if (not np.isfinite(max_abs)) or max_abs <= 0:
        return np.nan
    step = median_bias_step(vv)
    if (not np.isfinite(step)) or step <= 0:
        step = max((2.0 * max_abs) / max(vv.size - 1, 1), 1e-3)
    sigma_pts = float(np.clip(0.12 / max(step, 1e-12), 0.75, 4.0))
    yy_s = gaussian_filter1d(np.asarray(yy, dtype=float), sigma=sigma_pts, mode="nearest")
    min_abs = float(max(0.25, 4.0 * step))
    peak_vals: list[float] = []
    pos_mask = vv >= min_abs
    neg_mask = vv <= -min_abs
    if np.count_nonzero(pos_mask) >= 3:
        peak_vals.append(float(vv[pos_mask][int(np.argmax(yy_s[pos_mask]))]))
    if np.count_nonzero(neg_mask) >= 3:
        peak_vals.append(float(abs(vv[neg_mask][int(np.argmax(yy_s[neg_mask]))])))
    peak_abs = float(np.nanmax(np.abs(peak_vals))) if peak_vals else np.nan
    if (not np.isfinite(peak_abs)) or peak_abs <= 0:
        peak_abs = 0.6 * max_abs
    margin = float(max(0.35, 6.0 * step))
    fit_abs = float(max(1.45 * peak_abs, peak_abs + margin))
    fit_abs = float(np.clip(fit_abs, min(max_abs, max(0.6 * max_abs, peak_abs)), max_abs))
    return fit_abs


def solve_affine_reference_scale_offset(
    model_vals: Sequence[float],
    data_vals: Sequence[float],
    weights: Sequence[float] | None = None,
) -> tuple[float, float]:
    mm = np.asarray(model_vals, dtype=float).ravel()
    dd = np.asarray(data_vals, dtype=float).ravel()
    if mm.size == 0 or dd.size != mm.size:
        return 1.0, 0.0
    finite = np.isfinite(mm) & np.isfinite(dd)
    ww = None
    if weights is not None:
        try:
            ww = np.asarray(weights, dtype=float).ravel()
            if ww.size == mm.size:
                finite &= np.isfinite(ww) & (ww > 0)
            else:
                ww = None
        except Exception:
            ww = None
    if np.count_nonzero(finite) < 2:
        return 1.0, 0.0
    x = np.asarray(mm[finite], dtype=float)
    y = np.asarray(dd[finite], dtype=float)
    design = np.column_stack([x, np.ones_like(x, dtype=float)])
    if ww is not None:
        w = np.asarray(ww[finite], dtype=float)
        design = design * w[:, None]
        y = y * w
    try:
        coeffs, *_ = np.linalg.lstsq(design, y, rcond=None)
        scale = float(coeffs[0])
        offset = float(coeffs[1])
    except Exception:
        scale = 1.0
        offset = 0.0
    if not np.isfinite(scale):
        scale = 1.0
    if not np.isfinite(offset):
        offset = 0.0
    return float(scale), float(offset)


def feature_weights(v_bias: Sequence[float], rho_sample_norm: Sequence[float]) -> np.ndarray:
    vv = np.asarray(v_bias, dtype=float).ravel()
    yy = np.asarray(rho_sample_norm, dtype=float).ravel()
    if vv.size != yy.size or vv.size < 9:
        return np.ones_like(yy, dtype=float)
    try:
        step = median_bias_step(vv)
        sigma_pts = float(np.clip(0.12 / max(step, 1e-12), 0.75, 3.0)) if np.isfinite(step) and step > 0 else 1.0
        ys = gaussian_filter1d(np.asarray(yy, dtype=float), sigma=sigma_pts, mode="nearest")
    except Exception:
        ys = np.asarray(yy, dtype=float)
    finite = np.isfinite(vv) & np.isfinite(ys)
    if np.count_nonzero(finite) < 9:
        return np.ones_like(yy, dtype=float)
    y_ref = float(np.nanmedian(ys[finite]))
    feature = np.abs(ys - y_ref)
    feature_scale = float(np.nanpercentile(feature[finite], 95.0))
    if not np.isfinite(feature_scale) or feature_scale <= 1e-12:
        feature_scale = float(np.nanmax(feature[finite])) if np.any(finite) else 1.0
    if not np.isfinite(feature_scale) or feature_scale <= 1e-12:
        feature_scale = 1.0
    weights = 1.0 + 1.7 * np.clip(feature / feature_scale, 0.0, 1.5)
    try:
        slope = np.abs(np.gradient(ys, vv))
        slope_scale = float(np.nanpercentile(slope[finite], 95.0))
        if np.isfinite(slope_scale) and slope_scale > 1e-12:
            weights += 0.7 * np.clip(slope / slope_scale, 0.0, 1.5)
    except Exception:
        pass
    try:
        abs_max = float(np.nanmax(np.abs(vv[finite])))
        step = median_bias_step(vv)
        center_width = max(0.12, 4.0 * step if np.isfinite(step) and step > 0 else 0.0, 0.08 * abs_max)
        if np.isfinite(center_width) and center_width > 0:
            weights += 1.2 * np.exp(-0.5 * (vv / center_width) ** 2)
    except Exception:
        pass
    weights = np.asarray(np.clip(weights, 0.5, 5.0), dtype=float)
    norm = float(np.nanmean(weights[finite]))
    if np.isfinite(norm) and norm > 1e-12:
        weights = weights / norm
    weights[~np.isfinite(weights)] = 1.0
    return np.asarray(weights, dtype=float)


def detect_gap_peak_positions(v_bias: Sequence[float], rho_sample_norm: Sequence[float]) -> list[float]:
    vv = np.asarray(v_bias, dtype=float).ravel()
    yy = np.asarray(rho_sample_norm, dtype=float).ravel()
    finite = np.isfinite(vv) & np.isfinite(yy)
    if np.count_nonzero(finite) < 9:
        return []
    vv = vv[finite]
    yy = yy[finite]
    order = np.argsort(vv)
    vv = vv[order]
    yy = yy[order]
    step = median_bias_step(vv)
    sigma_pts = float(np.clip(0.12 / max(step, 1e-12), 0.75, 3.0)) if np.isfinite(step) and step > 0 else 1.0
    try:
        ys = gaussian_filter1d(yy, sigma=sigma_pts, mode="nearest")
    except Exception:
        ys = yy
    max_abs = float(np.nanmax(np.abs(vv))) if vv.size else 0.0
    min_abs = float(max(0.35, 6.0 * step if np.isfinite(step) and step > 0 else 0.0, 0.06 * max_abs))
    candidates: list[float] = []
    for side in (-1, 1):
        idx = np.where((vv * side) >= min_abs)[0]
        if idx.size < 3:
            continue
        local: list[int] = []
        for i in idx:
            if i <= 0 or i >= ys.size - 1:
                continue
            if ys[i] >= ys[i - 1] and ys[i] >= ys[i + 1]:
                local.append(int(i))
        if not local:
            local = [int(idx[int(np.nanargmax(ys[idx]))])]
        local = sorted(local, key=lambda i: float(ys[i]), reverse=True)[:4]
        candidates.extend(abs(float(vv[i])) for i in local if np.isfinite(vv[i]))
    if not candidates:
        return []
    values = sorted(float(v) for v in candidates if np.isfinite(v) and v > 0)
    merged: list[float] = []
    tol = max(0.12, 3.0 * step if np.isfinite(step) and step > 0 else 0.0)
    for value in values:
        if not merged or abs(value - merged[-1]) > tol:
            merged.append(value)
        else:
            merged[-1] = 0.5 * (merged[-1] + value)
    return merged


def make_time_budget_callback(time_budget_s: Optional[float], fit_label: str = "DOS fit"):
    if time_budget_s is None:
        return None
    try:
        budget = float(time_budget_s)
    except Exception:
        return None
    if (not np.isfinite(budget)) or budget <= 0:
        return None
    deadline = time.perf_counter() + max(0.05, budget)
    message = f"{fit_label} did not converge within {budget:.1f} s."

    def _callback():
        if time.perf_counter() >= deadline:
            return message
        return False

    return _callback


def combine_cancel_callbacks(*callbacks):
    active = [cb for cb in callbacks if cb is not None]
    if not active:
        return None

    def _callback():
        for cb in active:
            try:
                result = cb()
            except RuntimeError:
                raise
            except Exception:
                continue
            if isinstance(result, str) and result.strip():
                return str(result).strip()
            if bool(result):
                return True
        return False

    return _callback


def format_fit_failure_message(exc: Exception) -> str:
    text = str(exc or "").strip()
    lower = text.lower()
    if "did not converge within" in lower:
        return f"{text} The gap-model fit is reported as unavailable."
    if "maximum number of function evaluations" in lower or "maxfev" in lower:
        return "DOS fit did not converge within the current iteration budget."
    if "canceled" in lower:
        return "DOS fit was canceled."
    if not text:
        return "DOS fit failed."
    return f"DOS fit failed: {text}."
