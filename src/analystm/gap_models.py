import numpy as np
from typing import Dict, List, Sequence, Tuple

MODEL_ISOTROPIC_S = "Isotropic s-wave (Single)"
MODEL_D_WAVE = "d-wave (Single)"
MODEL_ANISOTROPIC_S = "Anisotropic s-wave (Single)"
MODEL_TWO_BAND_S = "Two Band s-wave"
MODEL_TWO_BAND_S_INGAP = "Two Band s-wave + In-gap peak"
MODEL_THREE_BAND_S = "Three Band s-wave"
MODEL_TWO_BAND_ANISOTROPIC_S = "Two Band Anisotropic s-wave"
MODEL_TWO_BAND_ANISOTROPIC_S_INGAP = "Two Band Anisotropic s-wave + In-gap peak"
MODEL_S_PLUS_D = "s-wave + d-wave"
MODEL_TWO_BAND_ANISOTROPIC_FESE = "Two Band Anisotropic s-wave (FeSe)"

GAP_MODEL_NAMES = [
    MODEL_ISOTROPIC_S,
    MODEL_D_WAVE,
    MODEL_ANISOTROPIC_S,
    MODEL_TWO_BAND_S,
    MODEL_TWO_BAND_S_INGAP,
    MODEL_S_PLUS_D,
    MODEL_TWO_BAND_ANISOTROPIC_S,
    MODEL_TWO_BAND_ANISOTROPIC_S_INGAP,
    MODEL_TWO_BAND_ANISOTROPIC_FESE,
    MODEL_THREE_BAND_S,
]

DEFAULT_SHARED_DYNES_GAMMA_MEV = 0.01
DEFAULT_GAP_MODEL_THETA_COUNT = 91
DEFAULT_FESE_MODEL_THETA_COUNT = 361


def _append_gamma_fit_param(specs: List[Dict[str, float]]) -> List[Dict[str, float]]:
    out = [dict(item) for item in specs]
    out.append(
        {
            "key": "gamma_meV",
            "label": "Γ",
            "unit": "meV",
            "initial": DEFAULT_SHARED_DYNES_GAMMA_MEV,
            "lower": 0.0,
            "upper": 2.0,
        }
    )
    return out


def normalize_gap_model_name(model_name: str) -> str:
    text = str(model_name or "").strip()
    for item in GAP_MODEL_NAMES:
        if text == item:
            return item
    low = text.lower()
    aliases = {
        "isotropic s-wave": MODEL_ISOTROPIC_S,
        "d-wave": MODEL_D_WAVE,
        "anisotropic s-wave": MODEL_ANISOTROPIC_S,
        "two band s-wave": MODEL_TWO_BAND_S,
        "two band s-wave + in-gap peak": MODEL_TWO_BAND_S_INGAP,
        "two band s-wave + ingap peak": MODEL_TWO_BAND_S_INGAP,
        "two band + in-gap peak": MODEL_TWO_BAND_S_INGAP,
        "two band + ingap": MODEL_TWO_BAND_S_INGAP,
        "ingap": MODEL_TWO_BAND_S_INGAP,
        "three band s-wave": MODEL_THREE_BAND_S,
        "three gap s-wave": MODEL_THREE_BAND_S,
        "3 gap s-wave": MODEL_THREE_BAND_S,
        "3gap s-wave": MODEL_THREE_BAND_S,
        "3gap": MODEL_THREE_BAND_S,
        "two band anisotropic s-wave": MODEL_TWO_BAND_ANISOTROPIC_S,
        "two band anisotropic s-wave (generic)": MODEL_TWO_BAND_ANISOTROPIC_S,
        "two band anisotropic s-wave + in-gap peak": MODEL_TWO_BAND_ANISOTROPIC_S_INGAP,
        "two band anisotropic s-wave + ingap peak": MODEL_TWO_BAND_ANISOTROPIC_S_INGAP,
        "two band anisotropic + in-gap peak": MODEL_TWO_BAND_ANISOTROPIC_S_INGAP,
        "two band anisotropic + ingap": MODEL_TWO_BAND_ANISOTROPIC_S_INGAP,
        "anisotropic in-gap": MODEL_TWO_BAND_ANISOTROPIC_S_INGAP,
        "anisotropic ingap": MODEL_TWO_BAND_ANISOTROPIC_S_INGAP,
        "s-wave + d-wave": MODEL_S_PLUS_D,
        "two band anisotropic s-wave (fese)": MODEL_TWO_BAND_ANISOTROPIC_FESE,
        "fese": MODEL_TWO_BAND_ANISOTROPIC_FESE,
    }
    for key, value in aliases.items():
        if low == key:
            return value
    return text


