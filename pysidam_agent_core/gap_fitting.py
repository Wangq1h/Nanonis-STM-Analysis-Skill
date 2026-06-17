from __future__ import annotations

from typing import Any, Optional, Sequence

import numpy as np
from scipy.optimize import curve_fit, least_squares

from .models import (
    DEFAULT_DOS_FIT_TIME_BUDGET_S,
    DEFAULT_FESE_DYNES_GAMMA_MEV,
    DEFAULT_PAPER_DOS_BROAD_SIGMA_MV,
    DOS_FIT_STRATEGY_MULTISTART_WEIGHTED,
    DOS_FIT_STRATEGY_PAPER,
    FESE_MODEL_FIT_GRID_MAX,
    FESE_MODEL_THETA_COUNT,
    MODEL_THREE_BAND_S,
    MODEL_TWO_BAND_ANISOTROPIC_FESE,
    MODEL_TWO_BAND_ANISOTROPIC_S,
    MODEL_TWO_BAND_ANISOTROPIC_S_INGAP,
    MODEL_TWO_BAND_S,
    MODEL_TWO_BAND_S_INGAP,
    build_gap_model_summary_params,
    evaluate_gap_model_raw,
    get_deconvolution_fit_param_spec,
    map_deconvolution_fit_values,
    normalize_gap_model_name,
    normalize_three_band_weights,
    order_fese_parameters,
)
from .numerics import (
    combine_cancel_callbacks,
    detect_gap_peak_positions,
    ensure_odd_grid_size,
    estimate_fit_abs_max,
    feature_weights,
    format_fit_failure_message,
    make_time_budget_callback,
    normalize_xy_arrays,
    resample_trace,
    solve_affine_reference_scale_offset,
)


def _as_float(value: Any, default: float = np.nan) -> float:
    try:
        out = float(value)
    except Exception:
        out = float(default)
    return out if np.isfinite(out) else float(default)


def _least_squares_compat(fun, x0, bounds, max_nfev: int):
    return least_squares(
        fun,
        x0=np.asarray(x0, dtype=float),
        bounds=(np.asarray(bounds[0], dtype=float), np.asarray(bounds[1], dtype=float)),
        max_nfev=int(max(1, max_nfev)),
    )


