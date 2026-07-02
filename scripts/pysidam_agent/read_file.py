#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[2]
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

try:
    from .common import ensure_runtime, header_summary, signals_summary, write_json
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from pysidam_agent.common import ensure_runtime, header_summary, signals_summary, write_json

from pysidam_agent_core.io import build_read_parameters


RAW_NANONIS_SUFFIXES = {".3ds", ".sxm", ".dat"}
IMPORTED_SUFFIXES = {".txt", ".csv", ".tsv", ".ibw"}


def structural_signals_summary(signals: Any, max_channels: int = 80) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not isinstance(signals, dict):
        return out
    for idx, (name, raw) in enumerate(signals.items()):
        if idx >= max_channels:
            out["_truncated"] = True
            out["_channel_count"] = len(signals)
            break
        if isinstance(raw, dict):
            sub: dict[str, Any] = {}
            for key, value in raw.items():
                arr = getattr(value, "shape", None)
                sub[str(key)] = {
                    "shape": [int(x) for x in arr] if arr is not None else [],
                    "dtype": str(getattr(value, "dtype", type(value).__name__)),
                }
            out[str(name)] = sub
        else:
            arr = getattr(raw, "shape", None)
            out[str(name)] = {
                "shape": [int(x) for x in arr] if arr is not None else [],
                "dtype": str(getattr(raw, "dtype", type(raw).__name__)),
            }
    return out


def read_one(path: Path, divider: float, include_header_values: bool, quick: bool = False) -> dict[str, Any]:
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
            "signals_summary": structural_signals_summary(signals) if quick else signals_summary(signals),
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
                    "bias_summary": signals_summary({"bias_mv": bias}) if bias is not None else {},
                    "scan_size_nm": scan_size_nm,
                    "topography_candidates": list(topo.keys()) if isinstance(topo, dict) else [],
                    "internal_axis_order": "(x, y, bias)",
                    "divider_applied": float(divider),
                }
                if not quick:
                    item["prepared_3ds"]["cube_summary"] = signals_summary(cubes)
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
            "signals_summary": structural_signals_summary(signals) if quick else signals_summary(signals),
            "privacy": "full header values and raw data are not serialized by default",
        }

    raise ValueError(f"Unsupported file suffix for quick bridge: {suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read STM/SJTM files with the PySIDAM-backed agent bridge.")
    parser.add_argument("paths", nargs="+", help="Input files.")
    parser.add_argument("--divider", type=float, default=1.0, help="Bias divider for 3DS normalization.")
    parser.add_argument("--include-header-values", action="store_true", help="Serialize selected header values.")
    parser.add_argument("--quick", action="store_true", help="Return structural summaries only; keep default divider=1.")
    parser.add_argument("--output-json", default="", help="Optional JSON output path.")
    args = parser.parse_args()
    divider_explicit = any(arg == "--divider" or arg.startswith("--divider=") for arg in sys.argv[1:])

    runtime = ensure_runtime(reexec=True)
    files = []
    errors = []
    for raw_path in args.paths:
        path = Path(raw_path)
        try:
            files.append(
                read_one(
                    path,
                    divider=args.divider,
                    include_header_values=args.include_header_values,
                    quick=args.quick,
                )
            )
        except Exception as exc:
            errors.append({
                "path": str(path.expanduser()),
                "error_type": type(exc).__name__,
                "error": str(exc),
            })

    payload = {
        "tool": "pysidam_agent/read_file.py",
        "runtime": runtime,
        "read_parameters": build_read_parameters(
            divider=args.divider,
            divider_explicit=divider_explicit,
            quick=args.quick,
        ),
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
