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
    "scripts/probe_runtime.py",
    "scripts/bootstrap_runtime.py",
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
        "scripts/bootstrap_runtime.py",
        "runtime/requirements-core.txt",
    ],
    "SKILL.md": [
        "name: stm-sjtm-data-processing",
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
        "Do not instantiate Qt",
        "LFDriftCorrector",
        "PeakFitter.fit_single_pixel",
        "UniversalVortexFitterEngine",
        "fit_nis_dynes_didv",
        "lockin_phase_extraction",
        "SJTMIcExtractionWindow",
        "SJTMSuperfluidDensityWindow",
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
    "scripts/probe_runtime.py": ["MODULES", "nanonispy", "Atom_Identificator_core", "git_info"],
    "scripts/bootstrap_runtime.py": [
        "DEFAULT_GROUPS",
        "safe_venv_path",
        "--dry-run",
        "--no-network",
        "subprocess.check_call",
        "runtime.json",
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
    markdown_files = list(ROOT.glob("*.md")) + list((ROOT / "references").glob("*.md"))
    for path in markdown_files:
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


def main() -> int:
    check_required_files()
    check_required_tokens()
    check_forbidden_tokens()
    check_skill_size()
    check_portable_references()
    print("PASS: stm-sjtm-data-processing package is structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