def get_gap_model_tooltip(model_name: str) -> str:
    model = normalize_gap_model_name(model_name)
    tips = {
        MODEL_ISOTROPIC_S: (
            "<b>Isotropic s-wave:</b><br>"
            "Δ(θ) = Δ<br>"
            "N(E) = Re((E-iΓ)/√((E-iΓ)² - Δ²))"
        ),
        MODEL_D_WAVE: (
            "<b>d-wave:</b><br>"
            "Δ(θ) = Δ cos(2θ)<br>"
            "N(E) = ⟨Re((E-iΓ)/√((E-iΓ)² - Δ(θ)²))⟩θ"
        ),
        MODEL_ANISOTROPIC_S: (
            "<b>Anisotropic s-wave:</b><br>"
            "Δ(θ) = Δ (1 + α cos(4θ))<br>"
            "N(E) = ⟨Re((E-iΓ)/√((E-iΓ)² - Δ(θ)²))⟩θ"
        ),
        MODEL_TWO_BAND_S: (
            "<b>Two Band s-wave:</b><br>"
            "Ntotal = w·N(Δ1,Γ1) + (1-w)·N(Δ2,Γ2)<br>"
            "(Linear sum of two isotropic s-wave DOS)"
        ),
        MODEL_TWO_BAND_S_INGAP: (
            "<b>Two Band s-wave + In-gap peak:</b><br>"
            "Ntotal = w·N(Δ1,Γ1) + (1-w)·N(Δ2,Γ2) + Aig·[L(E-Eig,γig)+L(E+Eig,γig)]<br>"
            "Use for symmetric in-gap resonance peaks without pulling the coherence peaks inward."
        ),
        MODEL_THREE_BAND_S: (
            "<b>Three Band s-wave:</b><br>"
            "Ntotal = w1·N(Δ1,Γ1) + w2·N(Δ2,Γ2) + w3·N(Δ3,Γ3)<br>"
            "w3 = 1 - w1 - w2, with non-negative normalized weights"
        ),
        MODEL_TWO_BAND_ANISOTROPIC_S: (
            "<b>Two Band Anisotropic s-wave:</b><br>"
            "Δ1(θ) = Δ1 (1 + α1 cos4θ)<br>"
            "Δ2(θ) = Δ2 (1 + α2 cos4θ)<br>"
            "Ntotal = w·N1 + (1-w)·N2"
        ),
        MODEL_TWO_BAND_ANISOTROPIC_S_INGAP: (
            "<b>Two Band Anisotropic s-wave + In-gap peak:</b><br>"
            "Δ1(θ) = Δ1 (1 + α1 cos4θ), Δ2(θ) = Δ2 (1 + α2 cos4θ)<br>"
            "Ntotal = w·N1 + (1-w)·N2 + Aig·[L(E-Eig,γig)+L(E+Eig,γig)]<br>"
            "Use when an anisotropic two-gap background also contains symmetric in-gap resonances."
        ),
        MODEL_S_PLUS_D: (
            "<b>s-wave + d-wave:</b><br>"
            "Ntotal = w·Ns(Δ1,Γ1) + (1-w)·Nd(Δ2,Γ2)<br>"
            "(Linear mixture of isotropic and nodal DOS)"
        ),
        MODEL_TWO_BAND_ANISOTROPIC_FESE: (
            "<b>Two Band Anisotropic s-wave (FeSe):</b><br>"
            "Δh(θ)=Δh,max[ph cos2θ + sh], sh=1-ph<br>"
            "Δe(θ)=Δe,max[pe cos2θ - se], se=1-pe<br>"
            "A(E)=y·Ah(E) + (1-y)·Ae(E)"
        ),
    }
    return tips.get(model, "")


def get_gap_model_formula_text(model_name: str) -> str:
    model = normalize_gap_model_name(model_name)
    details = {
        MODEL_ISOTROPIC_S: "DOS: N(E) ~ Re((E-iΓ)/√((E-iΓ)²-Δ²))",
        MODEL_D_WAVE: (
            "DOS: N(E) ~ ⟨Re((E-iΓ)/√((E-iΓ)²-Δ(θ)²))⟩θ\n"
            "         Δ(θ) = Δ·cos(2θ)"
        ),
        MODEL_ANISOTROPIC_S: (
            "DOS: N(E) ~ ⟨Re((E-iΓ)/√((E-iΓ)²-Δ(θ)²))⟩θ\n"
            "         Δ(θ) = Δ·(1+α·cos(4θ))"
        ),
        MODEL_TWO_BAND_S: (
            "DOS: Ntot = w·N(Δ1,Γ1) + (1-w)·N(Δ2,Γ2)\n"
            "         (Linear sum)"
        ),
        MODEL_TWO_BAND_S_INGAP: (
            "DOS: Ntot = w·N(Δ1,Γ1) + (1-w)·N(Δ2,Γ2)\n"
            "       + Aig·[L(E-Eig,γig)+L(E+Eig,γig)]\n"
            "         (Two superconducting bands plus symmetric in-gap resonance)"
        ),
        MODEL_THREE_BAND_S: (
            "DOS: Ntot = w1·N(Δ1,Γ1) + w2·N(Δ2,Γ2) + (1-w1-w2)·N(Δ3,Γ3)\n"
            "         (Three isotropic s-wave bands)"
        ),
        MODEL_TWO_BAND_ANISOTROPIC_S: (
            "DOS: Ntot = w·N1 + (1-w)·N2\n"
            "         Δ1(θ) = Δ1·(1+α1·cos4θ)\n"
            "         Δ2(θ) = Δ2·(1+α2·cos4θ)"
        ),
        MODEL_TWO_BAND_ANISOTROPIC_S_INGAP: (
            "DOS: Ntot = w·N1 + (1-w)·N2\n"
            "       + Aig·[L(E-Eig,γig)+L(E+Eig,γig)]\n"
            "         Δ1(θ) = Δ1·(1+α1·cos4θ)\n"
            "         Δ2(θ) = Δ2·(1+α2·cos4θ)"
        ),
        MODEL_S_PLUS_D: (
            "DOS: Ntot = w·Ns(Δ1,Γ1) + (1-w)·Nd(Δ2,Γ2)\n"
            "         (Mixed)"
        ),
        MODEL_TWO_BAND_ANISOTROPIC_FESE: (
            "DOS: A(E) = y·Ah(E) + (1-y)·Ae(E)\n"
            "         Δh(θ) = Δh,max·[ph·cos2θ + sh], sh = 1-ph\n"
            "         Δe(θ) = Δe,max·[pe·cos2θ - se], se = 1-pe"
        ),
    }
    return details.get(model, "")


