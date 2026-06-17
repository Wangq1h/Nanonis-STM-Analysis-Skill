#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any


try:
    from .common import ensure_runtime, header_summary, signals_summary, write_json
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from pysidam_agent.common import ensure_runtime, header_summary, signals_summary, write_json


RAW_NANONIS_SUFFIXES = {".3ds", ".sxm", ".dat"}
IMPORTED_SUFFIXES = {".txt", ".csv", ".tsv", ".ibw"}


def read_one(path: Path, divider: float, include_header_values: bool) -> dict[str, Any]:
    path = path.expanduser()
    suffix = path.suffix.lower()
    if suffix in RAW_NANONIS_SUFFIXES:
        from pysidam.core.nanonis_io import read_nanonis_file

        nf = read_nanonis_file(path)
        obj = nf.obj
        signals = getattr(obj, "signals", {})
        header = getattr(obj, "header", {})
        item: dict[str, Any] = {
            "path": str(path),
            "name": path.name,
            "suffix": suffix,
            "reader": "pysidam.core.nanonis_io.read_nanonis_file",
            "dtype": nf.dtype,
            "channels": list(nf.channels),
            "header": header_summary(header, include_values=include_header_values),
            "signals_summary": signals_summary(signals),
            "privacy": "full header values and raw data are not serialized by default",
        }
        if nf.dtype == "3ds":
            try:
                from pysidam.core.dataset_utils import prepare_3ds_dataset

                cubes, bias, scan_size_nm, topo = prepare_3ds_dataset(
                    signals,
                    header=header,
                    divider=divider,
                    spectral_only=False,
                )
                item["prepared_3ds"] = {
                    "cube_channels": list(cubes.keys()),
                    "cube_summary": signals_summary(cubes),
                    "bias_summary": signals_summary({"bias_mv": bias}) if bias is not None else {},
                    "scan_size_nm": scan_size_nm,
                    "topography_candidates": list(topo.keys()) if isinstance(topo, dict) else [],
                    "internal_axis_order": "(x, y, bias)",
                }
            except Exception as exc:
                item["prepared_3ds_error"] = f"{type(exc).__name__}: {exc}"
        return item

    if suffix in IMPORTED_SUFFIXES:
        from pysidam.core.import_io import read_imported_file

        imported = read_imported_file(path)
        obj = imported.obj
        signals = getattr(obj, "signals", {})
        header = getattr(obj, "header", {})
        return {
            "path": str(path),
            "name": path.name,
            "suffix": suffix,
            "reader": "pysidam.core.import_io.read_imported_file",
            "dtype": imported.dtype,
            "channels": list(imported.channels),
            "source_format": imported.source_format,
            "scan_size_nm": imported.scan_size_nm,
            "metadata": imported.metadata,
            "header": header_summary(header, include_values=include_header_values),
            "signals_summary": signals_summary(signals),
            "privacy": "full header values and raw data are not serialized by default",
        }

    raise ValueError(f"Unsupported file suffix for quick bridge: {suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read STM/SJTM files with the PySIDAM-backed agent bridge.")
    parser.add_argument("paths", nargs="+", help="Input files.")
    parser.add_argument("--divider", type=float, default=1.0, help="Bias divider for 3DS normalization.")
    parser.add_argument("--include-header-values", action="store_true", help="Serialize selected header values.")
    parser.add_argument("--output-json", default="", help="Optional JSON output path.")
    args = parser.parse_args()

    runtime = ensure_runtime(reexec=True)
    files = []
    errors = []
    for raw_path in args.paths:
        path = Path(raw_path)
        try:
            files.append(read_one(path, divider=args.divider, include_header_values=args.include_header_values))
        except Exception as exc:
            errors.append({
                "path": str(path.expanduser()),
                "error_type": type(exc).__name__,
                "error": str(exc),
            })

    payload = {
        "tool": "pysidam_agent/read_file.py",
        "runtime": runtime,
        "count": len(files),
        "error_count": len(errors),
        "files": files,
        "errors": errors,
    }
    if args.output_json:
        write_json(Path(args.output_json), payload)
    else:
        import json

        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if errors and not files else 0


if __name__ == "__main__":
    raise SystemExit(main())
