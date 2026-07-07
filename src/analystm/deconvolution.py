from __future__ import annotations

from functools import partial
from typing import Any, Optional, Sequence

import numpy as np
from scipy.integrate import simpson
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import least_squares

from .numerics import ensure_odd_grid_size, gaussian_broaden_uniform_trace, median_bias_step, normalize_xy_arrays, resample_trace


KB_MEV_PER_K = 8.617333262145e-2
DEFAULT_TIP_DELTA_MEV = 1.2
DEFAULT_TIP_GAMMA_MEV = 0.006
DEFAULT_DOS_BROAD_SIGMA_MV = 0.17
DEFAULT_TIP_FIT_GAUSSIAN_SIGMA_MV = 0.13
TIP_FIT_MODE_NIS = "NIS"
TIP_FIT_MODE_SIS = "SIS"


def _min_finite_grid_step(*grids: Sequence[float]) -> float:
    steps = []
    for grid in grids:
        try:
            step = median_bias_step(grid)
        except Exception:
            step = np.nan
        if np.isfinite(step) and step > 0:
            steps.append(float(step))
    return float(min(steps)) if steps else np.nan


def _use_zero_temperature_limit(temperature_K: float, *grids: Sequence[float]) -> bool:
    temp = float(max(0.0, temperature_K))
    if temp <= 1e-10:
        return True
    step = _min_finite_grid_step(*grids)
    if not np.isfinite(step) or step <= 0:
        return False
    return bool(KB_MEV_PER_K * temp < 0.5 * step)


def _dynes_gamma_floor(*grids: Sequence[float], gaussian_sigma_mV: float = 0.0) -> float:
    step = _min_finite_grid_step(*grids)
    floor = 0.002
    if np.isfinite(step) and step > 0:
        floor = max(floor, 0.10 * float(step))
    sigma = float(max(0.0, gaussian_sigma_mV))
    if sigma > 0:
        floor = max(floor, 0.02 * sigma)
    return float(floor)


def symmetrize_bias_trace(v_bias: Sequence[float], y: Sequence[float], n_grid: Optional[int] = None) -> tuple[np.ndarray, np.ndarray]:
    vv, yy = normalize_xy_arrays(v_bias, y)
    neg_span = float(abs(np.nanmin(vv))) if np.nanmin(vv) < 0 else 0.0
    pos_span = float(np.nanmax(vv)) if np.nanmax(vv) > 0 else 0.0
    span = float(min(neg_span, pos_span))
    if (not np.isfinite(span)) or span <= 0:
        raise ValueError("Energy symmetrization requires both negative and positive bias coverage around 0.")
    mask = (vv >= -span) & (vv <= span)
    if np.count_nonzero(mask) < 9:
        raise ValueError("Not enough overlap between positive and negative bias branches for symmetrization.")
    n_use = ensure_odd_grid_size(n_grid if n_grid else int(np.count_nonzero(mask)), minimum=9)
    grid = np.linspace(-span, span, n_use, dtype=float)
    y_pos = np.interp(grid, vv, yy)
    y_neg = np.interp(-grid, vv, yy)
    return np.asarray(grid, dtype=float), np.asarray(0.5 * (y_pos + y_neg), dtype=float)


def _fermi_dirac_mev(energy_meV: Any, temperature_K: float) -> np.ndarray:
    ee = np.asarray(energy_meV, dtype=float)
    temp = float(max(0.0, temperature_K))
    if temp <= 1e-10:
        return np.where(ee < 0.0, 1.0, 0.0).astype(float)
    kbt = KB_MEV_PER_K * temp
    arg = np.clip(ee / max(kbt, 1e-12), -700.0, 700.0)
    return 1.0 / (np.exp(arg) + 1.0)


def _fermi_dirac_prime_mev(energy_meV: Any, temperature_K: float) -> np.ndarray:
    ee = np.asarray(energy_meV, dtype=float)
    temp = float(max(0.0, temperature_K))
    if temp <= 1e-10:
        width = 1e-6
        return -np.exp(-0.5 * (ee / width) ** 2) / (np.sqrt(2.0 * np.pi) * width)
    kbt = KB_MEV_PER_K * temp
    arg = np.clip(ee / (2.0 * max(kbt, 1e-12)), -350.0, 350.0)
    cosh_term = np.cosh(arg)
    return -1.0 / (4.0 * kbt * cosh_term * cosh_term)


def dynes_dos(energy_meV: Sequence[float], delta_meV: float, gamma_meV: float) -> np.ndarray:
    ee = np.asarray(energy_meV, dtype=float)
    delta = float(max(0.0, delta_meV))
    gamma = float(max(0.0, gamma_meV))
    z = ee - 1j * gamma
    root = np.sqrt(z * z - delta * delta + 0j)
    with np.errstate(divide="ignore", invalid="ignore"):
        dos = np.real(z / root)
    return np.asarray(np.abs(np.nan_to_num(dos, nan=0.0, posinf=0.0, neginf=0.0)), dtype=float)


def compute_nis_didv_from_dos(
    sample_energy_grid: Sequence[float],
    rho_sample: Sequence[float],
    bias_grid: Sequence[float],
    temperature_K: float,
    gaussian_sigma_mV: float = 0.0,
) -> np.ndarray:
    e_grid = np.asarray(sample_energy_grid, dtype=float).ravel()
    rho_s = np.asarray(rho_sample, dtype=float).ravel()
    v_grid = np.asarray(bias_grid, dtype=float).ravel()
    if e_grid.size < 3 or rho_s.size != e_grid.size:
        raise ValueError("Invalid sample DOS grid for NIS dI/dV.")
    order = np.argsort(e_grid)
    e_grid = e_grid[order]
    rho_s = rho_s[order]
    if _use_zero_temperature_limit(temperature_K, e_grid, v_grid):
        didv = np.interp(v_grid, e_grid, rho_s, left=float(rho_s[0]), right=float(rho_s[-1]))
    else:
        didv = np.empty(v_grid.size, dtype=float)
        for idx, vv in enumerate(v_grid):
            kernel = -_fermi_dirac_prime_mev(e_grid - float(vv), temperature_K)
            didv[idx] = float(simpson(rho_s * kernel, x=e_grid))
    if float(max(0.0, gaussian_sigma_mV)) > 0:
        didv = gaussian_broaden_uniform_trace(v_grid, didv, gaussian_sigma_mV)
    return np.asarray(didv, dtype=float)


