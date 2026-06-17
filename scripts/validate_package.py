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
    "references/task-cards/sts-dat-quick.md",
    "references/task-cards/gap-fit-quick.md",
    "references/quality-checks.md",
    "references/reporting.md",
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
        "references/task-cards/sts-dat-quick.md",
        "references/task-cards/gap-fit-quick.md",
        "references/pysidam-capability-index.json",
        "runtime/requirements-core.txt",
    ],
    "SKILL.md": [
        "name: stm-sjtm-data-processing",
        "quick card",
        "scripts/resolve_runtime.py --probe",
        "scripts/pysidam_agent/read_file.py",
        "scripts/pysidam_agent/fit_gap.py",
        "references/pysidam-capability-index.json",
        "references/runtime-bootstrap.md",
        "references/data-contracts.md",
        "references/quality-checks.md",
        "references/format-io-matrix.md",
        "references/nanonis-3ds-ingest.md",
        "Do not make phase conclusions from real-IFFT images alone.",
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
        "divider=100.0",
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
        "Spectroscopy Processing",
        "SJTM-Specific Maps",
        "Fourier, QPI, And Lock-In",
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
        "SJTMIcExtractionWindow",
        "SJTMSuperfluidDensityWindow",
    ],
    "references/pysidam-capability-map.md": [
        "PySIDAM Capability Map",
        "HEADLESS_READY",
        "GUI_WRAPPED_EXTRACT",
        "OPTIONAL_DEP",
        "pysidam_agent",
        "capability index",
    ],
    "references/pysidam-capability-index.json": [
        "\"schema_version\"",
        "\"pysidam_commit\"",
        "\"HEADLESS_READY\"",
        "\"GUI_WRAPPED_EXTRACT\"",
        "\"core_io\"",
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
        "fit_selected_gap_dos_model_guarded",
        "Do not write a new optimizer",
        "PySIDAM fitter import is blocked",
    ],
    "references/quality-checks.md": [
        "Data-Contract Gates",
        "Fitting Gates",
        "FFT And Lock-In Gates",
        "Cross-Observable Gates",
        "Reporting Gates",
    ],
    "references/reporting.md": [
        "report.json",
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
        "fit_selected_gap_dos_model_guarded",
        "pysidam_fitter_import_failed",
        "Do not write a new optimizer",
        "fit_strategy",
        "fit_max_starts",
        "initial_params",
        "summary-json",
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
    if "fit_selected_gap_dos_model_guarded" not in text:
        fail("fit_gap.py must call PySIDAM fit_selected_gap_dos_model_guarded")
    forbidden = [
        "from scipy.optimize import least_squares",
        "from scipy.optimize import curve_fit",
        "scipy.optimize.least_squares",
        "scipy.optimize.curve_fit",
    ]
    bad = [token for token in forbidden if token in text]
    if bad:
        fail("fit_gap.py must not define its own optimizer: " + ", ".join(bad))


def main() -> int:
    check_required_files()
    check_required_tokens()
    check_forbidden_tokens()
    check_skill_size()
    check_portable_references()
    check_fit_bridge_uses_pysidam_fitter()
    print("PASS: stm-sjtm-data-processing package is structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