def _gap_fit_initial_guesses(
    model: str,
    specs: Sequence[dict[str, Any]],
    fit_grid: np.ndarray,
    data_fit: np.ndarray,
    gamma_meV: float,
    lower: Sequence[float],
    upper: Sequence[float],
    default_p0: Sequence[float],
) -> list[list[float]]:
    starts = [list(float(v) for v in default_p0)]
    keys = [str(spec.get("key", "")) for spec in specs]
    peaks = detect_gap_peak_positions(fit_grid, data_fit)
    if peaks:
        inner = float(peaks[0])
        outer = float(peaks[-1])
        middle = float(peaks[len(peaks) // 2]) if len(peaks) >= 3 else float(0.5 * (inner + outer))
    else:
        abs_max = float(np.nanmax(np.abs(np.asarray(fit_grid, dtype=float)))) if len(fit_grid) else 4.0
        inner = 0.35 * abs_max
        outer = 0.70 * abs_max
        middle = 0.52 * abs_max
    if outer < inner:
        inner, outer = outer, inner
    middle = float(np.clip(middle, min(inner, outer), max(inner, outer))) if outer > inner else float(inner)
    if outer <= 0:
        outer = 2.0
    if inner <= 0:
        inner = max(0.5, 0.5 * outer)
    p_est = float(np.clip(0.5 * (1.0 - inner / max(outer, 1e-12)), 0.02, 0.45))

    def make(**values):
        vals = list(float(v) for v in default_p0)
        for idx, key in enumerate(keys):
            if key in values:
                vals[idx] = float(values[key])
            elif key == "gamma_meV" or key in ("gamma1_meV", "gamma2_meV", "gamma3_meV"):
                vals[idx] = float(max(0.0, gamma_meV))
        clipped: list[float] = []
        for idx, value in enumerate(vals):
            hi = float(upper[idx])
            lo = float(lower[idx])
            clipped.append(float(np.clip(value, lo + 1e-9, hi - 1e-9 if np.isfinite(hi) else value)))
        return clipped

    if model == MODEL_TWO_BAND_ANISOTROPIC_FESE:
        starts.extend(
            [
                make(delta_hole_meV=outer, delta_electron_meV=inner, p_hole=p_est, p_electron=0.08, hole_weight=0.55),
                make(
                    delta_hole_meV=outer,
                    delta_electron_meV=max(inner, 0.75 * outer),
                    p_hole=p_est,
                    p_electron=max(0.04, 0.65 * p_est),
                    hole_weight=0.50,
                ),
                make(delta_hole_meV=outer, delta_electron_meV=inner, p_hole=0.04, p_electron=0.04, hole_weight=0.50),
                make(
                    delta_hole_meV=max(inner, 0.55 * outer),
                    delta_electron_meV=outer,
                    p_hole=0.06,
                    p_electron=p_est,
                    hole_weight=0.35,
                ),
            ]
        )
    elif model == MODEL_TWO_BAND_ANISOTROPIC_S_INGAP:
        ingap_gamma = float(max(0.01, min(0.12, 0.25 * max(inner, 1e-9))))
        starts.extend(
            [
                make(delta1_meV=outer, delta2_meV=middle, weight=0.50, alpha1=0.10, alpha2=0.10, ingap_energy_meV=inner, ingap_gamma_meV=ingap_gamma, ingap_amp=0.15),
                make(delta1_meV=middle, delta2_meV=outer, weight=0.45, alpha1=0.20, alpha2=0.10, ingap_energy_meV=inner, ingap_gamma_meV=ingap_gamma, ingap_amp=0.15),
                make(delta1_meV=outer, delta2_meV=max(inner, 0.65 * outer), weight=0.65, alpha1=0.25, alpha2=0.15, ingap_energy_meV=inner, ingap_gamma_meV=ingap_gamma, ingap_amp=0.10),
            ]
        )
    elif model == MODEL_TWO_BAND_S_INGAP:
        ingap_gamma = float(max(0.01, min(0.12, 0.25 * max(inner, 1e-9))))
        starts.extend(
            [
                make(delta1_meV=outer, delta2_meV=middle, weight=0.50, ingap_energy_meV=inner, ingap_gamma_meV=ingap_gamma, ingap_amp=0.15),
                make(delta1_meV=middle, delta2_meV=outer, weight=0.45, ingap_energy_meV=inner, ingap_gamma_meV=ingap_gamma, ingap_amp=0.15),
                make(delta1_meV=outer, delta2_meV=max(inner, 0.65 * outer), weight=0.65, ingap_energy_meV=inner, ingap_gamma_meV=ingap_gamma, ingap_amp=0.10),
            ]
        )
    elif model in (MODEL_TWO_BAND_S, MODEL_TWO_BAND_ANISOTROPIC_S):
        starts.extend(
            [
                make(delta1_meV=outer, delta2_meV=inner, weight=0.5, alpha1=0.05, alpha2=0.05),
                make(delta1_meV=inner, delta2_meV=outer, weight=0.5, alpha1=0.05, alpha2=0.05),
                make(delta1_meV=outer, delta2_meV=max(inner, 0.75 * outer), weight=0.65, alpha1=0.20, alpha2=0.10),
            ]
        )
    elif model == MODEL_THREE_BAND_S:
        starts.extend(
            [
                make(delta1_meV=outer, delta2_meV=middle, delta3_meV=inner, weight1=0.40, weight2=0.35),
                make(delta1_meV=inner, delta2_meV=middle, delta3_meV=outer, weight1=0.30, weight2=0.35),
                make(delta1_meV=outer, delta2_meV=max(inner, 0.65 * outer), delta3_meV=max(inner, 0.35 * outer), weight1=0.50, weight2=0.30),
            ]
        )
    elif "delta_meV" in keys:
        starts.append(make(delta_meV=inner))
        starts.append(make(delta_meV=outer))

    unique: list[list[float]] = []
    seen: set[tuple[float, ...]] = set()
    for start in starts:
        key = tuple(round(float(v), 8) for v in start)
        if key in seen:
            continue
        seen.add(key)
        unique.append(start)
    return unique


def fit_gap_model(
    v_bias: Sequence[float],
    rho_sample_norm: Sequence[float],
    *,
    model_name: str = MODEL_TWO_BAND_ANISOTROPIC_FESE,
    gaussian_sigma_mV: float = DEFAULT_PAPER_DOS_BROAD_SIGMA_MV,
    gamma_meV: float = DEFAULT_FESE_DYNES_GAMMA_MEV,
    initial_params: Optional[Sequence[float]] = None,
    fit_grid_max: int = FESE_MODEL_FIT_GRID_MAX,
    theta_count: int = FESE_MODEL_THETA_COUNT,
    fit_abs_max: Optional[float] = None,
    normalization_meta: Optional[dict[str, Any]] = None,
    fit_abs_source_override: Optional[str] = None,
    fit_roi_pct: Optional[float] = None,
    apply_model_gaussian_broadening: bool = False,
    curve_fit_maxfev: int = 20000,
    max_nfev: Optional[int] = None,
    cancel_callback=None,
    fit_strategy: str = DOS_FIT_STRATEGY_MULTISTART_WEIGHTED,
    fit_max_starts: Optional[int] = None,
) -> dict[str, Any]:
    model = normalize_gap_model_name(model_name)
    vv, yy = normalize_xy_arrays(v_bias, rho_sample_norm)
    maxfev = int(max(1, int(max_nfev if max_nfev is not None else curve_fit_maxfev)))

    fit_abs_source = "manual"
    fit_abs_used = fit_abs_max
    fit_abs_numeric = np.nan if fit_abs_used is None else float(fit_abs_used)
    if fit_abs_source_override is not None and np.isfinite(fit_abs_numeric) and fit_abs_numeric > 0:
        fit_abs_source = str(fit_abs_source_override)
    elif fit_abs_used is None or (not np.isfinite(fit_abs_numeric)) or fit_abs_numeric <= 0:
        fit_abs_used = estimate_fit_abs_max(vv, yy)
        fit_abs_source = "auto"
    fit_mask = np.isfinite(vv) & np.isfinite(yy)
    if fit_abs_used is not None:
        abs_max = float(fit_abs_used)
        if np.isfinite(abs_max) and abs_max > 0:
            fit_mask &= np.abs(vv) <= abs_max
    if np.count_nonzero(fit_mask) < 21:
        raise ValueError("Need at least 21 DOS points for the selected gap-model fit.")

    vv_fit = np.asarray(vv[fit_mask], dtype=float)
    yy_fit = np.asarray(yy[fit_mask], dtype=float)
    fit_n = min(ensure_odd_grid_size(vv_fit.size, minimum=21), ensure_odd_grid_size(fit_grid_max, minimum=21))
    fit_grid = np.linspace(float(vv_fit[0]), float(vv_fit[-1]), int(fit_n), dtype=float)
    data_fit = resample_trace(vv_fit, yy_fit, fit_grid, extrapolation="linear")

    strategy = str(fit_strategy or DOS_FIT_STRATEGY_MULTISTART_WEIGHTED).strip().lower()
    legacy_curve_fit = strategy in {
        "paper",
        DOS_FIT_STRATEGY_PAPER,
        "legacy",
        "legacy_curve_fit",
        "single_curve_fit",
        "curve_fit",
    }
    if legacy_curve_fit:
        strategy = DOS_FIT_STRATEGY_PAPER
    elif strategy in {"multistart", "weighted_multistart"}:
        strategy = DOS_FIT_STRATEGY_MULTISTART_WEIGHTED
    use_feature_weights = not legacy_curve_fit
    fit_weights = feature_weights(fit_grid, data_fit) if use_feature_weights else np.ones_like(data_fit, dtype=float)
    weighted_data_fit = np.asarray(data_fit, dtype=float) * np.asarray(fit_weights, dtype=float)

    specs = get_deconvolution_fit_param_spec(model)
    if not specs:
        raise ValueError(f"Unsupported DOS-fit model: {model}")
    if initial_params is None:
        p0 = [float(spec["initial"]) for spec in specs]
        for idx, spec in enumerate(specs):
            if str(spec.get("key")) in ("gamma_meV", "gamma1_meV", "gamma2_meV", "gamma3_meV"):
                p0[idx] = float(max(0.0, gamma_meV))
    else:
        p0 = [float(v) for v in initial_params]
        default_p0 = [float(spec["initial"]) for spec in specs]
        for idx, spec in enumerate(specs):
            if str(spec.get("key")) in ("gamma_meV", "gamma1_meV", "gamma2_meV", "gamma3_meV"):
                default_p0[idx] = float(max(0.0, gamma_meV))
        if len(p0) < len(default_p0):
            p0.extend(default_p0[len(p0):])
        elif len(p0) > len(default_p0):
            p0 = p0[: len(default_p0)]
    lower = [float(spec["lower"]) for spec in specs]
    upper = [float(spec["upper"]) for spec in specs]
    p0 = [
        float(np.clip(p0[i], lower[i] + 1e-9, upper[i] - 1e-9 if np.isfinite(upper[i]) else p0[i]))
        for i in range(len(specs))
    ]
    start_candidates = _gap_fit_initial_guesses(model, specs, fit_grid, data_fit, gamma_meV, lower, upper, p0)
    if initial_params is not None:
        start_candidates = [p0] + [start for start in start_candidates if tuple(start) != tuple(p0)]
    if maxfev <= 1000:
        start_candidates = start_candidates[:2]
    if fit_max_starts is not None:
        try:
            start_candidates = start_candidates[: max(1, int(fit_max_starts))]
        except Exception:
            pass

    def canonicalize(values: Sequence[float]) -> list[float]:
        vals = [float(v) for v in values]
        if model == MODEL_TWO_BAND_ANISOTROPIC_FESE:
            return [float(v) for v in order_fese_parameters(*vals)]
        if model == MODEL_THREE_BAND_S:
            keys = [str(spec.get("key", "")) for spec in specs]
            try:
                i_w1 = keys.index("weight1")
                i_w2 = keys.index("weight2")
                vals[i_w1], vals[i_w2], _w3 = normalize_three_band_weights(vals[i_w1], vals[i_w2])
            except Exception:
                pass
        return vals

    def evaluate_model_with_affine_reference(params: Sequence[float]):
        ordered = canonicalize(params)
        param_values = map_deconvolution_fit_values(model, ordered)
        model_display_raw = evaluate_gap_model_raw(
            vv,
            model,
            param_values,
            gaussian_sigma_mV=gaussian_sigma_mV,
            gamma_meV=gamma_meV,
            theta_count=theta_count,
            apply_gaussian_broadening=apply_model_gaussian_broadening,
        )
        model_fit_raw = resample_trace(vv, model_display_raw, fit_grid, extrapolation="linear")
        affine_scale, affine_offset = solve_affine_reference_scale_offset(
            model_fit_raw,
            data_fit,
            fit_weights if use_feature_weights else None,
        )
        model_display = affine_scale * np.asarray(model_display_raw, dtype=float) + affine_offset
        model_fit = affine_scale * np.asarray(model_fit_raw, dtype=float) + affine_offset
        affine_meta = {
            "enabled": True,
            "method": "fit_window_affine",
            "scale": float(affine_scale),
            "offset": float(affine_offset),
        }
        return np.asarray(model_display, dtype=float), np.asarray(model_fit, dtype=float), param_values, affine_meta

    def model_at(xv, *params):
        if cancel_callback is not None:
            try:
                cancel_result = cancel_callback()
                if isinstance(cancel_result, str) and cancel_result.strip():
                    raise RuntimeError(str(cancel_result).strip())
                if bool(cancel_result):
                    raise RuntimeError("DOS fit canceled.")
            except RuntimeError:
                raise
            except Exception:
                pass
        _model_display, model_fit_affine, _param_values, _affine_meta = evaluate_model_with_affine_reference(params)
        x_arr = np.asarray(xv, dtype=float)
        model_x = resample_trace(fit_grid, model_fit_affine, x_arr, extrapolation="linear")
        weights_x = resample_trace(fit_grid, fit_weights, x_arr, extrapolation="constant")
        return np.asarray(model_x * weights_x, dtype=float)

    best: tuple[float, list[float], str, str] | None = None
    last_exc: Exception | None = None

    def record_candidate(params: Sequence[float], status: str, message: str = "") -> None:
        nonlocal best
        ordered_i = canonicalize(params)
        try:
            _model_display_i, model_fit_i, _param_values_i, _model_norm_meta_i = evaluate_model_with_affine_reference(ordered_i)
        except Exception:
            return
        weighted_rss = float(np.sum((np.asarray(fit_weights, dtype=float) * (np.asarray(model_fit_i, dtype=float) - data_fit)) ** 2))
        if (not np.isfinite(weighted_rss)) or weighted_rss < 0:
            return
        if best is None or weighted_rss < best[0]:
            best = (weighted_rss, ordered_i, str(status), str(message or ""))

    if legacy_curve_fit:
        try:
            popt, _pcov = curve_fit(
                model_at,
                np.asarray(fit_grid, dtype=float),
                np.asarray(weighted_data_fit, dtype=float),
                p0=p0,
                bounds=(lower, upper),
                maxfev=maxfev,
            )
            record_candidate(popt, "converged", "")
        except RuntimeError:
            raise
        except Exception as exc:
            last_exc = exc
    else:
        for start in start_candidates:
            record_candidate(start, "initial_guess", "")
            try:
                def residual(params):
                    return model_at(np.asarray(fit_grid, dtype=float), *params) - np.asarray(weighted_data_fit, dtype=float)

                lsq = _least_squares_compat(residual, np.asarray(start, dtype=float), bounds=(lower, upper), max_nfev=maxfev)
                status = "converged" if bool(getattr(lsq, "success", False)) else "iteration_limit"
                record_candidate(getattr(lsq, "x", start), status, getattr(lsq, "message", ""))
            except RuntimeError:
                raise
            except Exception as exc:
                last_exc = exc
                continue

    if best is None:
        if last_exc is not None:
            raise RuntimeError(str(last_exc))
        raise RuntimeError("DOS fit failed to produce a finite candidate.")

    best_rss, best_params, best_status, best_message = best
    best_params = canonicalize(best_params)
    model_display, model_fit, param_values, model_norm_meta = evaluate_model_with_affine_reference(best_params)
    residual_display = np.asarray(yy, dtype=float) - np.asarray(model_display, dtype=float)
    fit_residual = np.asarray(data_fit, dtype=float) - np.asarray(model_fit, dtype=float)
    ss_res = float(np.sum(fit_residual**2))
    centered = np.asarray(data_fit, dtype=float) - float(np.nanmean(data_fit))
    ss_tot = float(np.sum(centered**2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 1e-15 else np.nan
    param_order = [str(spec.get("key", "")) for spec in specs]
    summary_params = build_gap_model_summary_params(model, param_values)

    return {
        "model_name": str(model),
        "bias_display": np.asarray(vv, dtype=float),
        "rho_data_display": np.asarray(yy, dtype=float),
        "rho_model_display": np.asarray(model_display, dtype=float),
        "rho_model_display_full": np.asarray(model_display, dtype=float),
        "bias_fit": np.asarray(fit_grid, dtype=float),
        "rho_data_fit": np.asarray(data_fit, dtype=float),
        "rho_model_fit": np.asarray(model_fit, dtype=float),
        "residual_display": np.asarray(residual_display, dtype=float),
        "param_order": param_order,
        "param_values": {str(key): float(value) for key, value in param_values.items()},
        "param_bounds": [
            {"key": str(spec.get("key", "")), "lower": float(spec.get("lower", np.nan)), "upper": float(spec.get("upper", np.nan))}
            for spec in specs
        ],
        "summary_params": summary_params,
        "gamma_meV": float(gamma_meV),
        "gaussian_sigma_mV": float(gaussian_sigma_mV),
        "r2": r2,
        "fit_status": str(best_status),
        "fit_status_message": str(best_message),
        "fit_strategy": str(strategy),
        "fit_max_starts": int(len(start_candidates)),
        "fit_multistart_count": int(len(start_candidates)),
        "fit_feature_weighted": bool(use_feature_weights),
        "fit_weighted_rss": float(best_rss),
        "fit_abs_max": _as_float(fit_abs_used),
        "fit_abs_source": str(fit_abs_source),
        "fit_roi_pct": _as_float(fit_roi_pct),
        "fit_point_count": int(len(fit_grid)),
        "initial_params": [float(v) for v in p0],
        "model_norm_meta": dict(model_norm_meta),
        "model_norm_scope": "fit_window_affine",
        "normalization_meta": dict(normalization_meta or {}),
    }


def fit_gap_model_guarded(
    v_bias: Sequence[float],
    rho_sample_norm: Sequence[float],
    *,
    time_budget_s: Optional[float] = DEFAULT_DOS_FIT_TIME_BUDGET_S,
    cancel_callback=None,
    **fit_kwargs,
) -> dict[str, Any]:
    model_name = normalize_gap_model_name(fit_kwargs.get("model_name", MODEL_TWO_BAND_ANISOTROPIC_FESE))
    fit_strategy = str(fit_kwargs.get("fit_strategy", DOS_FIT_STRATEGY_MULTISTART_WEIGHTED) or DOS_FIT_STRATEGY_MULTISTART_WEIGHTED)
    fit_max_starts = fit_kwargs.get("fit_max_starts")
    gaussian_sigma = fit_kwargs.get("gaussian_sigma_mV", DEFAULT_PAPER_DOS_BROAD_SIGMA_MV)
    fit_abs_max = fit_kwargs.get("fit_abs_max")
    fit_abs_source = fit_kwargs.get("fit_abs_source_override")
    fit_roi_pct = fit_kwargs.get("fit_roi_pct")
    normalization_meta = dict(fit_kwargs.get("normalization_meta") or {})
    combined_cancel = combine_cancel_callbacks(cancel_callback, make_time_budget_callback(time_budget_s))
    try:
        return fit_gap_model(
            v_bias,
            rho_sample_norm,
            cancel_callback=combined_cancel,
            **fit_kwargs,
        )
    except Exception as exc:
        rho_data = np.asarray(rho_sample_norm, dtype=float)
        error_message = format_fit_failure_message(exc)
        try:
            fit_max_starts_value = int(max(1, int(fit_max_starts)))
        except Exception:
            fit_max_starts_value = np.nan
        return {
            "model_name": str(model_name),
            "bias_display": np.asarray(v_bias, dtype=float),
            "rho_data_display": rho_data,
            "rho_model_display": np.full_like(rho_data, np.nan, dtype=float),
            "rho_model_display_full": np.full_like(rho_data, np.nan, dtype=float),
            "summary_params": [],
            "gaussian_sigma_mV": _as_float(gaussian_sigma),
            "r2": np.nan,
            "fit_status": "not_converged" if "converge" in error_message.lower() else "failed",
            "fit_status_message": error_message,
            "fit_strategy": fit_strategy,
            "fit_max_starts": fit_max_starts_value,
            "fit_multistart_count": fit_max_starts_value,
            "fit_feature_weighted": str(fit_strategy).lower() != DOS_FIT_STRATEGY_PAPER,
            "fit_weighted_rss": np.nan,
            "fit_abs_max": _as_float(fit_abs_max),
            "fit_abs_source": str(fit_abs_source or ""),
            "fit_roi_pct": _as_float(fit_roi_pct),
            "normalization_meta": normalization_meta,
            "model_norm_meta": {},
            "model_norm_scope": "",
            "error": error_message,
        }