def compute_sis_didv_from_dos(
    sample_energy_grid: Sequence[float],
    rho_sample: Sequence[float],
    bias_grid: Sequence[float],
    tip_support_bias: Sequence[float],
    rho_tip_support: Sequence[float],
    temperature_K: float,
    gaussian_sigma_mV: float = 0.0,
) -> np.ndarray:
    e_grid = np.asarray(sample_energy_grid, dtype=float).ravel()
    rho_s = np.asarray(rho_sample, dtype=float).ravel()
    v_grid = np.asarray(bias_grid, dtype=float).ravel()
    tip_bias = np.asarray(tip_support_bias, dtype=float).ravel()
    rho_tip = np.asarray(rho_tip_support, dtype=float).ravel()
    if e_grid.size < 3 or rho_s.size != e_grid.size:
        raise ValueError("Invalid sample DOS grid for SIS dI/dV.")
    if tip_bias.size < 3 or rho_tip.size != tip_bias.size:
        raise ValueError("Invalid tip DOS support grid for SIS dI/dV.")
    if not (np.all(np.isfinite(e_grid)) and np.all(np.isfinite(rho_s))):
        raise ValueError("SIS dI/dV sample DOS grid must be finite.")
    if not (np.all(np.isfinite(tip_bias)) and np.all(np.isfinite(rho_tip))):
        raise ValueError("SIS dI/dV tip DOS support grid must be finite.")

    e_order = np.argsort(e_grid)
    e_grid = np.asarray(e_grid[e_order], dtype=float)
    rho_s = np.asarray(rho_s[e_order], dtype=float)
    tip_order = np.argsort(tip_bias)
    tip_bias = np.asarray(tip_bias[tip_order], dtype=float)
    rho_tip = np.asarray(rho_tip[tip_order], dtype=float)

    drho_tip = np.gradient(rho_tip, tip_bias, edge_order=2 if tip_bias.size >= 3 else 1)
    f_e = _fermi_dirac_mev(e_grid, temperature_K)
    didv = np.empty(v_grid.size, dtype=float)
    for idx, voltage in enumerate(v_grid):
        shifted = e_grid - float(voltage)
        rho_eval = np.interp(
            shifted,
            tip_bias,
            rho_tip,
            left=float(rho_tip[0]),
            right=float(rho_tip[-1]),
        )
        drho_eval = np.interp(
            shifted,
            tip_bias,
            drho_tip,
            left=float(drho_tip[0]),
            right=float(drho_tip[-1]),
        )
        f_shift = _fermi_dirac_mev(shifted, temperature_K)
        fp_shift = _fermi_dirac_prime_mev(shifted, temperature_K)
        integrand = rho_s * (-drho_eval * (f_shift - f_e) - rho_eval * fp_shift)
        didv[idx] = float(simpson(integrand, x=e_grid))
    if float(max(0.0, gaussian_sigma_mV)) > 0:
        didv = gaussian_broaden_uniform_trace(bias_grid, didv, gaussian_sigma_mV)
    return np.asarray(didv, dtype=float)


def _simulate_nis_didv_dynes_fine(
    bias_grid: Sequence[float],
    delta_meV: float,
    gamma_meV: float,
    temperature_K: float,
    gaussian_sigma_mV: float = 0.0,
) -> np.ndarray:
    vv = np.asarray(bias_grid, dtype=float).ravel()
    temp = float(max(0.0, temperature_K))
    gamma_use = float(max(float(gamma_meV), _dynes_gamma_floor(vv, gaussian_sigma_mV=gaussian_sigma_mV)))
    if _use_zero_temperature_limit(temp, vv):
        didv = dynes_dos(vv, float(delta_meV), gamma_use)
    else:
        gap = float(max(abs(delta_meV), 1e-9))
        max_v = float(np.nanmax(np.abs(vv)))
        limit = max(max_v * 3.0, max_v + 10.0 * gap + 15.0 * KB_MEV_PER_K * temp)
        e_grid = np.linspace(-limit, limit, 2049, dtype=float)
        didv = compute_nis_didv_from_dos(e_grid, dynes_dos(e_grid, float(delta_meV), gamma_use), vv, temp)
    if float(max(0.0, gaussian_sigma_mV)) > 0:
        didv = gaussian_broaden_uniform_trace(vv, didv, gaussian_sigma_mV)
    return np.asarray(didv, dtype=float)


def _simulate_sis_didv_dynes_fine(
    bias_grid: Sequence[float],
    delta_meV: float,
    gamma_meV: float,
    temperature_K: float,
    gaussian_sigma_mV: float = 0.0,
) -> np.ndarray:
    vv = np.asarray(bias_grid, dtype=float).ravel()
    temp = float(max(0.0, temperature_K))
    gap = float(max(abs(delta_meV), 1e-9))
    max_v = float(np.nanmax(np.abs(vv)))
    sample_limit = max(max_v * 3.0, max_v + 10.0 * gap + 15.0 * KB_MEV_PER_K * temp, 8.0 * gap)
    sample_grid = np.linspace(-sample_limit, sample_limit, 2049, dtype=float)
    gamma_use = float(max(float(gamma_meV), _dynes_gamma_floor(sample_grid, vv, gaussian_sigma_mV=gaussian_sigma_mV)))
    rho = dynes_dos(sample_grid, float(delta_meV), gamma_use)
    tip_support = np.linspace(-(sample_limit + max_v), sample_limit + max_v, 4097, dtype=float)
    rho_tip = dynes_dos(tip_support, float(delta_meV), gamma_use)
    didv = compute_sis_didv_from_dos(sample_grid, rho, vv, tip_support, rho_tip, temp)
    if float(max(0.0, gaussian_sigma_mV)) > 0:
        didv = gaussian_broaden_uniform_trace(vv, didv, gaussian_sigma_mV)
    return np.asarray(didv, dtype=float)


