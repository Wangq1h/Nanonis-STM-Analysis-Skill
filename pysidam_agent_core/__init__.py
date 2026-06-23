"""Headless PySIDAM-derived helpers for STM/SJTM agent workflows."""

from importlib import import_module

__all__ = [
    "ApprovalValidationError",
    "PROFILE_TWO_BAND_SPLUSMINUS_GAP_PRIORITY",
    "fit_gap_model",
    "fit_gap_model_guarded",
    "fit_gap_priority_modes",
    "render_review_html",
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
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