def gap_model_is_two_band(model_name: str) -> bool:
    model = normalize_gap_model_name(model_name)
    return model in (
        MODEL_TWO_BAND_S,
        MODEL_TWO_BAND_S_INGAP,
        MODEL_THREE_BAND_S,
        MODEL_TWO_BAND_ANISOTROPIC_S,
        MODEL_TWO_BAND_ANISOTROPIC_S_INGAP,
        MODEL_S_PLUS_D,
        MODEL_TWO_BAND_ANISOTROPIC_FESE,
    )


def gap_model_uses_second_gap(model_name: str) -> bool:
    return gap_model_is_two_band(model_name)


def gap_model_uses_second_gamma(model_name: str) -> bool:
    model = normalize_gap_model_name(model_name)
    return model in (MODEL_TWO_BAND_S, MODEL_TWO_BAND_S_INGAP, MODEL_THREE_BAND_S, MODEL_TWO_BAND_ANISOTROPIC_S, MODEL_TWO_BAND_ANISOTROPIC_S_INGAP, MODEL_S_PLUS_D)


def gap_model_uses_third_gap(model_name: str) -> bool:
    model = normalize_gap_model_name(model_name)
    return model in (MODEL_THREE_BAND_S, MODEL_TWO_BAND_S_INGAP, MODEL_TWO_BAND_ANISOTROPIC_S_INGAP)


def gap_model_uses_third_gamma(model_name: str) -> bool:
    model = normalize_gap_model_name(model_name)
    return model in (MODEL_THREE_BAND_S, MODEL_TWO_BAND_S_INGAP, MODEL_TWO_BAND_ANISOTROPIC_S_INGAP)


def gap_model_uses_weight(model_name: str) -> bool:
    model = normalize_gap_model_name(model_name)
    return model in (MODEL_TWO_BAND_S, MODEL_TWO_BAND_S_INGAP, MODEL_THREE_BAND_S, MODEL_TWO_BAND_ANISOTROPIC_S, MODEL_TWO_BAND_ANISOTROPIC_S_INGAP, MODEL_S_PLUS_D, MODEL_TWO_BAND_ANISOTROPIC_FESE)


def gap_model_uses_alpha(model_name: str) -> bool:
    model = normalize_gap_model_name(model_name)
    return model in (MODEL_ANISOTROPIC_S, MODEL_TWO_BAND_ANISOTROPIC_S, MODEL_TWO_BAND_ANISOTROPIC_S_INGAP, MODEL_TWO_BAND_ANISOTROPIC_FESE)


def gap_model_uses_alpha2(model_name: str) -> bool:
    model = normalize_gap_model_name(model_name)
    return model in (MODEL_TWO_BAND_ANISOTROPIC_S, MODEL_TWO_BAND_ANISOTROPIC_S_INGAP, MODEL_TWO_BAND_ANISOTROPIC_FESE)


def get_dynes_fit_model_defaults(model_name: str) -> Dict[str, float]:
    model = normalize_gap_model_name(model_name)
    defaults = {
        "d1": 0.9,
        "g1": 0.14,
        "d2": 0.5,
        "g2": 0.1,
        "d3": 0.25,
        "g3": 0.1,
        "weight": 0.5,
        "weight2": 0.25,
        "alpha": 0.3,
        "alpha2": 0.2,
        "temp": 1.5,
        "amp": 1.0,
        "offset": 0.0,
    }
    if model == MODEL_TWO_BAND_ANISOTROPIC_S:
        defaults.update(
            {
                "d1": 2.4,
                "g1": 0.14,
                "d2": 1.68,
                "g2": 0.10,
                "weight": 0.5,
                "alpha": 0.20,
                "alpha2": 0.20,
                "temp": 1.5,
            }
        )
    if model == MODEL_THREE_BAND_S:
        defaults.update(
            {
                "d1": 2.4,
                "g1": 0.10,
                "d2": 1.6,
                "g2": 0.08,
                "d3": 0.8,
                "g3": 0.06,
                "weight": 0.40,
                "weight2": 0.35,
                "temp": 1.5,
            }
        )
    if model == MODEL_TWO_BAND_S_INGAP:
        defaults.update(
            {
                "d1": 2.4,
                "g1": 0.10,
                "d2": 1.6,
                "g2": 0.08,
                "d3": 0.25,
                "g3": 0.05,
                "weight": 0.50,
                "weight2": 0.15,
                "temp": 1.5,
            }
        )
    if model == MODEL_TWO_BAND_ANISOTROPIC_S_INGAP:
        defaults.update(
            {
                "d1": 2.4,
                "g1": 0.10,
                "d2": 1.6,
                "g2": 0.08,
                "d3": 0.25,
                "g3": 0.05,
                "weight": 0.50,
                "weight2": 0.15,
                "alpha": 0.20,
                "alpha2": 0.20,
                "temp": 1.5,
            }
        )
    if model == MODEL_TWO_BAND_ANISOTROPIC_FESE:
        defaults.update(
            {
                "d1": 2.4,
                "g1": DEFAULT_SHARED_DYNES_GAMMA_MEV,
                "d2": 1.68,
                "g2": DEFAULT_SHARED_DYNES_GAMMA_MEV,
                "weight": 0.5,
                "alpha": 0.192,
                "alpha2": 0.284,
                "temp": 0.3,
            }
        )
    return defaults


