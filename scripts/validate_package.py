#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "README.md",
    "SKILL.md",
    "LICENSE",
    "CHANGELOG.md",
    "RELEASE_NOTES_v0.1.0.md",
    "RELEASE_NOTES_v0.1.1.md",
    "RELEASE_NOTES_v0.1.2.md",
    "RELEASE_NOTES_v0.1.3.md",
    "RELEASE_NOTES_v0.1.4.md",
    "RELEASE_NOTES_v0.1.5.md",
    "RELEASE_NOTES_v0.2.0.md",
    "RELEASE_NOTES_v0.2.1.md",
    "RELEASE_NOTES_v0.2.2.md",
    "RELEASE_NOTES_v0.2.3.md",
    "RELEASE_NOTES_v0.2.4.md",
    "pysidam_agent_core/__init__.py",
    "pysidam_agent_core/approval.py",
    "pysidam_agent_core/gap_priority.py",
    "pysidam_agent_core/io.py",
    "pysidam_agent_core/models.py",
    "pysidam_agent_core/numerics.py",
    "pysidam_agent_core/gap_fitting.py",
    "pysidam_agent_core/bragg_phase.py",
    "pysidam_agent_core/phase_lockin.py",
    "pysidam_agent_core/atom_ai.py",
    "scripts/approval_gate.py",
    "scripts/probe_runtime.py",
    "scripts/resolve_runtime.py",
    "scripts/bootstrap_runtime.py",
    "scripts/sync_installed_skill.py",
    "scripts/pysidam_agent/__init__.py",
    "scripts/pysidam_agent/common.py",
    "scripts/pysidam_agent/capabilities.py",
    "scripts/pysidam_agent/read_file.py",
    "scripts/pysidam_agent/plot_spectrum.py",
    "scripts/pysidam_agent/fit_gap.py",
    "scripts/pysidam_agent/bragg_phase.py",
    "scripts/pysidam_agent/phase_lockin.py",
    "scripts/pysidam_agent/atom_ai.py",
    "runtime/constraints.txt",
    "runtime/requirements-core.txt",
    "runtime/requirements-nanonis.txt",
    "runtime/requirements-ibw.txt",
    "runtime/requirements-ai.txt",
    "runtime/requirements-ui.txt",
    "references/workflow.md",
    "references/runtime-bootstrap.md",
    "references/format-io-matrix.md",
    "references/data-contracts.md",
    "references/nanonis-3ds-ingest.md",
    "references/fitting-recipes.md",
    "references/pysidam-tool-map.md",
    "references/pysidam-capability-map.md",
    "references/pysidam-capability-index.json",
    "references/approval-gates.md",
    "references/task-cards/sts-dat-quick.md",
    "references/task-cards/gap-fit-quick.md",
    "references/quality-checks.md",
    "references/reporting.md",
    "assets/approval-gate-template.html",
    "tests/test_approval_gate.py",
    "tests/test_atom_ai_core.py",
    "tests/test_phase_lockin_core.py",
    "tests/test_phase_lockin_cli.py",
]

