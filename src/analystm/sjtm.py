from __future__ import annotations

from typing import Any, Sequence
import warnings

import numpy as np
from scipy.optimize import OptimizeWarning, curve_fit


def gaussian_model(x: np.ndarray | float, amp: float, center: float, sigma: float, offset: float):
    return amp * np.exp(-0.5 * ((np.asarray(x, dtype=float) - center) / sigma) ** 2) + offset


def _as_yxb_cube(cube: Any, bias_size: int) -> np.ndarray:
    arr = np.asarray(cube, dtype=float)
    if arr.ndim != 3:
        raise ValueError("SJTM input must be a 3D spectral cube")
    if arr.shape[-1] == bias_size:
        return np.ascontiguousarray(arr, dtype=float)
    if arr.shape[0] == bias_size:
        return np.ascontiguousarray(np.moveaxis(arr, 0, -1), dtype=float)
    raise ValueError("could not identify the bias axis in the SJTM cube")


def _fit_ic_branch(
    v: np.ndarray,
    y: np.ndarray,
    *,
    branch: str,
    window: tuple[float, float],
    min_points: int,
    maxfev: int,
) -> tuple[float, np.ndarray]:
    lo, hi = sorted([float(window[0]), float(window[1])])
    mask = (v >= lo) & (v <= hi) & np.isfinite(v) & np.isfinite(y)
    if np.count_nonzero(mask) < int(min_points):
        return np.nan, np.full(4, np.nan, dtype=float)
    xv = np.asarray(v[mask], dtype=float)
    yy = np.asarray(y[mask], dtype=float)
    if branch == "neg":
        idx = int(np.argmin(yy))
        c0 = float(np.nanmedian(yy))
        span = float(np.nanmax(yy) - np.nanmin(yy))
        amp = float(yy[idx] - c0)
        if (not np.isfinite(amp)) or amp >= 0:
            amp = -max(span * 0.5, 1.0)
        lower = [-np.inf, lo, max((hi - lo) / 1e4, 1e-12), -np.inf]
        upper = [0.0, hi, max(hi - lo, 1e-9), np.inf]
        fallback = float(np.nanmin(yy))
    else:
        idx = int(np.argmax(yy))
        c0 = float(np.nanmedian(yy))
        span = float(np.nanmax(yy) - np.nanmin(yy))
        amp = float(yy[idx] - c0)
        if (not np.isfinite(amp)) or amp <= 0:
            amp = max(span * 0.5, 1.0)
        lower = [0.0, lo, max((hi - lo) / 1e4, 1e-12), -np.inf]
        upper = [np.inf, hi, max(hi - lo, 1e-9), np.inf]
        fallback = float(np.nanmax(yy))
    p0 = [amp, float(xv[idx]), max((hi - lo) / 6.0, 1e-12), c0]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", OptimizeWarning)
            popt, _ = curve_fit(gaussian_model, xv, yy, p0=p0, bounds=(lower, upper), maxfev=maxfev)
        value = float(gaussian_model(float(popt[1]), *popt)) * 1e-12
        return value, np.asarray(popt, dtype=float)
    except Exception:
        return fallback * 1e-12, np.full(4, np.nan, dtype=float)


def _ic_algo_config(fit_mode: str = "quick", *, use_parallel: bool = False, workers: int = 1) -> dict[str, Any]:
    text = str(fit_mode or "quick").strip().lower()
    if text == "accurate":
        return {
            "label": "Accurate",
            "maxfev": 4200,
            "retries": 2,
            "center_jitter_frac": 0.06,
            "sigma_jitter_frac": 0.20,
            "amp_jitter_frac": 0.20,
            "progress_div": 100,
            "use_parallel": bool(use_parallel),
            "workers": int(max(1, workers)),
        }
    return {
        "label": "Quick",
        "maxfev": 1200,
        "retries": 0,
        "center_jitter_frac": 0.0,
        "sigma_jitter_frac": 0.0,
        "amp_jitter_frac": 0.0,
        "progress_div": 80,
        "use_parallel": False,
        "workers": 1,
    }


