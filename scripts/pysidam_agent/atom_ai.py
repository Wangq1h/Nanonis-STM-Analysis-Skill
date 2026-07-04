#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[2]
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

try:
    from .common import ensure_runtime, write_json
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from pysidam_agent.common import ensure_runtime, write_json


def _json_default(value: Any) -> Any:
    try:
        import numpy as np

        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
        if isinstance(value, np.ndarray):
            return value.tolist()
    except Exception:
        pass
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _read_csv(path: Path) -> list[dict[str, Any]]:
    path = Path(path).expanduser()
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def _load_regions(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    regions = payload.get("regions", payload) if isinstance(payload, dict) else payload
    if not isinstance(regions, list):
        raise ValueError("regions JSON must be a list or an object with a 'regions' list")
    return [dict(item) for item in regions]


def _coords_from_rows(rows: list[dict[str, Any]], x_column: str, y_column: str) -> Any:
    import numpy as np

    coords = []
    for idx, row in enumerate(rows, start=1):
        try:
            coords.append([float(row[x_column]), float(row[y_column])])
        except KeyError as exc:
            raise KeyError(f"row {idx} is missing required coordinate column {exc}") from exc
        except ValueError as exc:
            raise ValueError(f"row {idx} has non-numeric coordinates") from exc
    return np.asarray(coords, dtype=float)


def command_recommend_scale(args: argparse.Namespace) -> int:
    from pysidam_agent_core.atom_ai import scale_recommendation

    payload = {
        "tool": "pysidam_agent/atom_ai.py recommend-scale",
        "policy": "Use this before AI atom detection to tune resize_ratio; human-specified detector parameters still take priority.",
        "result": scale_recommendation(
            shape_yx=(args.shape_yx[0], args.shape_yx[1]),
            scan_size_nm_xy=(args.scan_size_nm[0], args.scan_size_nm[1]),
            resize_ratio=args.resize_ratio,
            expected_spacing_nm=args.expected_spacing_nm,
            target_inference_pixel_nm=args.target_inference_pixel_nm,
        ),
    }
    _emit_payload(payload, args.output_json)
    return 0


def command_lattice_qc(args: argparse.Namespace) -> int:
    from pysidam_agent_core.atom_ai import lattice_qc

    rows = _read_csv(Path(args.atoms_csv))
    coords = _coords_from_rows(rows, args.x_column, args.y_column)
    bounds = tuple(args.scan_size_nm) if args.scan_size_nm else None
    result = lattice_qc(
        coords,
        expected_spacing_nm=args.expected_spacing_nm,
        bounds_nm_xy=bounds,
    )
    payload = {
        "tool": "pysidam_agent/atom_ai.py lattice-qc",
        "source_csv": str(Path(args.atoms_csv).expanduser()),
        "coordinate_columns": [args.x_column, args.y_column],
        "result": result,
    }
    _emit_payload(payload, args.output_json)
    return 0 if result["passes"] or args.allow_qc_fail else 2


def command_wipe_regions(args: argparse.Namespace) -> int:
    from pysidam_agent_core.atom_ai import apply_wipe_regions

    rows = _read_csv(Path(args.atoms_csv))
    regions = _load_regions(Path(args.regions_json))
    wiped, summary = apply_wipe_regions(
        rows,
        regions,
        class_key=args.class_key,
        output_key=args.output_key,
        wipe_prefix=args.wipe_prefix,
    )
    if args.output_csv:
        _write_csv(Path(args.output_csv), wiped)
    payload = {
        "tool": "pysidam_agent/atom_ai.py wipe-regions",
        "source_csv": str(Path(args.atoms_csv).expanduser()),
        "regions_json": str(Path(args.regions_json).expanduser()),
        "output_csv": str(Path(args.output_csv).expanduser()) if args.output_csv else "",
        "regions": regions,
        "summary": summary,
        "preview_rows": wiped[:5],
        "policy": "Human-specified wipe regions only exclude marked atoms; remaining AI A/B labels are preserved.",
    }
    _emit_payload(payload, args.output_json)
    return 0


def _emit_payload(payload: dict[str, Any], output_json: str) -> None:
    if output_json:
        write_json(Path(output_json), payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Atom AI scale, lattice-QC, and human wipe helpers for STM/SJTM workflows."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scale = sub.add_parser("recommend-scale", help="Recommend or check AtomDetector resize_ratio scale.")
    scale.add_argument("--shape-yx", nargs=2, type=int, metavar=("NY", "NX"), required=True)
    scale.add_argument("--scan-size-nm", nargs=2, type=float, metavar=("SX", "SY"), required=True)
    scale.add_argument("--resize-ratio", type=float, default=None)
    scale.add_argument("--expected-spacing-nm", type=float, default=None)
    scale.add_argument("--target-inference-pixel-nm", type=float, default=0.026)
    scale.add_argument("--output-json", default="")
    scale.set_defaults(func=command_recommend_scale)

    qc = sub.add_parser("lattice-qc", help="Check whether AI-detected atoms form an orderly square lattice.")
    qc.add_argument("atoms_csv", help="Atom table with coordinates in nm.")
    qc.add_argument("--x-column", default="x_nm")
    qc.add_argument("--y-column", default="y_nm")
    qc.add_argument("--expected-spacing-nm", type=float, default=None)
    qc.add_argument("--scan-size-nm", nargs=2, type=float, metavar=("SX", "SY"), default=None)
    qc.add_argument("--allow-qc-fail", action="store_true", help="Return exit code 0 even when QC recommends retuning.")
    qc.add_argument("--output-json", default="")
    qc.set_defaults(func=command_lattice_qc)

    wipe = sub.add_parser("wipe-regions", help="Mark human-specified DW/dirty/defect regions as excluded.")
    wipe.add_argument("atoms_csv", help="Atom table with x_nm and y_nm columns.")
    wipe.add_argument("--regions-json", required=True, help="List of x_band/y_band/rectangle/circle/polygon regions.")
    wipe.add_argument("--output-csv", default="", help="CSV path for the wiped atom table.")
    wipe.add_argument("--class-key", default="class")
    wipe.add_argument("--output-key", default="analysis_class")
    wipe.add_argument("--wipe-prefix", default="excluded")
    wipe.add_argument("--output-json", default="")
    wipe.set_defaults(func=command_wipe_regions)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    ensure_runtime(reexec=True)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