def get_deconvolution_fit_param_spec(model_name: str) -> List[Dict[str, float]]:
    model = normalize_gap_model_name(model_name)
    if model == MODEL_ISOTROPIC_S:
        return _append_gamma_fit_param([
            {"key": "delta_meV", "label": "Δ", "unit": "meV", "initial": 2.0, "lower": 0.1, "upper": 8.0},
        ])
    if model == MODEL_D_WAVE:
        return _append_gamma_fit_param([
            {"key": "delta_meV", "label": "Δ", "unit": "meV", "initial": 2.0, "lower": 0.1, "upper": 8.0},
        ])
    if model == MODEL_ANISOTROPIC_S:
        return _append_gamma_fit_param([
            {"key": "delta_max_meV", "label": "Δmax", "unit": "meV", "initial": 2.0, "lower": 0.1, "upper": 8.0},
            {"key": "alpha", "label": "α", "unit": "", "initial": 0.25, "lower": 0.0, "upper": 1.0},
        ])
    if model == MODEL_TWO_BAND_S:
        return _append_gamma_fit_param([
            {"key": "delta1_meV", "label": "Δ1", "unit": "meV", "initial": 2.4, "lower": 0.1, "upper": 8.0},
            {"key": "delta2_meV", "label": "Δ2", "unit": "meV", "initial": 1.68, "lower": 0.1, "upper": 8.0},
            {"key": "weight", "label": "w", "unit": "", "initial": 0.5, "lower": 0.0, "upper": 1.0},
        ])
    if model == MODEL_THREE_BAND_S:
        return [
            {"key": "delta1_meV", "label": "Δ1", "unit": "meV", "initial": 2.4, "lower": 0.1, "upper": 8.0},
            {"key": "gamma1_meV", "label": "Γ1", "unit": "meV", "initial": DEFAULT_SHARED_DYNES_GAMMA_MEV, "lower": 0.0, "upper": 2.0},
            {"key": "delta2_meV", "label": "Δ2", "unit": "meV", "initial": 1.6, "lower": 0.1, "upper": 8.0},
            {"key": "gamma2_meV", "label": "Γ2", "unit": "meV", "initial": DEFAULT_SHARED_DYNES_GAMMA_MEV, "lower": 0.0, "upper": 2.0},
            {"key": "delta3_meV", "label": "Δ3", "unit": "meV", "initial": 0.8, "lower": 0.1, "upper": 8.0},
            {"key": "gamma3_meV", "label": "Γ3", "unit": "meV", "initial": DEFAULT_SHARED_DYNES_GAMMA_MEV, "lower": 0.0, "upper": 2.0},
            {"key": "weight1", "label": "w1", "unit": "", "initial": 0.40, "lower": 0.0, "upper": 1.0},
            {"key": "weight2", "label": "w2", "unit": "", "initial": 0.35, "lower": 0.0, "upper": 1.0},
        ]
    if model == MODEL_TWO_BAND_S_INGAP:
        return [
            {"key": "delta1_meV", "label": "Δ1", "unit": "meV", "initial": 2.4, "lower": 0.1, "upper": 8.0},
            {"key": "gamma1_meV", "label": "Γ1", "unit": "meV", "initial": DEFAULT_SHARED_DYNES_GAMMA_MEV, "lower": 0.0, "upper": 2.0},
            {"key": "delta2_meV", "label": "Δ2", "unit": "meV", "initial": 1.6, "lower": 0.1, "upper": 8.0},
            {"key": "gamma2_meV", "label": "Γ2", "unit": "meV", "initial": DEFAULT_SHARED_DYNES_GAMMA_MEV, "lower": 0.0, "upper": 2.0},
            {"key": "weight", "label": "w1", "unit": "", "initial": 0.5, "lower": 0.0, "upper": 1.0},
            {"key": "ingap_energy_meV", "label": "Eig", "unit": "meV", "initial": 0.25, "lower": 0.0, "upper": 3.0},
            {"key": "ingap_gamma_meV", "label": "γig", "unit": "meV", "initial": 0.05, "lower": 0.001, "upper": 2.0},
            {"key": "ingap_amp", "label": "Aig", "unit": "", "initial": 0.15, "lower": 0.0, "upper": 5.0},
        ]
    if model == MODEL_TWO_BAND_ANISOTROPIC_S:
        return _append_gamma_fit_param([
            {"key": "delta1_meV", "label": "Δ1,max", "unit": "meV", "initial": 2.4, "lower": 0.1, "upper": 8.0},
            {"key": "delta2_meV", "label": "Δ2,max", "unit": "meV", "initial": 1.68, "lower": 0.1, "upper": 8.0},
            {"key": "alpha1", "label": "α1", "unit": "", "initial": 0.20, "lower": 0.0, "upper": 1.0},
            {"key": "alpha2", "label": "α2", "unit": "", "initial": 0.20, "lower": 0.0, "upper": 1.0},
            {"key": "weight", "label": "w", "unit": "", "initial": 0.5, "lower": 0.0, "upper": 1.0},
        ])
    if model == MODEL_TWO_BAND_ANISOTROPIC_S_INGAP:
        return [
            {"key": "delta1_meV", "label": "Δ1,max", "unit": "meV", "initial": 2.4, "lower": 0.1, "upper": 8.0},
            {"key": "gamma1_meV", "label": "Γ1", "unit": "meV", "initial": DEFAULT_SHARED_DYNES_GAMMA_MEV, "lower": 0.0, "upper": 2.0},
            {"key": "delta2_meV", "label": "Δ2,max", "unit": "meV", "initial": 1.6, "lower": 0.1, "upper": 8.0},
            {"key": "gamma2_meV", "label": "Γ2", "unit": "meV", "initial": DEFAULT_SHARED_DYNES_GAMMA_MEV, "lower": 0.0, "upper": 2.0},
            {"key": "weight", "label": "w1", "unit": "", "initial": 0.5, "lower": 0.0, "upper": 1.0},
            {"key": "alpha1", "label": "α1", "unit": "", "initial": 0.20, "lower": 0.0, "upper": 1.0},
            {"key": "alpha2", "label": "α2", "unit": "", "initial": 0.20, "lower": 0.0, "upper": 1.0},
            {"key": "ingap_energy_meV", "label": "Eig", "unit": "meV", "initial": 0.25, "lower": 0.0, "upper": 3.0},
            {"key": "ingap_gamma_meV", "label": "γig", "unit": "meV", "initial": 0.05, "lower": 0.001, "upper": 2.0},
            {"key": "ingap_amp", "label": "Aig", "unit": "", "initial": 0.15, "lower": 0.0, "upper": 5.0},
        ]
    if model == MODEL_S_PLUS_D:
        return _append_gamma_fit_param([
            {"key": "delta_s_meV", "label": "Δs", "unit": "meV", "initial": 2.4, "lower": 0.1, "upper": 8.0},
            {"key": "delta_d_meV", "label": "Δd", "unit": "meV", "initial": 1.68, "lower": 0.1, "upper": 8.0},
            {"key": "weight", "label": "w", "unit": "", "initial": 0.5, "lower": 0.0, "upper": 1.0},
        ])
    if model == MODEL_TWO_BAND_ANISOTROPIC_FESE:
        return _append_gamma_fit_param([
            {"key": "delta_hole_meV", "label": "Δh,max", "unit": "meV", "initial": 2.4, "lower": 0.2, "upper": 8.0},
            {"key": "delta_electron_meV", "label": "Δe,max", "unit": "meV", "initial": 1.68, "lower": 0.1, "upper": 8.0},
            {"key": "p_hole", "label": "ph", "unit": "", "initial": 0.192, "lower": 0.0, "upper": 0.49},
            {"key": "p_electron", "label": "pe", "unit": "", "initial": 0.284, "lower": 0.0, "upper": 0.49},
            {"key": "hole_weight", "label": "y", "unit": "", "initial": 0.5, "lower": 0.0, "upper": 1.0},
        ])
    return []


