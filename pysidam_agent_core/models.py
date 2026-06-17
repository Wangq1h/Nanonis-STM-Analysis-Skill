from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from pysidam.core.superconducting_gap_models import (
    DEFAULT_FESE_MODEL_THETA_COUNT,
    DEFAULT_SHARED_DYNES_GAMMA_MEV,
    GAP_MODEL_NAMES,
    MODEL_ANISOTROPIC_S,
    MODEL_D_WAVE,
    MODEL_ISOTROPIC_S,
    MODEL_S_PLUS_D,
    MODEL_THREE_BAND_S,
    MODEL_TWO_BAND_ANISOTROPIC_FESE,
    MODEL_TWO_BAND_ANISOTROPIC_S,
    MODEL_TWO_BAND_ANISOTROPIC_S_INGAP,
    MODEL_TWO_BAND_S,
    MODEL_TWO_BAND_S_INGAP,
    build_gap_model_summary_params,
    evaluate_gap_dos_model,
    get_deconvolution_fit_param_spec,
    map_deconvolution_fit_values,
    normalize_gap_model_name,
    normalize_three_band_weights,
    order_fese_parameters,
)

DEFAULT_PAPER_DOS_BROAD_SIGMA_MV = 0.17
DEFAULT_DOS_FIT_TIME_BUDGET_S = 10.0
DOS_FIT_STRATEGY_PAPER = "paper_curve_fit"
DOS_FIT_STRATEGY_MULTISTART_WEIGHTED = "multistart_weighted"
DEFAULT_FESE_HOLE_GAP_MEV = 2.4
DEFAULT_FESE_ELECTRON_GAP_MEV = 1.68
DEFAULT_FESE_HOLE_P = 0.192
DEFAULT_FESE_ELECTRON_P = 0.284
DEFAULT_FESE_HOLE_WEIGHT = 0.5
DEFAULT_FESE_DYNES_GAMMA_MEV = DEFAULT_SHARED_DYNES_GAMMA_MEV
FESE_MODEL_THETA_COUNT = DEFAULT_FESE_MODEL_THETA_COUNT
FESE_MODEL_FIT_GRID_MAX = 201


def model_param_specs(model_name: str) -> list[dict[str, Any]]:
    return [dict(item) for item in get_deconvolution_fit_param_spec(model_name)]


