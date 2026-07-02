from __future__ import annotations

from pathlib import Path
from typing import Any


def build_read_parameters(divider: float = 1.0, divider_explicit: bool = False, quick: bool = False) -> dict[str, Any]:
    """Return the auditable read contract used by agent bridge readers."""
    value = float(divider)
    if divider_explicit:
        source = "explicit_user_requested_extra_scaling"
        policy = (
            "Raw Nanonis bias axes are normally treated as already divider-corrected by the experiment "
            "software; this run applies an extra divider only because it was explicitly requested."
        )
    else:
        source = "default_no_rescale_bias_already_corrected"
        policy = (
            "Raw Nanonis bias axes are treated as already divider-corrected by the experiment software. "
            "Do not rescale from header comments such as divider=1/100 unless the user explicitly requests "
            "extra scaling."
        )
    return {
        "divider": value,
        "divider_source": source,
        "divider_policy": policy,
        "quick": bool(quick),
    }


def load_signals(path: str | Path) -> tuple[dict[str, Any], str]:
    """Load one spectrum-like file through PySIDAM core readers."""
    file_path = Path(path).expanduser()
    suffix = file_path.suffix.lower()
    if suffix == ".dat":
        from pysidam.core.nanonis_io import read_nanonis_file

        nf = read_nanonis_file(file_path)
        return getattr(nf.obj, "signals", {}), "pysidam.core.nanonis_io.read_nanonis_file"
    if suffix in {".txt", ".csv", ".tsv", ".ibw"}:
        from pysidam.core.import_io import read_imported_file

        imported = read_imported_file(file_path)
        return getattr(imported.obj, "signals", {}), "pysidam.core.import_io.read_imported_file"
    raise ValueError(f"Unsupported spectrum input suffix: {suffix}")