def map_deconvolution_fit_values(model_name: str, params: Sequence[float]) -> Dict[str, float]:
    specs = get_deconvolution_fit_param_spec(model_name)
    values = [float(v) for v in params]
    out = {spec["key"]: values[i] for i, spec in enumerate(specs) if i < len(values)}
    if normalize_gap_model_name(model_name) == MODEL_THREE_BAND_S:
        w1, w2, w3 = normalize_three_band_weights(out.get("weight1", 0.4), out.get("weight2", 0.35))
        out["weight1"] = w1
        out["weight2"] = w2
        out["weight3"] = w3
    return out


def build_gap_model_summary_params(model_name: str, param_values: Dict[str, float]) -> List[Dict[str, float]]:
    model = normalize_gap_model_name(model_name)
    params: List[Dict[str, float]] = []
    if model == MODEL_ISOTROPIC_S:
        params.append({"key": "delta_meV", "label": "Δ", "value": float(param_values.get("delta_meV", np.nan)), "unit": "meV"})
    elif model == MODEL_D_WAVE:
        params.append({"key": "delta_meV", "label": "Δ", "value": float(param_values.get("delta_meV", np.nan)), "unit": "meV"})
    elif model == MODEL_ANISOTROPIC_S:
        params.extend(
            [
                {"key": "delta_max_meV", "label": "Δmax", "value": float(param_values.get("delta_max_meV", np.nan)), "unit": "meV"},
                {"key": "alpha", "label": "α", "value": float(param_values.get("alpha", np.nan)), "unit": ""},
            ]
        )
    elif model == MODEL_TWO_BAND_S:
        params.extend(
            [
                {"key": "delta1_meV", "label": "Δ1", "value": float(param_values.get("delta1_meV", np.nan)), "unit": "meV"},
                {"key": "delta2_meV", "label": "Δ2", "value": float(param_values.get("delta2_meV", np.nan)), "unit": "meV"},
                {"key": "weight", "label": "w", "value": float(param_values.get("weight", np.nan)), "unit": ""},
            ]
        )
    elif model == MODEL_THREE_BAND_S:
        w1, w2, w3 = normalize_three_band_weights(
            param_values.get("weight1", param_values.get("weight", np.nan)),
            param_values.get("weight2", np.nan),
        )
        params.extend(
            [
                {"key": "delta1_meV", "label": "Δ1", "value": float(param_values.get("delta1_meV", np.nan)), "unit": "meV"},
                {"key": "gamma1_meV", "label": "Γ1", "value": float(param_values.get("gamma1_meV", np.nan)), "unit": "meV"},
                {"key": "delta2_meV", "label": "Δ2", "value": float(param_values.get("delta2_meV", np.nan)), "unit": "meV"},
                {"key": "gamma2_meV", "label": "Γ2", "value": float(param_values.get("gamma2_meV", np.nan)), "unit": "meV"},
                {"key": "delta3_meV", "label": "Δ3", "value": float(param_values.get("delta3_meV", np.nan)), "unit": "meV"},
                {"key": "gamma3_meV", "label": "Γ3", "value": float(param_values.get("gamma3_meV", np.nan)), "unit": "meV"},
                {"key": "weight1", "label": "w1", "value": w1, "unit": ""},
                {"key": "weight2", "label": "w2", "value": w2, "unit": ""},
                {"key": "weight3", "label": "w3", "value": w3, "unit": ""},
            ]
        )
    elif model == MODEL_TWO_BAND_S_INGAP:
        params.extend(
            [
                {"key": "delta1_meV", "label": "Δ1", "value": float(param_values.get("delta1_meV", np.nan)), "unit": "meV"},
                {"key": "gamma1_meV", "label": "Γ1", "value": float(param_values.get("gamma1_meV", np.nan)), "unit": "meV"},
                {"key": "delta2_meV", "label": "Δ2", "value": float(param_values.get("delta2_meV", np.nan)), "unit": "meV"},
                {"key": "gamma2_meV", "label": "Γ2", "value": float(param_values.get("gamma2_meV", np.nan)), "unit": "meV"},
                {"key": "weight", "label": "w1", "value": float(param_values.get("weight", np.nan)), "unit": ""},
                {"key": "ingap_energy_meV", "label": "Eig", "value": float(param_values.get("ingap_energy_meV", np.nan)), "unit": "meV"},
                {"key": "ingap_gamma_meV", "label": "γig", "value": float(param_values.get("ingap_gamma_meV", np.nan)), "unit": "meV"},
                {"key": "ingap_amp", "label": "Aig", "value": float(param_values.get("ingap_amp", np.nan)), "unit": ""},
            ]
        )
    elif model == MODEL_TWO_BAND_ANISOTROPIC_S:
        params.extend(
            [
                {"key": "delta1_meV", "label": "Δ1,max", "value": float(param_values.get("delta1_meV", np.nan)), "unit": "meV"},
                {"key": "delta2_meV", "label": "Δ2,max", "value": float(param_values.get("delta2_meV", np.nan)), "unit": "meV"},
                {"key": "alpha1", "label": "α1", "value": float(param_values.get("alpha1", np.nan)), "unit": ""},
                {"key": "alpha2", "label": "α2", "value": float(param_values.get("alpha2", np.nan)), "unit": ""},
                {"key": "weight", "label": "w", "value": float(param_values.get("weight", np.nan)), "unit": ""},
            ]
        )
    elif model == MODEL_TWO_BAND_ANISOTROPIC_S_INGAP:
        params.extend(
            [
                {"key": "delta1_meV", "label": "Δ1,max", "value": float(param_values.get("delta1_meV", np.nan)), "unit": "meV"},
                {"key": "gamma1_meV", "label": "Γ1", "value": float(param_values.get("gamma1_meV", np.nan)), "unit": "meV"},
                {"key": "delta2_meV", "label": "Δ2,max", "value": float(param_values.get("delta2_meV", np.nan)), "unit": "meV"},
                {"key": "gamma2_meV", "label": "Γ2", "value": float(param_values.get("gamma2_meV", np.nan)), "unit": "meV"},
                {"key": "weight", "label": "w1", "value": float(param_values.get("weight", np.nan)), "unit": ""},
                {"key": "alpha1", "label": "α1", "value": float(param_values.get("alpha1", np.nan)), "unit": ""},
                {"key": "alpha2", "label": "α2", "value": float(param_values.get("alpha2", np.nan)), "unit": ""},
                {"key": "ingap_energy_meV", "label": "Eig", "value": float(param_values.get("ingap_energy_meV", np.nan)), "unit": "meV"},
                {"key": "ingap_gamma_meV", "label": "γig", "value": float(param_values.get("ingap_gamma_meV", np.nan)), "unit": "meV"},
                {"key": "ingap_amp", "label": "Aig", "value": float(param_values.get("ingap_amp", np.nan)), "unit": ""},
            ]
        )
    elif model == MODEL_S_PLUS_D:
        params.extend(
            [
                {"key": "delta_s_meV", "label": "Δs", "value": float(param_values.get("delta_s_meV", np.nan)), "unit": "meV"},
                {"key": "delta_d_meV", "label": "Δd", "value": float(param_values.get("delta_d_meV", np.nan)), "unit": "meV"},
                {"key": "weight", "label": "w", "value": float(param_values.get("weight", np.nan)), "unit": ""},
            ]
        )
    elif model == MODEL_TWO_BAND_ANISOTROPIC_FESE:
        p_h = float(param_values.get("p_hole", np.nan))
        p_e = float(param_values.get("p_electron", np.nan))
        params.extend(
            [
                {"key": "delta_hole_meV", "label": "Δh,max", "value": float(param_values.get("delta_hole_meV", np.nan)), "unit": "meV"},
                {"key": "delta_electron_meV", "label": "Δe,max", "value": float(param_values.get("delta_electron_meV", np.nan)), "unit": "meV"},
                {"key": "p_hole", "label": "ph", "value": p_h, "unit": ""},
                {"key": "p_electron", "label": "pe", "value": p_e, "unit": ""},
                {"key": "s_hole", "label": "sh", "value": (1.0 - p_h) if np.isfinite(p_h) else np.nan, "unit": ""},
                {"key": "s_electron", "label": "se", "value": (1.0 - p_e) if np.isfinite(p_e) else np.nan, "unit": ""},
                {"key": "hole_weight", "label": "y", "value": float(param_values.get("hole_weight", np.nan)), "unit": ""},
            ]
        )
    if model not in (MODEL_THREE_BAND_S, MODEL_TWO_BAND_S_INGAP, MODEL_TWO_BAND_ANISOTROPIC_S_INGAP):
        params.append({"key": "gamma_meV", "label": "Γ", "value": float(param_values.get("gamma_meV", np.nan)), "unit": "meV"})
    return params