def _fit_dynes(
    v_bias: Sequence[float],
    didv: Sequence[float],
    *,
    mode: str,
    temperature_K: float,
    gaussian_sigma_mV: float,
    exclude_region: tuple[float, float] | None = None,
    symmetrize: bool = True,
) -> dict[str, Any]:
    vv_raw, yy_raw = normalize_xy_arrays(v_bias, didv)
    vv_fit, yy_fit = symmetrize_bias_trace(vv_raw, yy_raw) if symmetrize else (vv_raw, yy_raw)
    fit_mask = np.isfinite(vv_fit) & np.isfinite(yy_fit)
    if exclude_region is not None:
        a, b = sorted([float(exclude_region[0]), float(exclude_region[1])])
        fit_mask &= ~((vv_fit >= a) & (vv_fit <= b))
    if np.count_nonzero(fit_mask) < 15:
        raise ValueError(f"Not enough points remain for fixed-temperature {mode} Dynes fitting.")
    x_fit = vv_fit[fit_mask]
    y_fit = yy_fit[fit_mask]
    y_s = gaussian_filter1d(yy_fit, sigma=2.0, mode="nearest")
    step = median_bias_step(vv_fit)
    exclude = max(0.12, 3.0 * step) if np.isfinite(step) and step > 0 else 0.12
    peak_mask = np.abs(vv_fit) >= exclude
    if np.count_nonzero(peak_mask) < 4:
        peak_mask = np.isfinite(vv_fit) & np.isfinite(y_s)
    peak_abs = float(abs(vv_fit[peak_mask][int(np.argmax(y_s[peak_mask]))])) if np.any(peak_mask) else 1.0
    delta0 = float(max(0.05, 0.5 * peak_abs if mode == TIP_FIT_MODE_SIS else peak_abs))
    gamma_floor = _dynes_gamma_floor(vv_fit, gaussian_sigma_mV=gaussian_sigma_mV)
    gamma0 = min(max(0.002, 0.02 * delta0), 0.2)
    amp0 = float(max(np.nanmax(y_fit) - np.nanmin(y_fit), 1e-6))
    off0 = float(np.nanmedian(y_fit[np.abs(x_fit) > 0.8 * np.nanmax(np.abs(x_fit))])) if x_fit.size else 0.0

    def residual(params):
        delta, gamma, scale, offset = [float(v) for v in params]
        base = _simulate_sis_didv_dynes_fine(x_fit, delta, gamma, temperature_K, gaussian_sigma_mV) if mode == TIP_FIT_MODE_SIS else _simulate_nis_didv_dynes_fine(x_fit, delta, gamma, temperature_K, gaussian_sigma_mV)
        return np.asarray(scale * base + offset - y_fit, dtype=float)

    result = least_squares(
        residual,
        x0=np.asarray([delta0, max(gamma0, gamma_floor), amp0, off0], dtype=float),
        bounds=(np.asarray([0.05, gamma_floor, 0.0, -np.inf]), np.asarray([10.0, 1.0, np.inf, np.inf])),
        max_nfev=20000,
    )
    delta, gamma, scale, offset = [float(v) for v in result.x]
    full_base = _simulate_sis_didv_dynes_fine(vv_fit, delta, gamma, temperature_K, gaussian_sigma_mV) if mode == TIP_FIT_MODE_SIS else _simulate_nis_didv_dynes_fine(vv_fit, delta, gamma, temperature_K, gaussian_sigma_mV)
    fit_full = scale * full_base + offset
    residual_full = yy_fit - fit_full
    mask = np.isfinite(residual_full) & np.isfinite(yy_fit)
    r2 = np.nan
    if np.any(mask):
        ss_res = float(np.sum(residual_full[mask] ** 2))
        ss_tot = float(np.sum((yy_fit[mask] - float(np.mean(yy_fit[mask]))) ** 2))
        if ss_tot > 0:
            r2 = 1.0 - ss_res / ss_tot
    return {
        "bias_fit": vv_fit,
        "didv_fit_input": yy_fit,
        "didv_fit_model": np.asarray(fit_full, dtype=float),
        "delta_meV": delta,
        "gamma_meV": gamma,
        "scale": scale,
        "offset": offset,
        "temperature_K": float(max(0.0, temperature_K)),
        "gaussian_sigma_mV": float(max(0.0, gaussian_sigma_mV)),
        "gamma_floor_meV": float(gamma_floor),
        "r2": float(r2) if np.isfinite(r2) else np.nan,
        "exclude_region": None if exclude_region is None else [float(min(exclude_region)), float(max(exclude_region))],
        "fit_mode": f"{mode.lower()}_dynes_didv_fixed_t",
    }


def fit_nis_dynes_didv(*args, **kwargs) -> dict[str, Any]:
    return _fit_dynes(*args, mode=TIP_FIT_MODE_NIS, **kwargs)


def fit_sis_dynes_didv(*args, **kwargs) -> dict[str, Any]:
    return _fit_dynes(*args, mode=TIP_FIT_MODE_SIS, **kwargs)


