"""Headless PySIDAM-derived helpers for STM/SJTM agent workflows."""

from importlib import import_module

__all__ = [
    "ApprovalValidationError",
    "PROFILE_TWO_BAND_SPLUSMINUS_GAP_PRIORITY",
    "apply_wipe_regions",
    "fit_gap_model",
    "fit_gap_model_guarded",
    "fit_gap_priority_modes",
    "build_domain_wall_masks",
    "domain_wall_policy",
    "lattice_qc",
    "q_cycles_to_pysidam_px_yx",
    "render_review_html",
    "region_stats",
    "run_pysidam_lockin",
    "scale_recommendation",
    "validate_decision",
    "validate_proposal",
    "validate_report_links_decision",
]


def __getattr__(name: str):
    if name in {
        "ApprovalValidationError",
        "render_review_html",
        "validate_decision",
        "validate_proposal",
        "validate_report_links_decision",
    }:
        approval = import_module(".approval", __name__)
        return getattr(approval, name)
    if name in {"fit_gap_model", "fit_gap_model_guarded"}:
        gap_fitting = import_module(".gap_fitting", __name__)
        return getattr(gap_fitting, name)
    if name in {"PROFILE_TWO_BAND_SPLUSMINUS_GAP_PRIORITY", "fit_gap_priority_modes"}:
        gap_priority = import_module(".gap_priority", __name__)
        return getattr(gap_priority, name)
    if name in {"apply_wipe_regions", "lattice_qc", "scale_recommendation"}:
        atom_ai = import_module(".atom_ai", __name__)
        return getattr(atom_ai, name)
    if name in {"build_domain_wall_masks", "domain_wall_policy", "region_stats"}:
        domain_wall = import_module(".domain_wall", __name__)
        return getattr(domain_wall, name)
    if name in {"q_cycles_to_pysidam_px_yx", "run_pysidam_lockin"}:
        phase_lockin = import_module(".phase_lockin", __name__)
        return getattr(phase_lockin, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