def get_gap_visual_profiles(
    model_name: str,
    theta: np.ndarray,
    delta1: float,
    delta2: float = 0.0,
    alpha: float = 0.0,
    alpha2: float = 0.0,
    delta3: float = 0.0,
):
    model = normalize_gap_model_name(model_name)
    th = np.asarray(theta, dtype=float)
    if model == MODEL_ISOTROPIC_S:
        return [np.full_like(th, float(delta1), dtype=float)]
    if model == MODEL_D_WAVE:
        return [float(delta1) * np.cos(2.0 * th)]
    if model == MODEL_ANISOTROPIC_S:
        return [float(delta1) * (1.0 + float(alpha) * np.cos(4.0 * th))]
    if model == MODEL_TWO_BAND_S:
        return [
            np.full_like(th, float(delta1), dtype=float),
            np.full_like(th, float(delta2), dtype=float),
        ]
    if model == MODEL_TWO_BAND_S_INGAP:
        return [
            np.full_like(th, float(delta1), dtype=float),
            np.full_like(th, float(delta2), dtype=float),
            np.full_like(th, float(delta3), dtype=float),
        ]
    if model == MODEL_THREE_BAND_S:
        return [
            np.full_like(th, float(delta1), dtype=float),
            np.full_like(th, float(delta2), dtype=float),
            np.full_like(th, float(delta3), dtype=float),
        ]
    if model == MODEL_TWO_BAND_ANISOTROPIC_S:
        return [
            float(delta1) * (1.0 + float(alpha) * np.cos(4.0 * th)),
            float(delta2) * (1.0 + float(alpha2) * np.cos(4.0 * th)),
        ]
    if model == MODEL_TWO_BAND_ANISOTROPIC_S_INGAP:
        return [
            float(delta1) * (1.0 + float(alpha) * np.cos(4.0 * th)),
            float(delta2) * (1.0 + float(alpha2) * np.cos(4.0 * th)),
            np.full_like(th, float(delta3), dtype=float),
        ]
    if model == MODEL_S_PLUS_D:
        return [
            np.full_like(th, float(delta1), dtype=float),
            float(delta2) * np.cos(2.0 * th),
        ]
    if model == MODEL_TWO_BAND_ANISOTROPIC_FESE:
        return [
            float(delta1) * (float(alpha) * np.cos(2.0 * th) + (1.0 - float(alpha))),
            float(delta2) * (float(alpha2) * np.cos(2.0 * th) - (1.0 - float(alpha2))),
        ]
    return [np.full_like(th, float(delta1), dtype=float)]