REQUIRED_TOKENS = {
    "README.md": [
        "STM/SJTM Data Processing Agent Skill",
        "Quick Start",
        "Codex Installation",
        "Non-Codex Agent Usage",
        "GitHub Release",
        "scripts/probe_runtime.py",
        "scripts/resolve_runtime.py",
        "scripts/bootstrap_runtime.py",
        "scripts/sync_installed_skill.py",
        "scripts/pysidam_agent/read_file.py",
        "scripts/pysidam_agent/fit_gap.py",
        "scripts/pysidam_agent/bragg_phase.py",
        "scripts/pysidam_agent/phase_lockin.py",
        "scripts/pysidam_agent/atom_ai.py",
        "references/task-cards/sts-dat-quick.md",
        "references/task-cards/gap-fit-quick.md",
        "references/pysidam-capability-index.json",
        "runtime/requirements-core.txt",
    ],
    "SKILL.md": [
        "name: stm-sjtm-data-processing",
        "quick card",
        "Ask the user to choose a fitting mode",
        "scripts/resolve_runtime.py --probe",
        "scripts/pysidam_agent/read_file.py",
        "scripts/pysidam_agent/fit_gap.py",
        "scripts/pysidam_agent/bragg_phase.py",
        "scripts/pysidam_agent/phase_lockin.py",
        "scripts/pysidam_agent/atom_ai.py",
        "references/pysidam-capability-index.json",
        "Fast Tool Routing",
        "scripts/pysidam_agent/capabilities.py --query",
        "Do not build a fresh source index",
        "references/approval-gates.md",
        "approval gate",
        "fit_window",
        "q_selection",
        "peak_count",
        "references/runtime-bootstrap.md",
        "references/data-contracts.md",
        "references/quality-checks.md",
        "references/format-io-matrix.md",
        "references/nanonis-3ds-ingest.md",
        "Do not make phase conclusions from real-IFFT images alone.",
        "lockin_engine = pysidam.qpi_analysis.qpi_phase_analysis.lockin_phase_extraction",
        "resize_ratio",
        "lattice-qc",
        "wipe-regions",
    ],
    "references/runtime-bootstrap.md": [
        "nanonispy",
        "Atom_Identificator_core",
        "igorwriter",
        "bootstrap_runtime.py",
        "resolve_runtime.py",
        "runtime.json",
        "host.json",
        "user-writable",
        "no sudo",
        "git fetch origin --prune",
        "do not merge or reset",
    ],
    "references/nanonis-3ds-ingest.md": [
        "read_nanonis_file",
        "prepare_3ds_dataset",
        "(x, y, bias)",
        "divider=1.0",
        "Do not hand-roll",
    ],
    "references/format-io-matrix.md": [
        ".3ds",
        ".sxm",
        ".dat",
        ".ibw",
        ".npz",
        "PXP is not",
        "normalize_sxm_direction_map",
        "imported_file_to_numeric_table",
    ],
    "references/workflow.md": [
        "Ingest",
        "runtime bootstrap",
        "Normalize Data Contracts",
        "Topography Processing",
        "atom_ai.py recommend-scale",
        "Spectroscopy Processing",
        "SJTM-Specific Maps",
        "Fourier, QPI, And Lock-In",
        "phase_lockin.py run",
        "Cross-Observable Analysis",
        "Evidence Package",
    ],
    "references/data-contracts.md": [
        "(y, x)",
        "(y, x, bias)",
        "(bias, y, x)",
        "(x, y, bias)",
        "bias unit",
        "coordinate frame",
    ],
    "references/fitting-recipes.md": [
        "Superconducting Gap Fitting",
        "Dynes",
        "SIS",
        "NIS",
        "Multipeak",
        "approval gate",
        "fit_window",
        "peak_count",
        "strict-pysidam-compatible",
        "gap-priority experimental",
        "Peak Height, Z-Ratio, And Bias Calibration",
    ],
    "references/pysidam-tool-map.md": [
        "origin/main",
        "pysidam.core.nanonis_io",
        "pysidam.core.dataset_utils",
        "pysidam_agent",
        "references/pysidam-capability-index.json",
        "Do not instantiate Qt",
        "LFDriftCorrector",
        "PeakFitter.fit_single_pixel",
        "UniversalVortexFitterEngine",
        "fit_nis_dynes_didv",
        "lockin_phase_extraction",
        "phase_lockin.py run",
        "SJTMIcExtractionWindow",
        "SJTMSuperfluidDensityWindow",
    ],
    "references/pysidam-capability-map.md": [
        "PySIDAM Capability Map",
        "HEADLESS_READY",
        "GUI_WRAPPED_EXTRACT",
        "OPTIONAL_DEP",
        "pysidam_agent",
        "phase_lockin.py",
        "atom_ai.py",
        "capability index",
    ],
    "pysidam_agent_core/bragg_phase.py": [
        "q_selection_policy",
        "find_peak_in_roi",
        "preprocess_topography",
    ],
    "pysidam_agent_core/phase_lockin.py": [
        "LOCKIN_ENGINE",
        "q_cycles_to_pysidam_px_yx",
        "run_pysidam_lockin",
        "pysidam.qpi_analysis.qpi_phase_analysis.lockin_phase_extraction",
    ],
    "pysidam_agent_core/atom_ai.py": [
        "scale_recommendation",
        "lattice_qc",
        "apply_wipe_regions",
        "resize_ratio",
        "fourfold_order",
    ],
    "scripts/pysidam_agent/bragg_phase.py": [
        "policy",
        "inspect-roi",
        "lockin-from-decision",
    ],
    "scripts/pysidam_agent/phase_lockin.py": [
        "parse_q_args",
        "write_outputs",
        "run_pysidam_lockin",
        "phase_lockin_maps.npz",
    ],
    "scripts/pysidam_agent/atom_ai.py": [
        "recommend-scale",
        "lattice-qc",
        "wipe-regions",
        "pysidam_agent_core.atom_ai",
    ],
    "references/pysidam-capability-index.json": [
        "\"schema_version\"",
        "\"pysidam_commit\"",
        "\"HEADLESS_READY\"",
        "\"GUI_WRAPPED_EXTRACT\"",
        "\"core_io\"",
        "\"agent_atom_ai_scale_qc_wipe\"",
        "\"clean_2d_phase_lockin_bridge\"",
        "\"qpi_lockin\"",
        "\"sjtm\"",
        "\"deconvolution\"",
    ],
    "references/task-cards/sts-dat-quick.md": [
        "STS DAT Quick Card",
        "resolve_runtime.py --probe",
        "pysidam_agent/read_file.py",
        "pysidam_agent/plot_spectrum.py",
        "no scientific conclusion",
    ],
    "references/task-cards/gap-fit-quick.md": [
        "Gap Fit Quick Card",
        "pysidam_agent/fit_gap.py",
        "pysidam_agent_core.gap_fitting.fit_gap_model_guarded",
        "two_band_splusminus_gap_priority",
        "fit_overlay_overview.png",
        "quantitative fitting must produce diagnostic plots",
        "Ask before fitting",
        "strict-pysidam-compatible",
        "gap-priority experimental",
        "Do not write a new optimizer",
        "PySIDAM UI fitter import is blocked",
    ],
    "references/quality-checks.md": [
        "Data-Contract Gates",
        "Fitting Gates",
        "FFT And Lock-In Gates",
        "lockin_phase_extraction",
        "AI Atom Detection Gates",
        "Cross-Observable Gates",
        "Reporting Gates",
        "approval gate",
        "fit_window",
        "q_selection",
        "peak_count",
    ],
    "references/reporting.md": [
        "report.json",
        "approval gate",
        "fit_window",
        "q_selection",
        "peak_count",
        "inputs",
        "data_contract",
        "quality",
        "warnings",
        "software",
    ],
    "CHANGELOG.md": ["v0.1.0", "Initial preview release"],
    "RELEASE_NOTES_v0.1.0.md": ["v0.1.0", "Release checklist"],
    "RELEASE_NOTES_v0.1.1.md": ["v0.1.1", "runtime bootstrap", "probe_runtime.py"],
    "RELEASE_NOTES_v0.1.2.md": ["v0.1.2", "bootstrap_runtime.py", "isolated"],
    "RELEASE_NOTES_v0.1.3.md": ["v0.1.3", "resolve_runtime.py", "host.json"],
    "RELEASE_NOTES_v0.1.4.md": ["v0.1.4", "quick card", "pysidam_agent", "sync_installed_skill.py"],
    "RELEASE_NOTES_v0.1.5.md": ["v0.1.5", "fit_gap.py", "fit_selected_gap_dos_model_guarded", "Do not write a new optimizer"],
    "RELEASE_NOTES_v0.2.0.md": ["v0.2.0", "pysidam_agent_core", "headless", "fit_gap_model_guarded"],
    "RELEASE_NOTES_v0.2.1.md": ["v0.2.1", "strict-pysidam-compatible", "gap-priority experimental", "Ask before fitting"],
    "RELEASE_NOTES_v0.2.2.md": ["v0.2.2", "two_band_splusminus_gap_priority", "--save-overview", "fit_overlay_overview.png"],
    "RELEASE_NOTES_v0.2.3.md": ["v0.2.3", "approval gate", "fit_window", "q_selection", "peak_count"],
    "RELEASE_NOTES_v0.2.4.md": [
        "v0.2.4",
        "bragg_phase.py",
        "divider",
        "read_file.py --quick",
        "user-specified q",
    ],
    "pysidam_agent_core/__init__.py": ["fit_gap_model_guarded", "scale_recommendation", "run_pysidam_lockin"],
    "pysidam_agent_core/approval.py": [
        "GATE_TYPES",
        "fit_window",
        "q_selection",
        "peak_count",
        "validate_proposal",
        "validate_decision",
        "validate_report_links_decision",
        "render_review_html",
    ],
    "pysidam_agent_core/gap_priority.py": [
        "PROFILE_TWO_BAND_SPLUSMINUS_GAP_PRIORITY",
        "fit_two_band_splusminus_gap_priority",
        "fit_gap_priority_modes",
        "candidate_fit_abs_mV",
        "center_platform_rmse_pA",
        "coherence_peak_rmse_pA",
        "boundary_hit",
    ],
    "pysidam_agent_core/io.py": ["load_signals", "read_nanonis_file", "read_imported_file"],
    "pysidam_agent_core/models.py": [
        "pysidam.core.superconducting_gap_models",
        "evaluate_gap_dos_model",
        "get_deconvolution_fit_param_spec",
    ],
    "pysidam_agent_core/numerics.py": [
        "normalize_xy_arrays",
        "feature_weights",
        "detect_gap_peak_positions",
        "solve_affine_reference_scale_offset",
    ],
    "pysidam_agent_core/gap_fitting.py": [
        "fit_gap_model_guarded",
        "fit_gap_model",
        "least_squares",
        "fit_feature_weighted",
    ],
    "scripts/probe_runtime.py": ["MODULES", "nanonispy", "Atom_Identificator_core", "git_info"],
    "scripts/resolve_runtime.py": [
        "HOST_CONFIG",
        "runtime.json",
        "--probe",
        "--print-python",
        "--bootstrap-command",
        "subprocess.check_call",
    ],
    "scripts/bootstrap_runtime.py": [
        "DEFAULT_GROUPS",
        "HOST_CONFIG",
        "load_host_config",
        "safe_venv_path",
        "--dry-run",
        "--no-network",
        "subprocess.check_call",
        "runtime.json",
    ],
    "scripts/sync_installed_skill.py": [
        "remove_installed_git",
        "stm-sjtm-data-processing",
        ".codex/skills",
        "dry-run",
    ],
    "scripts/pysidam_agent/common.py": [
        "ensure_runtime",
        "STM_SJTM_AGENT_RUNTIME_REEXEC",
        "runtime.json",
        "pysidam_root",
    ],
    "scripts/pysidam_agent/capabilities.py": [
        "pysidam-capability-index.json",
        "--domain",
        "--status",
        "--query",
        "matches_query",
        "Keyword search",
    ],
    "scripts/pysidam_agent/read_file.py": [
        "read_nanonis_file",
        "read_imported_file",
        "privacy",
        "signals_summary",
    ],
    "scripts/pysidam_agent/plot_spectrum.py": [
        "matplotlib.use(\"Agg\")",
        "Bias calc (V)",
        "LI Demod 1 X",
        "summary-json",
    ],
    "scripts/pysidam_agent/fit_gap.py": [
        "pysidam_agent_core.gap_fitting",
        "fit_gap_model_guarded",
        "two_band_splusminus_gap_priority",
        "--profile",
        "--symmetry",
        "--auto-fit-window",
        "--save-overview",
        "report.json",
        "pysidam_agent_core_import_failed",
        "Do not write a task-local optimizer",
        "fit_strategy",
        "fit_max_starts",
        "initial_params",
        "summary-json",
    ],
    "scripts/approval_gate.py": [
        "validate-proposal",
        "validate-decision",
        "validate-report",
        "render-html",
        "approval_proposal.json",
        "approval_decision.json",
    ],
    "tests/test_atom_ai_core.py": [
        "test_resize_1p5_matches_fts_spin_pixel_scale",
        "test_square_lattice_qc_passes_orderly_grid",
        "test_apply_wipe_regions_marks_dw_band_and_dirty_spot",
    ],
    "tests/test_phase_lockin_core.py": [
        "test_q_cycles_convert_to_pysidam_absolute_pixels",
        "test_run_pysidam_lockin_emits_standard_maps_and_engine",
    ],
    "tests/test_phase_lockin_cli.py": [
        "test_parse_q_args_accepts_labels_and_auto_labels",
        "test_write_outputs_saves_report_npz_and_stats",
    ],
    "references/approval-gates.md": [
        "Approval Gates",
        "fit_window",
        "q_selection",
        "peak_count",
        "user_preapproved",
        "approval_proposal.json",
        "approval_decision.json",
    ],
    "assets/approval-gate-template.html": [
        "{{ question }}",
        "{{ gate_type }}",
        "{{ recommendation_json }}",
        "{{ risks_html }}",
        "{{ evidence_html }}",
    ],
    "tests/test_approval_gate.py": [
        "test_valid_q_selection_proposal_passes",
        "test_invalid_gate_type_fails",
        "test_valid_decision_passes",
        "test_report_requires_decision_reference",
        "test_render_review_html_contains_question",
    ],
    "runtime/requirements-core.txt": ["numpy", "scipy", "scikit-image", "matplotlib", "openpyxl"],
    "runtime/requirements-nanonis.txt": ["nanonispy"],
    "runtime/requirements-ibw.txt": ["igorwriter"],
    "runtime/requirements-ai.txt": ["AI4STM"],
    "runtime/requirements-ui.txt": ["PyQt5", "pyqtgraph"],
    "runtime/constraints.txt": ["# Constraints"],
}

