from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from scipy.optimize import least_squares
from scipy.signal import find_peaks

from .gap_models import MODEL_TWO_BAND_S, evaluate_gap_dos_model

PROFILE_TWO_BAND_SPLUSMINUS_GAP_PRIORITY = "two_band_splusminus_gap_priority"


def _robust_scale(y: np.ndarray) -> float:
    q95, q05 = np.nanpercentile(y, [95, 5])
    return float(max(1e-9, (q95 - q05) / 6.0))


def _normalize_xy(bias_mV: Sequence[float], signal: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(bias_mV, dtype=float).ravel()
    y = np.asarray(signal, dtype=float).ravel()
    finite = np.isfinite(x) & np.isfinite(y)
    x = x[finite]
    y = y[finite]
    if x.size < 21:
        raise ValueError("Need at least 21 finite spectroscopy points for gap-priority fitting.")
    order = np.argsort(x)
    x = x[order]
    y = y[order]
    uniq, inv = np.unique(x, return_inverse=True)
    if uniq.size != x.size:
        counts = np.bincount(inv).astype(float)
        sums = np.bincount(inv, weights=y)
        y = sums / np.maximum(counts, 1.0)
        x = uniq
    return np.asarray(x, dtype=float), np.asarray(y, dtype=float)


def symmetrize_trace(bias_mV: Sequence[float], signal: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    x, y = _normalize_xy(bias_mV, signal)
    y_reverse = np.interp(-x, x, y)
    return x, np.asarray(0.5 * (y + y_reverse), dtype=float)


def detect_peak_abs_positions(bias_mV: Sequence[float], signal: Sequence[float]) -> dict[str, Any]:
    x, y = _normalize_xy(bias_mV, signal)
    spread = max(1e-9, float(np.nanpercentile(y, 95) - np.nanpercentile(y, 5)))
    yn = (y - float(np.nanpercentile(y, 5))) / spread
    out: dict[str, Any] = {"negative": [], "positive": [], "abs_selected": []}
    for side_name, side_mask in (("negative", x < 0), ("positive", x > 0)):
        xx = x[side_mask]
        yy = yn[side_mask]
        roi = (np.abs(xx) >= 0.7) & (np.abs(xx) <= 4.8)
        if not np.any(roi):
            continue
        xxr = xx[roi]
        yyr = yy[roi]
        peaks, props = find_peaks(yyr, prominence=0.035, distance=4)
        entries = []
        for idx, prom in zip(peaks, props.get("prominences", [])):
            entries.append(
                {
                    "bias_mV": float(xxr[idx]),
                    "abs_bias_mV": float(abs(xxr[idx])),
                    "height_norm": float(yyr[idx]),
                    "prominence_norm": float(prom),
                }
            )
        entries.sort(key=lambda item: item["prominence_norm"], reverse=True)
        out[side_name] = entries[:4]

    candidates = [item for side in ("negative", "positive") for item in out[side]]
    candidates.sort(key=lambda item: item["prominence_norm"], reverse=True)
    selected: list[float] = []
    for item in candidates:
        value = float(item["abs_bias_mV"])
        if all(abs(value - prev) > 0.42 for prev in selected):
            selected.append(value)
        if len(selected) == 2:
            break
    if len(selected) < 2:
        selected = [1.9, 3.0]
    selected.sort()
    out["abs_selected"] = selected[:2]
    return out


def _candidate_fit_windows(peak_abs: Sequence[float], x: np.ndarray, auto_fit_window: bool, manual: Sequence[float] | None) -> list[float]:
    max_abs = float(np.nanmax(np.abs(x)))
    if manual:
        values = [float(v) for v in manual if np.isfinite(float(v)) and float(v) > 0]
    elif auto_fit_window:
        large = max(float(v) for v in peak_abs) if peak_abs else min(max_abs, 3.0)
        values = [large + 1.45, 4.45, 5.10, 6.0, 7.5, max_abs]
    else:
        values = [min(max_abs, max(4.45, max(float(v) for v in peak_abs) + 1.45))]
    out: list[float] = []
    for value in values:
        clipped = float(np.clip(value, 2.5, max_abs))
        if not any(abs(clipped - prev) < 0.05 for prev in out):
            out.append(clipped)
    return out


def _weight_profile(x: np.ndarray, peak_abs: Sequence[float], fit_abs_mV: float, center_half_width: float) -> tuple[np.ndarray, dict[str, Any]]:
    weights = np.zeros_like(x, dtype=float)
    fit_mask = np.abs(x) <= fit_abs_mV
    weights[fit_mask] = 1.0
    center = np.abs(x) <= center_half_width
    weights[center & fit_mask] = 18.0

    peak_windows = []
    for pos in peak_abs:
        width = 0.34 if float(pos) < 2.5 else 0.42
        region = np.abs(np.abs(x) - float(pos)) <= width
        weights[region & fit_mask] = np.maximum(weights[region & fit_mask], 12.0)
        peak_windows.append([float(max(0.0, float(pos) - width)), float(float(pos) + width)])

    if peak_abs:
        shoulder = (np.abs(x) > center_half_width) & (np.abs(x) < max(float(v) for v in peak_abs) + 0.25)
        weights[shoulder & fit_mask] = np.maximum(weights[shoulder & fit_mask], 2.0)
    return weights, {
        "fit_abs_mV": float(fit_abs_mV),
        "center_half_width_mV": float(center_half_width),
        "peak_abs_mV": [float(v) for v in peak_abs],
        "peak_windows_abs_mV": peak_windows,
        "fit_point_count": int(np.count_nonzero(fit_mask)),
        "excluded_point_count": int(np.count_nonzero(~fit_mask)),
    }


def _model_curve(x: np.ndarray, params: np.ndarray, mode: str) -> np.ndarray:
    if mode == "sym":
        d1, d2, g1, g2, w, scale, offset, quad, bias_offset = params
        linear = 0.0
    else:
        d1, d2, g1, g2, w, scale, offset, linear, quad, bias_offset = params
    energy = np.asarray(x, dtype=float) - float(bias_offset)
    dos = evaluate_gap_dos_model(
        energy,
        MODEL_TWO_BAND_S,
        float(d1),
        float(g1),
        delta2_meV=float(d2),
        gamma2_meV=float(g2),
        weight=float(w),
        theta_count=361,
    )
    xx = np.asarray(x, dtype=float) / 10.0
    background = 1.0 + float(linear) * xx + float(quad) * xx * xx
    return np.asarray(float(offset) + float(scale) * dos * background, dtype=float)


def _bounds_for(mode: str) -> tuple[np.ndarray, np.ndarray, list[str]]:
    common_names = [
        "delta_small_meV",
        "delta_large_meV",
        "gamma_small_meV",
        "gamma_large_meV",
        "small_gap_band_weight",
        "scale",
        "offset",
    ]
    if mode == "sym":
        names = common_names + ["quadratic_background", "bias_offset_mV"]
        lower = np.array([0.45, 1.35, 1e-4, 1e-4, 0.02, 0.01, -8.0, -1.5, -0.28], dtype=float)
        upper = np.array([2.95, 4.8, 0.9, 0.9, 0.98, 40.0, 8.0, 1.5, 0.28], dtype=float)
    else:
        names = common_names + ["linear_background", "quadratic_background", "bias_offset_mV"]
        lower = np.array([0.45, 1.35, 1e-4, 1e-4, 0.02, 0.01, -8.0, -1.2, -1.5, -0.35], dtype=float)
        upper = np.array([2.95, 4.8, 0.9, 0.9, 0.98, 40.0, 8.0, 1.2, 1.5, 0.35], dtype=float)
    return lower, upper, names


def _initial_guesses(x: np.ndarray, y: np.ndarray, mode: str, peak_abs: Sequence[float], random_count: int, seed: int) -> list[np.ndarray]:
    rng = np.random.default_rng(int(seed))
    d_small = float(min(peak_abs)) if peak_abs else 1.9
    d_large = float(max(peak_abs)) if peak_abs else 3.0
    y_span = float(max(0.1, np.nanpercentile(y, 95) - np.nanpercentile(y, 5)))
    y_low = float(np.nanpercentile(y, 5))
    guesses: list[np.ndarray] = []
    base_gap_pairs = [
        (0.88 * d_small, 0.96 * d_large),
        (0.95 * d_small, 1.00 * d_large),
        (1.05 * d_small, 0.92 * d_large),
        (max(0.7, d_small - 0.25), d_large + 0.15),
    ]
    for gamma in (0.05, 0.12, 0.25):
        for gap1, gap2 in base_gap_pairs:
            if mode == "sym":
                guesses.append(np.array([gap1, gap2, gamma, gamma * 1.2, 0.5, y_span, y_low, 0.0, 0.0], dtype=float))
            else:
                guesses.append(np.array([gap1, gap2, gamma, gamma * 1.2, 0.5, y_span, y_low, 0.0, 0.0, 0.0], dtype=float))

    for _ in range(int(max(0, random_count))):
        gap1 = rng.uniform(max(0.65, d_small - 0.55), min(2.85, d_small + 0.45))
        gap2 = rng.uniform(max(gap1 + 0.25, d_large - 0.65), min(4.5, d_large + 0.75))
        gamma1 = 10 ** rng.uniform(np.log10(0.012), np.log10(0.55))
        gamma2 = 10 ** rng.uniform(np.log10(0.012), np.log10(0.65))
        weight = rng.uniform(0.15, 0.85)
        scale = y_span * rng.uniform(0.55, 1.6)
        offset = y_low + rng.normal(0.0, 0.35 * _robust_scale(y))
        quad = rng.uniform(-0.7, 0.5)
        bias_offset = rng.uniform(-0.18, 0.18)
        if mode == "sym":
            guesses.append(np.array([gap1, gap2, gamma1, gamma2, weight, scale, offset, quad, bias_offset], dtype=float))
        else:
            linear = rng.uniform(-0.55, 0.55)
            guesses.append(np.array([gap1, gap2, gamma1, gamma2, weight, scale, offset, linear, quad, bias_offset], dtype=float))
    return guesses


def _fit_window_candidate(
    x: np.ndarray,
    y: np.ndarray,
    mode: str,
    fit_abs_mV: float,
    peak_abs: Sequence[float],
    random_count: int,
    seed: int,
    max_nfev: int,
) -> dict[str, Any]:
    fit_mask = np.isfinite(x) & np.isfinite(y) & (np.abs(x) <= float(fit_abs_mV))
    if np.count_nonzero(fit_mask) < 40:
        raise ValueError("Not enough points inside candidate fit window.")
    xf = np.asarray(x[fit_mask], dtype=float)
    yf = np.asarray(y[fit_mask], dtype=float)
    center_half_width = float(max(0.55, 0.56 * min(float(v) for v in peak_abs))) if peak_abs else 1.08
    full_weights, weighting = _weight_profile(x, peak_abs, float(fit_abs_mV), center_half_width)
    wf = np.asarray(full_weights[fit_mask], dtype=float)
    y_scale = float(max(1e-9, np.nanpercentile(yf, 95) - np.nanpercentile(yf, 5)))
    lower, upper, names = _bounds_for(mode)

    def residual(params: np.ndarray) -> np.ndarray:
        penalty = []
        if params[0] > params[1]:
            penalty.append(10.0 * (params[0] - params[1]))
        return np.concatenate([((_model_curve(xf, params, mode) - yf) / y_scale) * wf, np.asarray(penalty, dtype=float)])

    best: tuple[float, Any] | None = None
    for idx, start in enumerate(_initial_guesses(xf, yf, mode, peak_abs, random_count, seed + int(1000 * fit_abs_mV))):
        p0 = np.clip(np.asarray(start, dtype=float), lower + 1e-9, upper - 1e-9)
        try:
            result = least_squares(
                residual,
                p0,
                bounds=(lower, upper),
                max_nfev=int(max(100, max_nfev)),
                xtol=1e-11,
                ftol=1e-11,
                gtol=1e-11,
            )
        except Exception:
            continue
        score = float(2.0 * result.cost)
        if best is None or score < best[0]:
            best = (score, result)
    if best is None:
        raise RuntimeError("All starts failed for candidate fit window.")

    result = best[1]
    params = np.asarray(result.x, dtype=float)
    model_full = _model_curve(x, params, mode)
    display_model = np.full_like(x, np.nan, dtype=float)
    display_model[fit_mask] = model_full[fit_mask]
    fit_model = np.asarray(model_full[fit_mask], dtype=float)
    residual_fit = fit_model - yf
    center_mask = np.abs(xf - float(params[-1])) <= center_half_width
    peak_mask = np.zeros_like(xf, dtype=bool)
    for pos in peak_abs:
        width = 0.34 if float(pos) < 2.5 else 0.42
        peak_mask |= np.abs(np.abs(xf) - float(pos)) <= width
    ss_res = float(np.sum(residual_fit**2))
    ss_tot = float(np.sum((yf - float(np.nanmean(yf))) ** 2))
    metrics = {
        "fit_r2": float(1.0 - ss_res / ss_tot) if ss_tot > 0 else np.nan,
        "fit_rmse": float(np.sqrt(np.mean(residual_fit**2))),
        "center_platform_rmse_pA": float(np.sqrt(np.mean(residual_fit[center_mask] ** 2))) if np.any(center_mask) else np.nan,
        "coherence_peak_rmse_pA": float(np.sqrt(np.mean(residual_fit[peak_mask] ** 2))) if np.any(peak_mask) else np.nan,
        "max_abs_residual_center_pA": float(np.nanmax(np.abs(residual_fit[center_mask]))) if np.any(center_mask) else np.nan,
        "max_abs_residual_peak_pA": float(np.nanmax(np.abs(residual_fit[peak_mask]))) if np.any(peak_mask) else np.nan,
    }
    bound_hits = []
    for name, value, lo, hi in zip(names, params, lower, upper):
        hit = abs(float(value) - float(lo)) < 1e-4 or abs(float(value) - float(hi)) < 1e-4
        if hit:
            bound_hits.append({"parameter": name, "value": float(value), "boundary_hit": True})
    weighted_score = float(
        8.0 * metrics["center_platform_rmse_pA"]
        + 4.0 * metrics["coherence_peak_rmse_pA"]
        + 0.25 * metrics["fit_rmse"]
        + 10.0 * len(bound_hits)
    )
    return {
        "fit_status": "converged" if bool(getattr(result, "success", False)) else "not_converged",
        "fit_status_message": str(getattr(result, "message", "")),
        "mode": mode,
        "fit_abs_mV": float(fit_abs_mV),
        "param_order": names,
        "parameters": {name: float(value) for name, value in zip(names, params)},
        "bounds": {name: [float(lo), float(hi)] for name, lo, hi in zip(names, lower, upper)},
        "quality": {
            "bound_hits": bound_hits,
            "boundary_hit_count": int(len(bound_hits)),
            "outer_normal_state_policy": "Points outside fit_abs_mV are plotted but excluded from the objective.",
            "model_contract": "two-band s-wave DOS magnitude; scalar STS does not determine s+- phase sign.",
        },
        "metrics": metrics,
        "weighted_score": weighted_score,
        "weighting": weighting,
        "arrays": {
            "bias_display": np.asarray(x, dtype=float),
            "signal_display": np.asarray(y, dtype=float),
            "model_display": np.asarray(display_model, dtype=float),
            "fit_weight": np.asarray(np.where(fit_mask, full_weights, np.nan), dtype=float),
            "fit_mask": fit_mask.astype(int),
        },
    }


def fit_two_band_splusminus_gap_priority(
    bias_mV: Sequence[float],
    signal: Sequence[float],
    *,
    mode: str = "unsym",
    auto_fit_window: bool = True,
    candidate_fit_abs_mV: Sequence[float] | None = None,
    random_starts: int = 24,
    max_nfev: int = 20000,
    seed: int = 1701,
) -> dict[str, Any]:
    base_x, base_y = _normalize_xy(bias_mV, signal)
    fit_x, fit_y = symmetrize_trace(base_x, base_y) if str(mode).lower() == "sym" else (base_x, base_y)
    mode_name = "sym" if str(mode).lower() == "sym" else "unsym"
    peak_detection = detect_peak_abs_positions(fit_x, fit_y)
    peak_abs = [float(v) for v in peak_detection.get("abs_selected", [1.9, 3.0])][:2]
    candidates = _candidate_fit_windows(peak_abs, fit_x, bool(auto_fit_window), candidate_fit_abs_mV)

    candidate_results = []
    last_error = ""
    for idx, fit_abs in enumerate(candidates):
        try:
            candidate_results.append(
                _fit_window_candidate(
                    fit_x,
                    fit_y,
                    mode_name,
                    fit_abs,
                    peak_abs,
                    int(random_starts),
                    int(seed + idx),
                    int(max_nfev),
                )
            )
        except Exception as exc:
            last_error = str(exc)
            continue
    if not candidate_results:
        raise RuntimeError(f"All candidate fit windows failed: {last_error}")
    best = min(candidate_results, key=lambda item: float(item.get("weighted_score", np.inf)))
    candidate_windows = [
        {
            "fit_abs_mV": float(item["fit_abs_mV"]),
            "fit_status": item["fit_status"],
            "metrics": dict(item["metrics"]),
            "weighted_score": float(item["weighted_score"]),
            "boundary_hit_count": int(item["quality"]["boundary_hit_count"]),
        }
        for item in candidate_results
    ]
    params = dict(best["parameters"])
    delta_values = sorted([float(params["delta_small_meV"]), float(params["delta_large_meV"])])
    out = dict(best)
    out.update(
        {
            "profile": PROFILE_TWO_BAND_SPLUSMINUS_GAP_PRIORITY,
            "model_name": "Two-band s+- DOS magnitude",
            "phase_note": "Scalar STS DOS is insensitive to the relative sign; this profile fits two-band Dynes DOS magnitude.",
            "mode": mode_name,
            "fit_status": best["fit_status"],
            "peak_detection": peak_detection,
            "candidate_fit_abs_mV": [float(v) for v in candidates],
            "candidate_windows": candidate_windows,
            "derived_parameters": {
                "delta_small_meV": float(delta_values[0]),
                "delta_large_meV": float(delta_values[1]),
                "small_gap_band_weight": float(params["small_gap_band_weight"]),
                "large_gap_band_weight": float(1.0 - params["small_gap_band_weight"]),
            },
        }
    )
    return out


def fit_gap_priority_modes(
    bias_mV: Sequence[float],
    signal: Sequence[float],
    *,
    symmetry: str = "none",
    auto_fit_window: bool = True,
    candidate_fit_abs_mV: Sequence[float] | None = None,
    random_starts: int = 24,
    max_nfev: int = 20000,
    seed: int = 1701,
) -> list[dict[str, Any]]:
    requested = str(symmetry or "none").strip().lower()
    if requested in {"both", "all"}:
        modes = ["unsym", "sym"]
    elif requested in {"sym", "symmetric"}:
        modes = ["sym"]
    else:
        modes = ["unsym"]
    return [
        fit_two_band_splusminus_gap_priority(
            bias_mV,
            signal,
            mode=mode,
            auto_fit_window=auto_fit_window,
            candidate_fit_abs_mV=candidate_fit_abs_mV,
            random_starts=random_starts,
            max_nfev=max_nfev,
            seed=seed + idx * 100,
        )
        for idx, mode in enumerate(modes)
    ]
