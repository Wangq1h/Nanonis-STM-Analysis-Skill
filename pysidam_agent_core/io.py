from __future__ import annotations

from pathlib import Path
from typing import Any


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