def build_paper_sis_grids(
    meas_bias: Sequence[float],
    n_grid: Optional[int] = None,
    target_abs_max: Optional[float] = None,
    display_cap: int = 1001,
    solve_cap: int = 2001,
) -> dict[str, Any]:
    vm = np.asarray(meas_bias, dtype=float).ravel()
    vm = vm[np.isfinite(vm)]
    if vm.size < 2:
        raise ValueError("Need a valid measured bias trace before building the deconvolution grids.")
    display_abs = float(np.nanmax(np.abs(vm)))
    step = median_bias_step(vm)
    if (not np.isfinite(step)) or step <= 0:
        step = max((2.0 * display_abs) / max(len(vm) - 1, 1), 1e-3)
    if n_grid is None or int(n_grid) <= 0:
        n_display = min(ensure_odd_grid_size(int(np.round((2.0 * display_abs) / step)) + 1, minimum=9), ensure_odd_grid_size(display_cap, minimum=9))
    else:
        n_display = ensure_odd_grid_size(n_grid, minimum=9)
    solve_abs = max(display_abs, float(target_abs_max) if target_abs_max is not None else 2.0 * display_abs)
    n_solve = int(np.round((2.0 * solve_abs) / step)) + 1
    n_solve = min(ensure_odd_grid_size(max(n_solve, n_display), minimum=n_display), ensure_odd_grid_size(solve_cap, minimum=n_display))
    return {
        "display_grid": np.linspace(-display_abs, display_abs, int(n_display), dtype=float),
        "solve_grid": np.linspace(-solve_abs, solve_abs, int(n_solve), dtype=float),
        "sample_abs_max": float(display_abs),
        "solve_abs_max": float(solve_abs),
    }


def prepare_measured_trace(
    meas_bias: Sequence[float],
    meas_didv: Sequence[float],
    *,
    display_grid: Sequence[float],
    solve_grid: Sequence[float],
    symmetrize_measured: bool = True,
) -> dict[str, np.ndarray]:
    vm_raw, gm_raw = normalize_xy_arrays(meas_bias, meas_didv)
    if symmetrize_measured:
        vm_used, gm_used = symmetrize_bias_trace(vm_raw, gm_raw)
    else:
        vm_used, gm_used = vm_raw, gm_raw
    return {
        "meas_raw_bias": vm_raw,
        "meas_raw_didv": gm_raw,
        "meas_used_bias": vm_used,
        "meas_used_didv": gm_used,
        "didv_display_raw": resample_trace(vm_raw, gm_raw, display_grid, extrapolation="linear"),
        "didv_display_used": resample_trace(vm_used, gm_used, display_grid, extrapolation="linear"),
        "didv_solve_used": resample_trace(vm_used, gm_used, solve_grid, extrapolation="linear"),
    }


def build_sis_didv_matrix(
    sample_energy_grid: Sequence[float],
    bias_grid: Sequence[float],
    tip_support_bias: Sequence[float],
    rho_tip_support: Sequence[float],
    temperature_K: float,
) -> np.ndarray:
    e_grid = np.asarray(sample_energy_grid, dtype=float).ravel()
    v_grid = np.asarray(bias_grid, dtype=float).ravel()
    tip_bias = np.asarray(tip_support_bias, dtype=float).ravel()
    rho_tip = np.asarray(rho_tip_support, dtype=float).ravel()
    if e_grid.size < 3 or v_grid.size < 3:
        raise ValueError("SIS deconvolution needs at least 3 energy points.")
    d_e = median_bias_step(e_grid)
    if (not np.isfinite(d_e)) or d_e <= 0:
        raise ValueError("SIS deconvolution requires a finite uniform-like bias spacing.")
    drho_tip = np.gradient(rho_tip, tip_bias, edge_order=2 if tip_bias.size >= 3 else 1)
    e_vals = e_grid[None, :]
    v_vals = v_grid[:, None]
    shifted = e_vals - v_vals
    rho_eval = np.interp(shifted.ravel(), tip_bias, rho_tip, left=float(rho_tip[0]), right=float(rho_tip[-1])).reshape(shifted.shape)
    drho_eval = np.interp(shifted.ravel(), tip_bias, drho_tip, left=float(drho_tip[0]), right=float(drho_tip[-1])).reshape(shifted.shape)
    use_zero = _use_zero_temperature_limit(temperature_K, e_grid, v_grid)
    temp_eval = 0.0 if use_zero else float(max(0.0, temperature_K))
    f_e = _fermi_dirac_mev(e_grid, temp_eval)[None, :]
    f_shift = _fermi_dirac_mev(shifted, temp_eval)
    kernel = (-drho_eval * (f_shift - f_e)) * float(d_e)
    if use_zero:
        rho_tip_zero = float(np.interp(0.0, tip_bias, rho_tip))
        for row, vv in enumerate(v_grid):
            if float(vv) < float(e_grid[0]) or float(vv) > float(e_grid[-1]):
                continue
            hi = int(np.searchsorted(e_grid, float(vv), side="left"))
            if hi <= 0:
                kernel[row, 0] += rho_tip_zero
            elif hi >= e_grid.size:
                kernel[row, -1] += rho_tip_zero
            else:
                left = float(e_grid[hi - 1])
                right = float(e_grid[hi])
                weight = float((float(vv) - left) / max(right - left, 1e-18))
                kernel[row, hi - 1] += rho_tip_zero * (1.0 - weight)
                kernel[row, hi] += rho_tip_zero * weight
    else:
        kernel -= rho_eval * _fermi_dirac_prime_mev(shifted, temp_eval) * float(d_e)
    return np.asarray(kernel, dtype=float)