def evaluate_gap_model_raw(
    energy_meV: Sequence[float],
    model_name: str,
    param_values: dict[str, float],
    *,
    gaussian_sigma_mV: float = DEFAULT_PAPER_DOS_BROAD_SIGMA_MV,
    gamma_meV: float = DEFAULT_FESE_DYNES_GAMMA_MEV,
    theta_count: int = FESE_MODEL_THETA_COUNT,
    apply_gaussian_broadening: bool = False,
):
    from .numerics import gaussian_broaden_uniform_trace

    model = normalize_gap_model_name(model_name)
    ee = np.asarray(energy_meV, dtype=float)
    values = dict(param_values or {})
    gamma_eval = float(max(0.0, values.get("gamma_meV", gamma_meV)))
    if model == MODEL_ISOTROPIC_S:
        rho = evaluate_gap_dos_model(
            ee,
            model,
            values.get("delta_meV", DEFAULT_FESE_HOLE_GAP_MEV),
            gamma_eval,
            theta_count=theta_count,
        )
    elif model == MODEL_D_WAVE:
        rho = evaluate_gap_dos_model(
            ee,
            model,
            values.get("delta_meV", DEFAULT_FESE_HOLE_GAP_MEV),
            gamma_eval,
            theta_count=theta_count,
        )
    elif model == MODEL_ANISOTROPIC_S:
        rho = evaluate_gap_dos_model(
            ee,
            model,
            values.get("delta_max_meV", DEFAULT_FESE_HOLE_GAP_MEV),
            gamma_eval,
            alpha=values.get("alpha", 0.25),
            theta_count=theta_count,
        )
    elif model == MODEL_TWO_BAND_S:
        rho = evaluate_gap_dos_model(
            ee,
            model,
            values.get("delta1_meV", DEFAULT_FESE_HOLE_GAP_MEV),
            gamma_eval,
            delta2_meV=values.get("delta2_meV", DEFAULT_FESE_ELECTRON_GAP_MEV),
            gamma2_meV=gamma_eval,
            weight=values.get("weight", 0.5),
            theta_count=theta_count,
        )
    elif model == MODEL_TWO_BAND_S_INGAP:
        rho = evaluate_gap_dos_model(
            ee,
            model,
            values.get("delta1_meV", DEFAULT_FESE_HOLE_GAP_MEV),
            values.get("gamma1_meV", gamma_eval),
            delta2_meV=values.get("delta2_meV", DEFAULT_FESE_ELECTRON_GAP_MEV),
            gamma2_meV=values.get("gamma2_meV", gamma_eval),
            weight=values.get("weight", 0.5),
            theta_count=theta_count,
            delta3_meV=values.get("ingap_energy_meV", 0.25),
            gamma3_meV=values.get("ingap_gamma_meV", 0.05),
            weight2=values.get("ingap_amp", 0.15),
        )
    elif model == MODEL_TWO_BAND_ANISOTROPIC_S:
        rho = evaluate_gap_dos_model(
            ee,
            model,
            values.get("delta1_meV", DEFAULT_FESE_HOLE_GAP_MEV),
            gamma_eval,
            delta2_meV=values.get("delta2_meV", DEFAULT_FESE_ELECTRON_GAP_MEV),
            gamma2_meV=gamma_eval,
            weight=values.get("weight", 0.5),
            alpha=values.get("alpha1", 0.20),
            alpha2=values.get("alpha2", 0.20),
            theta_count=theta_count,
        )
    elif model == MODEL_TWO_BAND_ANISOTROPIC_S_INGAP:
        rho = evaluate_gap_dos_model(
            ee,
            model,
            values.get("delta1_meV", DEFAULT_FESE_HOLE_GAP_MEV),
            values.get("gamma1_meV", gamma_eval),
            delta2_meV=values.get("delta2_meV", DEFAULT_FESE_ELECTRON_GAP_MEV),
            gamma2_meV=values.get("gamma2_meV", gamma_eval),
            weight=values.get("weight", 0.5),
            alpha=values.get("alpha1", 0.20),
            alpha2=values.get("alpha2", 0.20),
            theta_count=theta_count,
            delta3_meV=values.get("ingap_energy_meV", 0.25),
            gamma3_meV=values.get("ingap_gamma_meV", 0.05),
            weight2=values.get("ingap_amp", 0.15),
        )
    elif model == MODEL_THREE_BAND_S:
        rho = evaluate_gap_dos_model(
            ee,
            model,
            values.get("delta1_meV", DEFAULT_FESE_HOLE_GAP_MEV),
            values.get("gamma1_meV", gamma_eval),
            delta2_meV=values.get("delta2_meV", DEFAULT_FESE_ELECTRON_GAP_MEV),
            gamma2_meV=values.get("gamma2_meV", gamma_eval),
            theta_count=theta_count,
            delta3_meV=values.get("delta3_meV", max(0.1, 0.5 * DEFAULT_FESE_ELECTRON_GAP_MEV)),
            gamma3_meV=values.get("gamma3_meV", gamma_eval),
            weight=values.get("weight1", values.get("weight", 0.40)),
            weight2=values.get("weight2", 0.35),
        )
    elif model == MODEL_S_PLUS_D:
        rho = evaluate_gap_dos_model(
            ee,
            model,
            values.get("delta_s_meV", DEFAULT_FESE_HOLE_GAP_MEV),
            gamma_eval,
            delta2_meV=values.get("delta_d_meV", DEFAULT_FESE_ELECTRON_GAP_MEV),
            gamma2_meV=gamma_eval,
            weight=values.get("weight", 0.5),
            theta_count=theta_count,
        )
    else:
        delta_h, delta_e, p_h, p_e, w_h = order_fese_parameters(
            values.get("delta_hole_meV", DEFAULT_FESE_HOLE_GAP_MEV),
            values.get("delta_electron_meV", DEFAULT_FESE_ELECTRON_GAP_MEV),
            values.get("p_hole", DEFAULT_FESE_HOLE_P),
            values.get("p_electron", DEFAULT_FESE_ELECTRON_P),
            values.get("hole_weight", DEFAULT_FESE_HOLE_WEIGHT),
        )
        values.update(
            {
                "delta_hole_meV": delta_h,
                "delta_electron_meV": delta_e,
                "p_hole": p_h,
                "p_electron": p_e,
                "hole_weight": w_h,
            }
        )
        rho = evaluate_gap_dos_model(
            ee,
            MODEL_TWO_BAND_ANISOTROPIC_FESE,
            delta_h,
            gamma_eval,
            delta2_meV=delta_e,
            gamma2_meV=gamma_eval,
            weight=w_h,
            alpha=p_h,
            alpha2=p_e,
            theta_count=theta_count,
        )

    out = np.asarray(rho, dtype=float)
    if bool(apply_gaussian_broadening) and float(max(0.0, gaussian_sigma_mV)) > 0:
        out = gaussian_broaden_uniform_trace(ee, out, float(max(0.0, gaussian_sigma_mV)))
    return np.asarray(out, dtype=float)