def _compute_ic_row_pysidam(y_neg_row: Any, y_pos_row: Any, fit_cfg: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    v_neg = np.asarray(fit_cfg["v_neg"], dtype=float)
    v_pos = np.asarray(fit_cfg["v_pos"], dtype=float)
    min_pts = int(fit_cfg["min_pts"])
    vneg_min = float(fit_cfg["vneg_min"])
    vneg_max = float(fit_cfg["vneg_max"])
    vpos_min = float(fit_cfg["vpos_min"])
    vpos_max = float(fit_cfg["vpos_max"])
    sigma0_neg = float(fit_cfg["sigma0_neg"])
    sigma0_pos = float(fit_cfg["sigma0_pos"])
    sigma_bounds_neg = fit_cfg["sigma_bounds_neg"]
    sigma_bounds_pos = fit_cfg["sigma_bounds_pos"]
    maxfev = int(fit_cfg["maxfev"])
    retries = int(fit_cfg["retries"])
    center_jitter_neg = float(fit_cfg["center_jitter_neg"])
    center_jitter_pos = float(fit_cfg["center_jitter_pos"])
    sigma_jitter_frac = float(fit_cfg["sigma_jitter_frac"])
    amp_jitter_frac = float(fit_cfg["amp_jitter_frac"])

    y_neg_row = np.asarray(y_neg_row, dtype=float)
    y_pos_row = np.asarray(y_pos_row, dtype=float)
    ny = int(y_neg_row.shape[0])

    row_ic = np.full(ny, np.nan, dtype=float)
    row_fit_neg = np.full((ny, 4), np.nan, dtype=float)
    row_fit_pos = np.full((ny, 4), np.nan, dtype=float)

    last_neg = None
    last_pos = None

    for iy in range(ny):
        y_neg = np.asarray(y_neg_row[iy, :], dtype=float)
        y_pos = np.asarray(y_pos_row[iy, :], dtype=float)

        fin_neg = np.isfinite(y_neg)
        fin_pos = np.isfinite(y_pos)
        if np.count_nonzero(fin_neg) < min_pts or np.count_nonzero(fin_pos) < min_pts:
            continue

        i_dip = np.nan
        i_peak = np.nan

        try:
            y_neg_f = y_neg[fin_neg]
            v_neg_f = v_neg[fin_neg]
            idx_min = int(np.argmin(y_neg_f))
            c0 = float(np.nanmedian(y_neg_f))
            span = float(np.nanmax(y_neg_f) - np.nanmin(y_neg_f))
            a0 = float(y_neg_f[idx_min] - c0)
            if (not np.isfinite(a0)) or a0 >= 0:
                a0 = -max(span * 0.5, 1.0)
            v0_0 = float(v_neg_f[idx_min])
            p0_neg = [a0, v0_0, sigma0_neg, c0]
            if last_neg is not None and np.all(np.isfinite(last_neg)):
                p0_neg = list(last_neg)
                p0_neg[1] = float(np.clip(p0_neg[1], vneg_min, vneg_max))
                p0_neg[2] = float(np.clip(abs(p0_neg[2]), sigma_bounds_neg[0], sigma_bounds_neg[1]))
                p0_neg[0] = float(min(p0_neg[0], -1e-12))
            bounds_lower = [-np.inf, vneg_min, sigma_bounds_neg[0], -np.inf]
            bounds_upper = [0.0, vneg_max, sigma_bounds_neg[1], np.inf]
            best_neg = None
            best_neg_err = np.inf
            for attempt in range(max(1, retries + 1)):
                p0_try = list(p0_neg)
                if attempt > 0:
                    if center_jitter_neg > 0:
                        p0_try[1] = float(np.clip(p0_try[1] + np.random.uniform(-center_jitter_neg, center_jitter_neg), vneg_min, vneg_max))
                    if sigma_jitter_frac > 0:
                        p0_try[2] = float(
                            np.clip(
                                abs(p0_try[2]) * (1.0 + np.random.uniform(-sigma_jitter_frac, sigma_jitter_frac)),
                                sigma_bounds_neg[0],
                                sigma_bounds_neg[1],
                            )
                        )
                    if amp_jitter_frac > 0:
                        p0_try[0] = float(p0_try[0] * (1.0 + np.random.uniform(-amp_jitter_frac, amp_jitter_frac)))
                        p0_try[0] = min(p0_try[0], -1e-12)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", OptimizeWarning)
                    popt_try, _ = curve_fit(gaussian_model, v_neg_f, y_neg_f, p0=p0_try, bounds=(bounds_lower, bounds_upper), maxfev=maxfev)
                pred = gaussian_model(v_neg_f, *popt_try)
                err = float(np.nanmean((pred - y_neg_f) ** 2))
                if np.isfinite(err) and err < best_neg_err:
                    best_neg_err = err
                    best_neg = popt_try
            if best_neg is not None:
                row_fit_neg[iy] = best_neg
                last_neg = best_neg
                i_dip = gaussian_model(best_neg[1], *best_neg) * 1e-12
        except Exception:
            try:
                i_dip = float(np.nanmin(y_neg)) * 1e-12
            except Exception:
                pass

        try:
            y_pos_f = y_pos[fin_pos]
            v_pos_f = v_pos[fin_pos]
            idx_max = int(np.argmax(y_pos_f))
            c0p = float(np.nanmedian(y_pos_f))
            spanp = float(np.nanmax(y_pos_f) - np.nanmin(y_pos_f))
            a0p = float(y_pos_f[idx_max] - c0p)
            if (not np.isfinite(a0p)) or a0p <= 0:
                a0p = max(spanp * 0.5, 1.0)
            v0p_0 = float(v_pos_f[idx_max])
            p0_pos = [a0p, v0p_0, sigma0_pos, c0p]
            if last_pos is not None and np.all(np.isfinite(last_pos)):
                p0_pos = list(last_pos)
                p0_pos[1] = float(np.clip(p0_pos[1], vpos_min, vpos_max))
                p0_pos[2] = float(np.clip(abs(p0_pos[2]), sigma_bounds_pos[0], sigma_bounds_pos[1]))
                p0_pos[0] = float(max(p0_pos[0], 1e-12))
            bounds_lower = [0.0, vpos_min, sigma_bounds_pos[0], -np.inf]
            bounds_upper = [np.inf, vpos_max, sigma_bounds_pos[1], np.inf]
            best_pos = None
            best_pos_err = np.inf
            for attempt in range(max(1, retries + 1)):
                p0_try = list(p0_pos)
                if attempt > 0:
                    if center_jitter_pos > 0:
                        p0_try[1] = float(np.clip(p0_try[1] + np.random.uniform(-center_jitter_pos, center_jitter_pos), vpos_min, vpos_max))
                    if sigma_jitter_frac > 0:
                        p0_try[2] = float(
                            np.clip(
                                abs(p0_try[2]) * (1.0 + np.random.uniform(-sigma_jitter_frac, sigma_jitter_frac)),
                                sigma_bounds_pos[0],
                                sigma_bounds_pos[1],
                            )
                        )
                    if amp_jitter_frac > 0:
                        p0_try[0] = float(p0_try[0] * (1.0 + np.random.uniform(-amp_jitter_frac, amp_jitter_frac)))
                        p0_try[0] = max(p0_try[0], 1e-12)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", OptimizeWarning)
                    popt_try, _ = curve_fit(gaussian_model, v_pos_f, y_pos_f, p0=p0_try, bounds=(bounds_lower, bounds_upper), maxfev=maxfev)
                pred = gaussian_model(v_pos_f, *popt_try)
                err = float(np.nanmean((pred - y_pos_f) ** 2))
                if np.isfinite(err) and err < best_pos_err:
                    best_pos_err = err
                    best_pos = popt_try
            if best_pos is not None:
                row_fit_pos[iy] = best_pos
                last_pos = best_pos
                i_peak = gaussian_model(best_pos[1], *best_pos) * 1e-12
        except Exception:
            try:
                i_peak = float(np.nanmax(y_pos)) * 1e-12
            except Exception:
                pass

        if np.isfinite(i_dip) and np.isfinite(i_peak):
            row_ic[iy] = (abs(i_dip) + abs(i_peak)) / 2.0

    return row_ic, row_fit_neg, row_fit_pos


def compute_ic_map(
    bias: Sequence[float],
    current_cube: Any,
    *,
    neg_window: tuple[float, float],
    pos_window: tuple[float, float],
    min_points: int = 5,
    maxfev: int = 2000,
    fit_mode: str = "quick",
    random_seed: int | None = None,
) -> dict[str, Any]:
    bias_mV = np.asarray(bias, dtype=float).ravel()
    cube = _as_yxb_cube(current_cube, bias_mV.size)
    nx, ny, _ = cube.shape
    if random_seed is not None:
        np.random.seed(int(random_seed))

    vneg_min, vneg_max = sorted([float(neg_window[0]), float(neg_window[1])])
    vpos_min, vpos_max = sorted([float(pos_window[0]), float(pos_window[1])])
    min_pts = int(min_points)
    neg_mask = (bias_mV >= vneg_min) & (bias_mV <= vneg_max)
    pos_mask = (bias_mV >= vpos_min) & (bias_mV <= vpos_max)
    if int(np.count_nonzero(neg_mask)) < min_pts or int(np.count_nonzero(pos_mask)) < min_pts:
        raise ValueError("SJTM Ic fitting window has too few points")

    algo_cfg = _ic_algo_config(fit_mode)
    if maxfev != 2000:
        algo_cfg = dict(algo_cfg)
        algo_cfg["maxfev"] = int(maxfev)

    v_neg = bias_mV[neg_mask]
    v_pos = bias_mV[pos_mask]
    y_neg_cube = cube[:, :, neg_mask] * 1e12
    y_pos_cube = cube[:, :, pos_mask] * 1e12

    window_w_neg = max(float(vneg_max - vneg_min), 1e-9)
    window_w_pos = max(float(vpos_max - vpos_min), 1e-9)
    fit_cfg = {
        "v_neg": v_neg,
        "v_pos": v_pos,
        "min_pts": min_pts,
        "vneg_min": vneg_min,
        "vneg_max": vneg_max,
        "vpos_min": vpos_min,
        "vpos_max": vpos_max,
        "sigma0_neg": max(window_w_neg / 6.0, 1.0),
        "sigma0_pos": max(window_w_pos / 6.0, 1.0),
        "sigma_bounds_neg": (1e-9, max(window_w_neg * 5.0, 1.0)),
        "sigma_bounds_pos": (1e-9, max(window_w_pos * 5.0, 1.0)),
        "maxfev": int(algo_cfg["maxfev"]),
        "retries": int(algo_cfg["retries"]),
        "center_jitter_neg": float(algo_cfg["center_jitter_frac"]) * window_w_neg,
        "center_jitter_pos": float(algo_cfg["center_jitter_frac"]) * window_w_pos,
        "sigma_jitter_frac": float(algo_cfg["sigma_jitter_frac"]),
        "amp_jitter_frac": float(algo_cfg["amp_jitter_frac"]),
    }

    ic_map = np.full((nx, ny), np.nan, dtype=float)
    fit_neg = np.full((nx, ny, 4), np.nan, dtype=float)
    fit_pos = np.full((nx, ny, 4), np.nan, dtype=float)
    for ix in range(nx):
        row_ic, row_fit_neg, row_fit_pos = _compute_ic_row_pysidam(y_neg_cube[ix], y_pos_cube[ix], fit_cfg)
        ic_map[ix, :] = row_ic
        fit_neg[ix, :, :] = row_fit_neg
        fit_pos[ix, :, :] = row_fit_pos

    return {
        "ic_map": ic_map,
        "fit_params_neg": fit_neg,
        "fit_params_pos": fit_pos,
        "summary": {
            "valid_count": int(np.count_nonzero(np.isfinite(ic_map))),
            "failed_count": int(ic_map.size - np.count_nonzero(np.isfinite(ic_map))),
            "ic_mean_A": float(np.nanmean(ic_map)) if np.isfinite(ic_map).any() else np.nan,
        },
        "parameters": {
            "neg_window_mV": [float(min(neg_window)), float(max(neg_window))],
            "pos_window_mV": [float(min(pos_window)), float(max(pos_window))],
            "min_points": int(min_points),
            "fit_mode": str(algo_cfg["label"]),
            "maxfev": int(algo_cfg["maxfev"]),
            "retries": int(algo_cfg["retries"]),
            "center_jitter_frac": float(algo_cfg["center_jitter_frac"]),
            "sigma_jitter_frac": float(algo_cfg["sigma_jitter_frac"]),
            "amp_jitter_frac": float(algo_cfg["amp_jitter_frac"]),
            "random_seed": None if random_seed is None else int(random_seed),
        },
    }


def _resolve_g0_mask(bias: np.ndarray, window: tuple[float, float], min_points: int, *, allow_expand: bool = False) -> tuple[np.ndarray, dict[str, Any]]:
    lo, hi = sorted([float(window[0]), float(window[1])])
    mask = (bias >= lo) & (bias <= hi) & np.isfinite(bias)
    finite_idx = np.flatnonzero(np.isfinite(bias))
    if finite_idx.size == 0:
        raise ValueError("bias axis is invalid")
    zero_idx = int(finite_idx[np.argmin(np.abs(bias[finite_idx]))])
    mask[zero_idx] = True
    if np.count_nonzero(mask) < int(min_points) and not allow_expand:
        raise ValueError(f"G(0) window has {int(np.count_nonzero(mask))} point(s), need >= {int(min_points)}")
    expanded = False
    if np.count_nonzero(mask) < int(min_points):
        expanded = True
        order = finite_idx[np.argsort(np.abs(bias[finite_idx]))]
        for idx in order:
            mask[int(idx)] = True
            if np.count_nonzero(mask) >= int(min_points):
                break
    if np.count_nonzero(mask) < int(min_points):
        raise ValueError("G(0) window has too few points")
    return mask, {
        "requested_min_mV": lo,
        "requested_max_mV": hi,
        "effective_min_mV": float(np.nanmin(bias[mask])),
        "effective_max_mV": float(np.nanmax(bias[mask])),
        "points": int(np.count_nonzero(mask)),
        "expanded": bool(expanded),
    }


def _fit_gaussian_segment(x_seg: Sequence[float], y_seg: Sequence[float]) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
    x = np.asarray(x_seg, dtype=float).ravel()
    y = np.asarray(y_seg, dtype=float).ravel()
    finite = np.isfinite(x) & np.isfinite(y)
    if np.count_nonzero(finite) < 3:
        return None, None, None
    x = x[finite]
    y = y[finite]
    order = np.argsort(x)
    x_fit = x[order]
    y_fit = y[order]
    width = float(x_fit[-1] - x_fit[0])
    if width <= 0:
        return None, None, None
    x0_idx = int(np.argmin(np.abs(x_fit)))
    c0 = float(np.nanmedian(y_fit))
    amp0 = float(y_fit[x0_idx] - c0)
    if not np.isfinite(amp0) or abs(amp0) < 1e-15:
        span = float(np.nanmax(y_fit) - np.nanmin(y_fit))
        amp0 = span * 0.5 if np.isfinite(span) and span > 0 else 1.0
    unique = np.unique(x_fit)
    if unique.size >= 2:
        dx = np.diff(unique)
        dx = dx[(dx > 0) & np.isfinite(dx)]
        dx_min = float(np.min(dx)) if dx.size else width / 20.0
    else:
        dx_min = width / 20.0
    sigma_min = max(dx_min * 0.5, 1e-12)
    sigma0 = max(width / 6.0, sigma_min)
    sigma_max = max(width * 2.0, sigma_min * 2.0)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", OptimizeWarning)
            params, _ = curve_fit(
                gaussian_model,
                x_fit,
                y_fit,
                p0=[amp0, float(x_fit[x0_idx]), sigma0, c0],
                bounds=([-np.inf, float(x_fit[0]), sigma_min, -np.inf], [np.inf, float(x_fit[-1]), sigma_max, np.inf]),
                maxfev=10000,
            )
        return x_fit, gaussian_model(x_fit, *params), np.asarray(params, dtype=float)
    except Exception:
        return None, None, None


def compute_superfluid_metrics(
    bias: Sequence[float],
    rn_cube: Any,
    g0_cube: Any,
    *,
    rn_points: int = 5,
    rn_window: tuple[float, float] | None = None,
    g0_window: tuple[float, float] = (-0.15, 0.15),
    g0_min_points: int = 3,
    g0_allow_expand: bool = False,
) -> dict[str, Any]:
    bias_mV = np.asarray(bias, dtype=float).ravel()
    c1 = _as_yxb_cube(rn_cube, bias_mV.size)
    c2 = _as_yxb_cube(g0_cube, bias_mV.size)
    if c1.shape[:2] != c2.shape[:2]:
        raise ValueError("Rn and G(0) cubes must have matching map shape")

    if rn_window is None:
        rn_mask = np.zeros(bias_mV.size, dtype=bool)
        rn_mask[: min(int(rn_points), bias_mV.size)] = True
    else:
        lo, hi = sorted([float(rn_window[0]), float(rn_window[1])])
        rn_mask = (bias_mV >= lo) & (bias_mV <= hi) & np.isfinite(bias_mV)
    if np.count_nonzero(rn_mask) < 3:
        raise ValueError("Rn fitting window has fewer than 3 points")
    x_fit = bias_mV[rn_mask]
    y_block = np.asarray(c1[:, :, rn_mask], dtype=float)
    n = int(x_fit.size)
    sum_x = float(np.sum(x_fit))
    sum_x2 = float(np.sum(x_fit**2))
    sum_y = np.sum(y_block, axis=2)
    sum_xy = np.sum(y_block * x_fit.reshape(1, 1, -1), axis=2)
    denom = n * sum_x2 - sum_x**2
    if abs(denom) < 1e-12:
        denom = 1e-12
    slope_map = (n * sum_xy - sum_x * sum_y) / denom
    with np.errstate(divide="ignore", invalid="ignore"):
        rn_map = np.where(np.abs(slope_map) > 1e-12, 1.0 / slope_map, np.nan)

    g0_mask, g0_info = _resolve_g0_mask(bias_mV, g0_window, min_points=g0_min_points, allow_expand=g0_allow_expand)
    x_seg = bias_mV[g0_mask]
    g0_block = np.asarray(c2[:, :, g0_mask], dtype=float) * 1e12
    zero_local = int(np.argmin(np.abs(x_seg)))
    h, w = c2.shape[:2]
    g0_map = np.full((h, w), np.nan, dtype=float)
    g0_params = np.full((h, w, 4), np.nan, dtype=float)
    for y in range(h):
        for x in range(w):
            seg = g0_block[y, x, :]
            if not np.all(np.isfinite(seg)):
                continue
            _fx, _fy, params = _fit_gaussian_segment(x_seg, seg)
            if params is not None:
                g0_params[y, x, :] = params
                g0_map[y, x] = float(gaussian_model(0.0, *params)) / 1e12
            else:
                g0_map[y, x] = float(seg[zero_local]) / 1e12

    rn_safe = np.nan_to_num(rn_map)
    g0_safe = np.nan_to_num(g0_map)
    ns_map = g0_safe * (rn_safe**2)
    return {
        "rn_map": rn_map,
        "g0_map": g0_map,
        "ns_map": ns_map,
        "slope_map": slope_map,
        "g0_fit_params": g0_params,
        "summary": {
            "valid_rn_count": int(np.count_nonzero(np.isfinite(rn_map))),
            "valid_g0_count": int(np.count_nonzero(np.isfinite(g0_map))),
            "valid_ns_count": int(np.count_nonzero(np.isfinite(ns_map))),
        },
        "parameters": {
            "rn_window_mV": [float(np.nanmin(x_fit)), float(np.nanmax(x_fit))],
            "rn_points": int(n),
            "g0_window": g0_info,
            "g0_allow_expand": bool(g0_allow_expand),
        },
    }


def compute_sjtm_package(
    bias: Sequence[float],
    current_cube: Any,
    *,
    neg_window: tuple[float, float],
    pos_window: tuple[float, float],
    rn_cube: Any | None = None,
    g0_cube: Any | None = None,
    rn_window: tuple[float, float] | None = None,
    g0_window: tuple[float, float] = (-0.15, 0.15),
    min_points: int = 5,
    ic_fit_mode: str = "quick",
    random_seed: int | None = None,
) -> dict[str, Any]:
    current = current_cube
    rn_source = current if rn_cube is None else rn_cube
    g0_source = current if g0_cube is None else g0_cube
    ic = compute_ic_map(
        bias,
        current,
        neg_window=neg_window,
        pos_window=pos_window,
        min_points=min_points,
        fit_mode=ic_fit_mode,
        random_seed=random_seed,
    )
    sf = compute_superfluid_metrics(bias, rn_source, g0_source, rn_window=rn_window, g0_window=g0_window, rn_points=min_points)
    ic_parameters = dict(ic.get("parameters", {}))
    sf_parameters = dict(sf.get("parameters", {}))
    ic_summary = dict(ic.get("summary", {}))
    sf_summary = dict(sf.get("summary", {}))
    return {
        "ic_map": ic["ic_map"],
        "fit_params_neg": ic["fit_params_neg"],
        "fit_params_pos": ic["fit_params_pos"],
        "rn_map": sf["rn_map"],
        "g0_map": sf["g0_map"],
        "ns_map": sf["ns_map"],
        "slope_map": sf["slope_map"],
        "g0_fit_params": sf["g0_fit_params"],
        "valid_count": ic_summary.get("valid_count", 0),
        "failed_count": ic_summary.get("failed_count", 0),
        "summary": {**sf_summary, "ic": ic_summary, "superfluid": sf_summary},
        "parameters": {"ic": ic_parameters, "superfluid": sf_parameters},
        "algorithm": {
            "name": "AnalySTM SJTM Ic and superfluid metrics",
            "engine": "analystm.sjtm.compute_sjtm_package",
            "ic_pysidam_source_mapping": "SJTMIcExtractionWindow._compute_ic_row and SJTMIcExtractionWindow._compute_ic_map",
            "superfluid_pysidam_source_mapping": "SJTMSuperfluidDensityWindow._compute_metrics, _resolve_g0_window_mask, _fit_gaussian_segment",
            "ic_pysidam_mapping": "SJTMIcExtractionWindow._compute_ic_row and SJTMIcExtractionWindow._compute_ic_map",
            "superfluid_pysidam_mapping": "SJTMSuperfluidDensityWindow._compute_metrics, _resolve_g0_window_mask, _fit_gaussian_segment",
        },
    }