FORBIDDEN_TOKENS = [
    "Project FeSe",
    "map011",
    "20250926",
    "pxp_exports",
    "fe_site_analysis",
    "/Users/",
    "root__",
]

INCOMPLETE_MARKERS = ["T" + "BD", "TO" + "DO", "FIX" + "ME", "REPLACE" + "_ME"]


def read_text(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def check_required_files() -> None:
    missing = [rel for rel in REQUIRED_FILES if not (ROOT / rel).is_file()]
    if missing:
        fail("missing required files: " + ", ".join(missing))


def check_required_tokens() -> None:
    for rel, tokens in REQUIRED_TOKENS.items():
        text = read_text(rel)
        missing = [token for token in tokens if token not in text]
        if missing:
            fail(f"{rel} is missing required text: {', '.join(missing)}")


def check_forbidden_tokens() -> None:
    checked_files = (
        list(ROOT.glob("*.md"))
        + list((ROOT / "references").rglob("*.md"))
        + list((ROOT / "references").rglob("*.json"))
    )
    for path in checked_files:
        text = path.read_text(encoding="utf-8")
        bad = [token for token in FORBIDDEN_TOKENS if token in text]
        if bad:
            fail(f"{path.relative_to(ROOT)} contains forbidden experiment-specific text: {', '.join(bad)}")
        incomplete = [marker for marker in INCOMPLETE_MARKERS if marker in text]
        if incomplete:
            fail(f"{path.relative_to(ROOT)} contains incomplete marker text: {', '.join(incomplete)}")


def check_skill_size() -> None:
    lines = read_text("SKILL.md").splitlines()
    if len(lines) > 180:
        fail(f"SKILL.md should stay thin; found {len(lines)} lines")


def check_portable_references() -> None:
    for path in (ROOT / "references").glob("*.md"):
        text = path.read_text(encoding="utf-8")
        if "REQUIRED SUB-SKILL" in text or "::git-" in text:
            fail(f"{path.relative_to(ROOT)} contains Codex-specific control syntax")


def check_fit_bridge_uses_pysidam_fitter() -> None:
    path = ROOT / "scripts" / "pysidam_agent" / "fit_gap.py"
    if not path.is_file():
        fail("missing fit bridge: scripts/pysidam_agent/fit_gap.py")
    text = path.read_text(encoding="utf-8")
    if "pysidam_agent_core.gap_fitting" not in text or "fit_gap_model_guarded" not in text:
        fail("fit_gap.py must call pysidam_agent_core.gap_fitting.fit_gap_model_guarded")
    forbidden = [
        "from scipy.optimize import least_squares",
        "from scipy.optimize import curve_fit",
        "scipy.optimize.least_squares",
        "scipy.optimize.curve_fit",
    ]
    bad = [token for token in forbidden if token in text]
    if bad:
        fail("fit_gap.py must keep optimization inside pysidam_agent_core: " + ", ".join(bad))


def check_headless_core_boundary() -> None:
    checked_files = list((ROOT / "pysidam_agent_core").glob("*.py"))
    checked_files.append(ROOT / "scripts" / "pysidam_agent" / "fit_gap.py")
    forbidden = [
        "PyQt5",
        "pyqtgraph",
        "QApplication",
        "QWidget",
        "pysidam.useful_tools.usefultools_deconvolution_point",
    ]
    for path in checked_files:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        bad = [token for token in forbidden if token in text]
        if bad:
            fail(f"{path.relative_to(ROOT)} imports UI-bound fitting code: {', '.join(bad)}")


def main() -> int:
    check_required_files()
    check_required_tokens()
    check_forbidden_tokens()
    check_skill_size()
    check_portable_references()
    check_fit_bridge_uses_pysidam_fitter()
    check_headless_core_boundary()
    print("PASS: stm-sjtm-data-processing package is structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