def _clip_fese_p_value(value: float) -> float:
    return float(np.clip(float(value), 0.0, 0.49))


def normalize_three_band_weights(weight1: float, weight2: float) -> Tuple[float, float, float]:
    try:
        w1 = float(weight1)
    except Exception:
        w1 = 0.0
    try:
        w2 = float(weight2)
    except Exception:
        w2 = 0.0
    w1 = float(np.clip(w1 if np.isfinite(w1) else 0.0, 0.0, 1.0))
    w2 = float(np.clip(w2 if np.isfinite(w2) else 0.0, 0.0, 1.0))
    total12 = w1 + w2
    if total12 > 1.0:
        w1 /= total12
        w2 /= total12
        total12 = 1.0
    w3 = float(max(0.0, 1.0 - total12))
    return float(w1), float(w2), w3


def order_fese_parameters(
    delta_hole_meV: float,
    delta_electron_meV: float,
    p_hole: float,
    p_electron: float,
    hole_weight: float,
):
    d_h = float(delta_hole_meV)
    d_e = float(delta_electron_meV)
    p_h = _clip_fese_p_value(p_hole)
    p_e = _clip_fese_p_value(p_electron)
    w_h = float(np.clip(float(hole_weight), 0.0, 1.0))
    return d_h, d_e, p_h, p_e, w_h