def solve_sis_sample_dos(
    didv_matrix: Sequence[Sequence[float]],
    measured_didv: Sequence[float],
    pinv_rcond: float = 1e-2,
    weights: Optional[Sequence[float]] = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    y_mat = np.asarray(didv_matrix, dtype=float)
    g_vec = np.asarray(measured_didv, dtype=float).ravel()
    if y_mat.ndim != 2 or g_vec.size != y_mat.shape[0]:
        raise ValueError("Measured dI/dV size does not match the SIS operator grid.")
    w_vec = np.ones_like(g_vec, dtype=float) if weights is None else np.asarray(weights, dtype=float).ravel()
    if w_vec.size != g_vec.size:
        raise ValueError("Weight vector size does not match measured dI/dV.")
    finite_w = np.isfinite(w_vec) & (w_vec > 0)
    if not np.any(finite_w):
        raise ValueError("No positive finite weights remain for weighted SIS inversion.")
    w_vec = np.where(finite_w, w_vec, 0.0)
    sqrt_w = np.sqrt(w_vec)
    y_eff = y_mat * sqrt_w[:, None]
    g_eff = g_vec * sqrt_w
    u, s, vh = np.linalg.svd(np.nan_to_num(y_eff, nan=0.0, posinf=0.0, neginf=0.0), full_matrices=False)
    if s.size == 0:
        raise ValueError("SIS operator SVD failed.")
    rel_cut = float(max(0.0, pinv_rcond))
    tol = float(max(np.finfo(float).eps, rel_cut) * s[0])
    keep = s > tol
    if not np.any(keep):
        raise ValueError("Pseudo-inverse cutoff removed every singular value. Lower pinv rcond.")
    inv_s = np.zeros_like(s)
    inv_s[keep] = 1.0 / s[keep]
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        rho_s = (vh.T * inv_s) @ (u.T @ g_eff)
    meta = {
        "pinv_rcond": rel_cut,
        "sv_max": float(s[0]),
        "sv_min_kept": float(np.min(s[keep])),
        "rank_kept": int(np.count_nonzero(keep)),
        "rank_total": int(s.size),
        "condition_kept": float(s[0] / np.min(s[keep])),
        "weighting": {"enabled": weights is not None},
    }
    return np.asarray(rho_s, dtype=float), meta


def normalize_sample_dos_display(v_bias: Sequence[float], rho_s: Sequence[float], tail_fraction: float = 0.30) -> tuple[np.ndarray, dict[str, Any]]:
    vv = np.asarray(v_bias, dtype=float).ravel()
    rr = np.asarray(rho_s, dtype=float).ravel()
    if vv.size == 0 or rr.size != vv.size:
        return np.asarray(rr, dtype=float), {"enabled": False}
    finite = np.isfinite(vv) & np.isfinite(rr)
    if not np.any(finite):
        return np.asarray(rr, dtype=float), {"enabled": False}
    max_abs = float(np.nanmax(np.abs(vv[finite])))
    if (not np.isfinite(max_abs)) or max_abs <= 0:
        return np.asarray(rr, dtype=float), {"enabled": False}
    frac = float(np.clip(tail_fraction, 0.05, 0.49))
    tail_threshold = (1.0 - frac) * max_abs
    vv_finite = np.asarray(vv[finite], dtype=float)
    step = median_bias_step(vv_finite)
    if (not np.isfinite(step)) or step <= 0:
        step = max((2.0 * max_abs) / max(vv_finite.size - 1, 1), 1e-6)
    edge_trim = float(max(4.0 * step, 0.04 * max_abs))
    upper_bound = float(max(tail_threshold, max_abs - edge_trim))
    tail_mask = finite & (np.abs(vv) >= tail_threshold) & (np.abs(vv) <= upper_bound)
    tail_vals = np.abs(rr[tail_mask])
    if tail_vals.size < 4:
        tail_mask = finite & (np.abs(vv) >= tail_threshold)
        tail_vals = np.abs(rr[tail_mask])
    if tail_vals.size < 4:
        tail_vals = np.abs(rr[finite])
    if tail_vals.size >= 8:
        high_tail_floor = float(np.nanpercentile(tail_vals, 60.0))
        robust_tail_vals = tail_vals[tail_vals >= high_tail_floor]
        if robust_tail_vals.size >= 4:
            tail_vals = np.asarray(robust_tail_vals, dtype=float)
    scale = float(np.nanmedian(tail_vals)) if tail_vals.size else np.nan
    if (not np.isfinite(scale)) or scale <= 1e-12:
        scale = float(np.nanmax(np.abs(rr[finite]))) if np.any(finite) else 1.0
    if (not np.isfinite(scale)) or scale <= 1e-12:
        scale = 1.0
    return np.asarray(rr / scale, dtype=float), {
        "enabled": True,
        "tail_fraction": frac,
        "tail_threshold_mV": float(tail_threshold),
        "edge_trim_mV": float(edge_trim),
        "scale": float(scale),
        "tail_count": int(np.count_nonzero(tail_mask)),
    }


def build_linear_resample_matrix(
    src_grid: Sequence[float],
    dst_grid: Sequence[float],
    extrapolation: str = "linear",
    edge_points: int = 7,
) -> np.ndarray:
    src = np.asarray(src_grid, dtype=float).ravel()
    dst = np.asarray(dst_grid, dtype=float).ravel()
    if src.size < 2 or dst.size == 0:
        raise ValueError("Need at least 2 source points to build a resample matrix.")
    if not np.all(np.isfinite(src)) or not np.all(np.isfinite(dst)):
        raise ValueError("Resample grids must be finite.")
    if np.any(np.diff(src) <= 0):
        raise ValueError("Source grid for resample matrix must be strictly increasing.")

    n_src = int(src.size)
    mat = np.zeros((int(dst.size), n_src), dtype=float)
    idx = np.searchsorted(src, dst, side="left")
    mode = str(extrapolation or "linear").strip().lower()
    n_edge = int(np.clip(int(edge_points), 2, max(2, n_src)))

    def edge_fit_weights(x_edge: np.ndarray, target_value: float) -> np.ndarray:
        xx = np.asarray(x_edge, dtype=float).ravel()
        if xx.size < 2 or np.nanmax(xx) - np.nanmin(xx) <= 0:
            return np.full(xx.size, 1.0 / max(1, xx.size), dtype=float)
        design = np.column_stack([xx, np.ones(xx.size, dtype=float)])
        return np.asarray([float(target_value), 1.0], dtype=float) @ np.linalg.pinv(design)

    src_min = float(src[0])
    src_max = float(src[-1])
    for row, col in enumerate(idx):
        target_value = float(dst[row])
        if target_value == src_min:
            mat[row, 0] = 1.0
            continue
        if target_value == src_max:
            mat[row, -1] = 1.0
            continue
        if target_value < src_min:
            if mode == "constant":
                mat[row, 0] = 1.0
                continue
            weights = edge_fit_weights(src[:n_edge], target_value)
            mat[row, :n_edge] = weights
            continue
        if target_value > src_max:
            if mode == "constant":
                mat[row, -1] = 1.0
                continue
            weights = edge_fit_weights(src[-n_edge:], target_value)
            mat[row, -n_edge:] = weights
            continue

        if col <= 0:
            col = 1
        elif col >= n_src:
            col = n_src - 1
        left_idx = int(col - 1)
        right_idx = int(col)
        x0 = float(src[left_idx])
        x1 = float(src[right_idx])
        if abs(x1 - x0) <= 1e-20:
            mat[row, left_idx] = 1.0
            continue
        t = (target_value - x0) / (x1 - x0)
        mat[row, left_idx] = 1.0 - t
        mat[row, right_idx] = t
    return np.asarray(mat, dtype=float)


def nanmean_cube_over_pixels(arr3d: Any, valid_mask: Any) -> np.ndarray:
    arr = np.asarray(arr3d, dtype=float)
    if arr.ndim != 3:
        raise ValueError("Expected a 3D array for pixel averaging.")
    mask2 = np.asarray(valid_mask, dtype=bool)
    if mask2.shape != arr.shape[:2]:
        raise ValueError("Valid-mask shape mismatch.")
    if not np.any(mask2):
        return np.full(arr.shape[2], np.nan, dtype=float)
    out = np.full(arr.shape[2], np.nan, dtype=float)
    for idx in range(arr.shape[2]):
        plane = arr[:, :, idx]
        vals = plane[mask2 & np.isfinite(plane)]
        if vals.size:
            out[idx] = float(np.mean(vals))
    return out


def compute_r2_score(y_true: Sequence[float], residual: Sequence[float]) -> float:
    yy = np.asarray(y_true, dtype=float).ravel()
    rr = np.asarray(residual, dtype=float).ravel()
    mask = np.isfinite(yy) & np.isfinite(rr)
    if not np.any(mask):
        return np.nan
    ss_res = float(np.sum(rr[mask] ** 2))
    mean_y = float(np.mean(yy[mask]))
    ss_tot = float(np.sum((yy[mask] - mean_y) ** 2))
    if ss_tot <= 0:
        return np.nan
    return float(1.0 - ss_res / ss_tot)


def build_pinv_operator(
    didv_matrix: Sequence[Sequence[float]],
    pinv_rcond: float = 1e-2,
    weights: Optional[Sequence[float]] = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    y_mat = np.asarray(didv_matrix, dtype=float)
    if y_mat.ndim != 2:
        raise ValueError("SIS operator must be a 2D matrix.")
    n_rows = int(y_mat.shape[0])
    weight_meta = {
        "enabled": False,
        "min_weight": 1.0,
        "reference_value": np.nan,
        "percentile": np.nan,
        "power": 1.0,
        "weight_min_applied": 1.0,
        "weight_max_applied": 1.0,
    }
    sqrt_w = np.ones(n_rows, dtype=float)
    if weights is not None:
        weight_vec = np.asarray(weights, dtype=float).ravel()
        if weight_vec.size != n_rows:
            raise ValueError("Weight vector size mismatch for weighted pseudo-inverse.")
        weight_vec = np.nan_to_num(weight_vec, nan=0.0, posinf=0.0, neginf=0.0)
        weight_vec = np.clip(weight_vec, 0.0, None)
        sqrt_w = np.sqrt(np.clip(weight_vec, 0.0, None))
        if np.count_nonzero(sqrt_w > 0) < max(4, min(15, n_rows // 4)):
            raise ValueError("Too few non-zero weighted rows remain for the pseudo-inverse.")
        weighted_matrix = y_mat * sqrt_w[:, None]
        weight_meta = {
            "enabled": True,
            "min_weight": float(np.min(weight_vec)) if weight_vec.size else 1.0,
            "reference_value": np.nan,
            "percentile": np.nan,
            "power": 1.0,
            "weight_min_applied": float(np.min(weight_vec)) if weight_vec.size else 1.0,
            "weight_max_applied": float(np.max(weight_vec)) if weight_vec.size else 1.0,
        }
    else:
        weighted_matrix = y_mat

    u, s, vh = np.linalg.svd(np.nan_to_num(weighted_matrix, nan=0.0, posinf=0.0, neginf=0.0), full_matrices=False)
    if s.size == 0:
        raise ValueError("SIS operator SVD failed.")
    rel_cut = float(max(0.0, pinv_rcond))
    tol = float(max(np.finfo(float).eps, rel_cut) * s[0])
    keep = s > tol
    if not np.any(keep):
        raise ValueError("Pseudo-inverse cutoff removed every singular value. Lower pinv rcond.")
    inv_s = np.zeros_like(s)
    inv_s[keep] = 1.0 / s[keep]
    pinv_weighted = (vh.T * inv_s) @ u.T
    pinv_op = pinv_weighted * sqrt_w[None, :]
    smallest = float(np.min(s[keep])) if np.any(keep) else np.nan
    condition = float(s[0] / smallest) if np.isfinite(smallest) and smallest > 0 else np.inf
    meta = {
        "pinv_rcond": rel_cut,
        "sv_max": float(s[0]),
        "sv_min_kept": float(smallest) if np.isfinite(smallest) else np.nan,
        "rank_kept": int(np.count_nonzero(keep)),
        "rank_total": int(s.size),
        "condition_kept": float(condition),
        "weighting": dict(weight_meta),
    }
    return np.asarray(pinv_op, dtype=float), meta


def _default_zero_exclusion_region(v_bias: Sequence[float], floor_mV: float = 0.12) -> list[float]:
    vv = np.asarray(v_bias, dtype=float).ravel()
    step = median_bias_step(vv)
    half_width = float(max(float(floor_mV), 3.0 * step if np.isfinite(step) and step > 0 else 0.0))
    max_abs = float(np.nanmax(np.abs(vv))) if vv.size else half_width
    if np.isfinite(max_abs) and max_abs > 0:
        half_width = min(half_width, 0.25 * max_abs)
    return [-half_width, half_width]


def _solve_trace_from_matrix(
    matrix: np.ndarray,
    measured: np.ndarray,
    bias_grid: np.ndarray,
    display_grid: np.ndarray,
    *,
    pinv_rcond: float,
    exclude_region: tuple[float, float] | None,
    dos_broad_sigma_mV: float,
) -> dict[str, Any]:
    mask = np.isfinite(measured)
    if exclude_region is not None:
        a, b = sorted([float(exclude_region[0]), float(exclude_region[1])])
        mask &= ~((bias_grid >= a) & (bias_grid <= b))
    if np.count_nonzero(mask) < max(9, min(31, matrix.shape[1] // 10)):
        raise ValueError("Too few points remain after zero-bias exclusion for SIS deconvolution.")
    rho_s_solve, pinv_meta = solve_sis_sample_dos(matrix[mask, :], measured[mask], pinv_rcond=pinv_rcond)
    rho_s_display_raw = resample_trace(bias_grid, rho_s_solve, display_grid, extrapolation="linear")
    rho_s_broad = gaussian_broaden_uniform_trace(bias_grid, rho_s_solve, float(max(0.0, dos_broad_sigma_mV)))
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        didv_fit_solve = matrix @ rho_s_broad
    rho_display = resample_trace(bias_grid, rho_s_broad, display_grid, extrapolation="linear")
    rho_norm, norm_meta = normalize_sample_dos_display(display_grid, rho_display)
    norm_scale = float(norm_meta.get("scale", 1.0))
    if (not np.isfinite(norm_scale)) or abs(norm_scale) <= 1e-18:
        norm_scale = 1.0
    rho_s_display_raw_norm = rho_s_display_raw / norm_scale
    didv_fit_display = resample_trace(bias_grid, didv_fit_solve, display_grid, extrapolation="linear")
    measured_display = resample_trace(bias_grid, measured, display_grid, extrapolation="linear")
    residual = measured_display - didv_fit_display
    r2 = np.nan
    if np.any(mask):
        ss_res = float(np.sum((measured[mask] - didv_fit_solve[mask]) ** 2))
        ss_tot = float(np.sum((measured[mask] - float(np.mean(measured[mask]))) ** 2))
        if ss_tot > 0:
            r2 = 1.0 - ss_res / ss_tot
    return {
        "rho_s_solve": rho_s_solve,
        "rho_s_display_raw": rho_s_display_raw,
        "rho_s_display_raw_norm": rho_s_display_raw_norm,
        "rho_s": rho_norm,
        "rho_s_broadened_raw": rho_display,
        "didv_fit": didv_fit_display,
        "didv_meas_common": measured_display,
        "residual": residual,
        "r2": float(r2) if np.isfinite(r2) else np.nan,
        "pinv_meta": pinv_meta,
        "rho_norm_meta": norm_meta,
        "solve_mask": mask,
        "exclude_region": None if exclude_region is None else [float(min(exclude_region)), float(max(exclude_region))],
        "dos_broad_sigma_mV": float(max(0.0, dos_broad_sigma_mV)),
    }


def run_sis_didv_deconvolution(
    meas_bias: Sequence[float],
    meas_didv: Sequence[float],
    tip_bias: Sequence[float] | None = None,
    tip_didv: Sequence[float] | None = None,
    *,
    n_grid: Optional[int] = None,
    temperature_K: float = 0.3,
    tip_delta_meV: Optional[float] = DEFAULT_TIP_DELTA_MEV,
    tip_gamma_meV: Optional[float] = DEFAULT_TIP_GAMMA_MEV,
    dos_broad_sigma_mV: float = DEFAULT_DOS_BROAD_SIGMA_MV,
    symmetrize_measured: bool = True,
    symmetrize_tip: bool = True,
    pinv_rcond: float = 1e-2,
    zero_peak_region: tuple[float, float] | None = None,
    target_abs_max: Optional[float] = None,
) -> dict[str, Any]:
    grids = build_paper_sis_grids(meas_bias, n_grid=n_grid, target_abs_max=target_abs_max)
    v_display = np.asarray(grids["display_grid"], dtype=float)
    v_solve = np.asarray(grids["solve_grid"], dtype=float)
    meas = prepare_measured_trace(meas_bias, meas_didv, display_grid=v_display, solve_grid=v_solve, symmetrize_measured=symmetrize_measured)
    if zero_peak_region is None:
        zero_peak_region = tuple(_default_zero_exclusion_region(meas["meas_used_bias"]))  # type: ignore[assignment]
    delta_tip = float(DEFAULT_TIP_DELTA_MEV if tip_delta_meV is None else tip_delta_meV)
    gamma_tip = float(DEFAULT_TIP_GAMMA_MEV if tip_gamma_meV is None else tip_gamma_meV)
    if tip_bias is not None and tip_didv is not None and tip_delta_meV is None:
        fit = fit_sis_dynes_didv(tip_bias, tip_didv, temperature_K=temperature_K, gaussian_sigma_mV=DEFAULT_TIP_FIT_GAUSSIAN_SIGMA_MV, symmetrize=symmetrize_tip)
        delta_tip = float(fit["delta_meV"])
        gamma_tip = float(fit["gamma_meV"])
        tip_source = "tip_line_fit"
    else:
        tip_source = "manual"
    solve_abs = float(np.nanmax(np.abs(v_solve)))
    step = median_bias_step(v_solve)
    tip_support_abs = float(max(2.0 * solve_abs, 4.0 * max(delta_tip, 0.5)))
    n_support = ensure_odd_grid_size(int(np.round((2.0 * tip_support_abs) / max(step, 1e-12))) + 1, minimum=max(9, len(v_solve)))
    tip_support_bias = np.linspace(-tip_support_abs, tip_support_abs, n_support, dtype=float)
    rho_tip = dynes_dos(tip_support_bias, delta_tip, max(gamma_tip, _dynes_gamma_floor(v_solve, gaussian_sigma_mV=DEFAULT_TIP_FIT_GAUSSIAN_SIGMA_MV)))
    matrix = build_sis_didv_matrix(v_solve, v_solve, tip_support_bias, rho_tip, temperature_K)
    solved = _solve_trace_from_matrix(
        matrix,
        np.asarray(meas["didv_solve_used"], dtype=float),
        v_solve,
        v_display,
        pinv_rcond=pinv_rcond,
        exclude_region=zero_peak_region,
        dos_broad_sigma_mV=dos_broad_sigma_mV,
    )
    return {
        "v_common": v_display,
        "v_solve": v_solve,
        "sample_dos": np.asarray(solved["rho_s"], dtype=float),
        "sample_dos_solve": np.asarray(solved["rho_s_solve"], dtype=float),
        "sample_dos_raw_norm": np.asarray(solved["rho_s_display_raw_norm"], dtype=float),
        "sample_dos_raw": np.asarray(solved["rho_s_broadened_raw"], dtype=float),
        "reconvolved_didv": np.asarray(solved["didv_fit"], dtype=float),
        "measured_didv": np.asarray(solved["didv_meas_common"], dtype=float),
        "residual": np.asarray(solved["residual"], dtype=float),
        "r2": float(solved["r2"]) if np.isfinite(solved["r2"]) else np.nan,
        "didv_matrix_solve": matrix,
        "rho_tip_support": rho_tip,
        "tip_support_bias": tip_support_bias,
        "tip_delta_meV": delta_tip,
        "tip_gamma_meV": gamma_tip,
        "tip_source": tip_source,
        "temperature_K": float(max(0.0, temperature_K)),
        "pinv_meta": dict(solved["pinv_meta"]),
        "rho_norm_meta": dict(solved["rho_norm_meta"]),
        "solve_mask": np.asarray(solved["solve_mask"], dtype=bool),
        "zero_peak_exclude_region": [float(min(zero_peak_region)), float(max(zero_peak_region))] if zero_peak_region is not None else None,
        "algorithm": {
            "name": "AnalySTM SIS dI/dV deconvolution",
            "engine": "analystm.deconvolution.run_sis_didv_deconvolution",
            "pysidam_source_mapping": "fit_sis_dynes_didv, build_sis_didv_matrix, solve_sis_sample_dos, run_sis_didv_deconvolution",
            "pysidam_mapping": "fit_sis_dynes_didv, build_sis_didv_matrix, solve_sis_sample_dos, run_sis_didv_deconvolution",
        },
    }


def run_grid_deconvolution(
    meas_bias: Sequence[float],
    didv_cube: Any,
    **kwargs,
) -> dict[str, Any]:
    arr = np.asarray(didv_cube, dtype=float)
    bias = np.asarray(meas_bias, dtype=float).ravel()
    if arr.ndim != 3:
        raise ValueError("grid deconvolution expects a 3D cube")
    if arr.shape[-1] == bias.size:
        cube = arr
    elif arr.shape[0] == bias.size:
        cube = np.moveaxis(arr, 0, -1)
    else:
        raise ValueError("could not identify bias axis in deconvolution cube")
    h, w, _ = cube.shape
    first = run_sis_didv_deconvolution(bias, cube[0, 0, :], **kwargs)
    n = np.asarray(first["sample_dos"]).size
    sample = np.full((h, w, n), np.nan, dtype=float)
    r2_map = np.full((h, w), np.nan, dtype=float)
    status = np.zeros((h, w), dtype=np.int16)
    sample[0, 0, :] = first["sample_dos"]
    r2_map[0, 0] = first["r2"]
    for y in range(h):
        for x in range(w):
            if y == 0 and x == 0:
                continue
            try:
                out = run_sis_didv_deconvolution(bias, cube[y, x, :], **kwargs)
                sample[y, x, :] = out["sample_dos"]
                r2_map[y, x] = out["r2"]
            except Exception:
                status[y, x] = 1
    return {
        "v_common": first["v_common"],
        "sample_dos_cube": sample,
        "r2_map": r2_map,
        "status_map": status,
        "algorithm": {
            "name": "AnalySTM grid SIS deconvolution",
            "engine": "analystm.deconvolution.run_grid_deconvolution",
            "pysidam_source_mapping": "grid deconvolution loop over run_sis_didv_deconvolution",
            "pysidam_mapping": "grid deconvolution loop over run_sis_didv_deconvolution",
        },
    }