def _paper_dynes_angular_dos(energy_meV: np.ndarray, gap_values_meV: np.ndarray, gamma_meV: float) -> np.ndarray:
    ee = np.asarray(energy_meV, dtype=float).ravel()
    gap = np.asarray(gap_values_meV, dtype=float).ravel()
    gamma = float(max(0.0, gamma_meV))
    z = ee[:, None] - 1j * gamma
    root = np.sqrt(z * z - np.abs(gap[None, :]) ** 2 + 0j)
    # The paper writes sign(E), but at E = 0 that expression is ambiguous.
    # Use the non-positive branch so the DOS stays continuous and positive
    # through zero instead of creating a one-point dip at the exact center.
    branch_sign = np.where(ee[:, None] <= 0.0, -1.0, 1.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = branch_sign * np.real(z / root)
    ratio = np.nan_to_num(ratio, nan=0.0, posinf=0.0, neginf=0.0)
    return np.asarray(np.mean(ratio, axis=1), dtype=float)


def _positive_dynes_dos(energy_meV: np.ndarray, gap_values_meV: np.ndarray, gamma_meV: float) -> np.ndarray:
    ee = np.asarray(energy_meV, dtype=float).ravel()
    gap = np.asarray(gap_values_meV, dtype=float)
    gamma = float(max(0.0, gamma_meV))
    z = ee[:, None] - 1j * gamma
    root = np.sqrt(z * z - gap[None, :] * gap[None, :] + 0j)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.real(z / root)
    ratio = np.abs(np.nan_to_num(ratio, nan=0.0, posinf=0.0, neginf=0.0))
    return np.asarray(np.mean(ratio, axis=1), dtype=float)


def _symmetric_lorentzian_peaks(energy_meV: np.ndarray, center_meV: float, gamma_meV: float) -> np.ndarray:
    ee = np.asarray(energy_meV, dtype=float).ravel()
    center = abs(float(center_meV))
    gamma = float(max(abs(float(gamma_meV)), 1e-9))
    gamma2 = gamma * gamma
    left = gamma2 / ((ee + center) * (ee + center) + gamma2)
    right = gamma2 / ((ee - center) * (ee - center) + gamma2)
    return np.asarray(left + right, dtype=float)


def evaluate_gap_dos_model(
    energy_meV: np.ndarray,
    model_name: str,
    delta1_meV: float,
    gamma1_meV: float,
    delta2_meV: float = 0.0,
    gamma2_meV: float = 0.0,
    weight: float = 0.5,
    alpha: float = 0.0,
    alpha2: float = 0.0,
    theta_count: int = DEFAULT_GAP_MODEL_THETA_COUNT,
    delta3_meV: float = 0.0,
    gamma3_meV: float = 0.0,
    weight2: float = 0.25,
) -> np.ndarray:
    model = normalize_gap_model_name(model_name)
    ee = np.asarray(energy_meV, dtype=float).ravel()
    n_theta = max(17, int(theta_count))
    theta = np.linspace(0.0, np.pi, n_theta, endpoint=False, dtype=float)
    cos2 = np.cos(2.0 * theta)
    cos4 = np.cos(4.0 * theta)
    w = float(np.clip(float(weight), 0.0, 1.0))
    g2 = float(gamma2_meV if np.isfinite(float(gamma2_meV)) else gamma1_meV)
    if model == MODEL_ISOTROPIC_S:
        return _positive_dynes_dos(ee, np.asarray([float(delta1_meV)], dtype=float), gamma1_meV)
    if model == MODEL_D_WAVE:
        gaps = float(delta1_meV) * cos2
        return _positive_dynes_dos(ee, gaps, gamma1_meV)
    if model == MODEL_ANISOTROPIC_S:
        gaps = float(delta1_meV) * (1.0 + float(alpha) * cos4)
        return _positive_dynes_dos(ee, gaps, gamma1_meV)
    if model == MODEL_TWO_BAND_S:
        band1 = _positive_dynes_dos(ee, np.asarray([float(delta1_meV)], dtype=float), gamma1_meV)
        band2 = _positive_dynes_dos(ee, np.asarray([float(delta2_meV)], dtype=float), g2)
        return np.asarray(w * band1 + (1.0 - w) * band2, dtype=float)
    if model == MODEL_TWO_BAND_S_INGAP:
        g3 = float(gamma3_meV if np.isfinite(float(gamma3_meV)) else gamma1_meV)
        band1 = _positive_dynes_dos(ee, np.asarray([float(delta1_meV)], dtype=float), gamma1_meV)
        band2 = _positive_dynes_dos(ee, np.asarray([float(delta2_meV)], dtype=float), g2)
        peak = float(max(0.0, weight2)) * _symmetric_lorentzian_peaks(ee, delta3_meV, g3)
        return np.asarray(w * band1 + (1.0 - w) * band2 + peak, dtype=float)
    if model == MODEL_THREE_BAND_S:
        g3 = float(gamma3_meV if np.isfinite(float(gamma3_meV)) else gamma1_meV)
        w1, w2, w3 = normalize_three_band_weights(weight, weight2)
        band1 = _positive_dynes_dos(ee, np.asarray([float(delta1_meV)], dtype=float), gamma1_meV)
        band2 = _positive_dynes_dos(ee, np.asarray([float(delta2_meV)], dtype=float), g2)
        band3 = _positive_dynes_dos(ee, np.asarray([float(delta3_meV)], dtype=float), g3)
        return np.asarray(w1 * band1 + w2 * band2 + w3 * band3, dtype=float)
    if model == MODEL_TWO_BAND_ANISOTROPIC_S:
        gap1 = float(delta1_meV) * (1.0 + float(alpha) * cos4)
        gap2 = float(delta2_meV) * (1.0 + float(alpha2) * cos4)
        band1 = _positive_dynes_dos(ee, gap1, gamma1_meV)
        band2 = _positive_dynes_dos(ee, gap2, g2)
        return np.asarray(w * band1 + (1.0 - w) * band2, dtype=float)
    if model == MODEL_TWO_BAND_ANISOTROPIC_S_INGAP:
        g3 = float(gamma3_meV if np.isfinite(float(gamma3_meV)) else gamma1_meV)
        gap1 = float(delta1_meV) * (1.0 + float(alpha) * cos4)
        gap2 = float(delta2_meV) * (1.0 + float(alpha2) * cos4)
        band1 = _positive_dynes_dos(ee, gap1, gamma1_meV)
        band2 = _positive_dynes_dos(ee, gap2, g2)
        peak = float(max(0.0, weight2)) * _symmetric_lorentzian_peaks(ee, delta3_meV, g3)
        return np.asarray(w * band1 + (1.0 - w) * band2 + peak, dtype=float)
    if model == MODEL_S_PLUS_D:
        band1 = _positive_dynes_dos(ee, np.asarray([float(delta1_meV)], dtype=float), gamma1_meV)
        band2 = _positive_dynes_dos(ee, float(delta2_meV) * cos2, g2)
        return np.asarray(w * band1 + (1.0 - w) * band2, dtype=float)
    if model == MODEL_TWO_BAND_ANISOTROPIC_FESE:
        n_theta_fese = max(33, int(theta_count if np.isfinite(theta_count) else DEFAULT_FESE_MODEL_THETA_COUNT))
        theta_fese = np.linspace(0.0, np.pi, n_theta_fese, endpoint=False, dtype=float)
        cos2_fese = np.cos(2.0 * theta_fese)
        d_h, d_e, p_h, p_e, w_h = order_fese_parameters(delta1_meV, delta2_meV, alpha, alpha2, weight)
        gap_h = d_h * (p_h * cos2_fese + (1.0 - p_h))
        gap_e = d_e * (p_e * cos2_fese - (1.0 - p_e))
        band_h = _paper_dynes_angular_dos(ee, gap_h, gamma1_meV)
        band_e = _paper_dynes_angular_dos(ee, gap_e, g2 if gap_model_uses_second_gamma(model) else gamma1_meV)
        return np.asarray(w_h * band_h + (1.0 - w_h) * band_e, dtype=float)
    return _positive_dynes_dos(ee, np.asarray([float(delta1_meV)], dtype=float), gamma1_meV)
