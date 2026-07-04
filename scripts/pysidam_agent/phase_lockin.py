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


def parse_q_args(items: list[str]) -> dict[str, tuple[float, float]]:
    out: dict[str, tuple[float, float]] = {}
    for idx, raw in enumerate(items, start=1):
        if "=" in raw:
            label, value = raw.split("=", 1)
            label = label.strip() or f"q{idx}"
        else:
            label, value = f"q{idx}", raw
        parts = [part.strip() for part in value.split(",")]
        if len(parts) != 2:
            raise argparse.ArgumentTypeError("--q expects LABEL=QX,QY or QX,QY")
        out[label] = (float(parts[0]), float(parts[1]))
    if not out:
        raise argparse.ArgumentTypeError("at least one --q is required")
    return out


def parse_float_list(raw: str) -> list[float]:
    return [float(part.strip()) for part in str(raw).replace(";", ",").split(",") if part.strip()]


def load_input_map(args: argparse.Namespace) -> tuple[Any, tuple[float, float], dict[str, Any]]:
    import numpy as np

    path = Path(args.input).expanduser()
    suffix = path.suffix.lower()
    source_info: dict[str, Any] = {"source_file": str(path), "source_suffix": suffix}

    if suffix == ".npy":
        arr = np.asarray(np.load(path), dtype=float)
        scan_size = _scan_size_from_args(args)
        source_info["reader"] = "numpy.load"
        return _ensure_2d(arr), scan_size, source_info

    if suffix == ".npz":
        archive = np.load(path)
        key = args.npz_key or _first_2d_npz_key(archive)
        arr = np.asarray(archive[key], dtype=float)
        scan_size = _scan_size_from_args(args, archive=archive)
        source_info.update({"reader": "numpy.load", "npz_key": key})
        return _ensure_2d(arr), scan_size, source_info

    if suffix in {".csv", ".tsv", ".txt"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        arr = np.asarray(np.loadtxt(path, delimiter=delimiter), dtype=float)
        scan_size = _scan_size_from_args(args)
        source_info["reader"] = "numpy.loadtxt"
        return _ensure_2d(arr), scan_size, source_info

    if suffix == ".sxm":
        from pysidam.core.nanonis_io import read_nanonis_file
        from pysidam_agent_core.bragg_phase import scan_size_nm_xy, selected_sxm_map

        nf = read_nanonis_file(path)
        obj = nf.obj
        header = getattr(obj, "header", {}) or {}
        signals = getattr(obj, "signals", {}) or {}
        if args.channel not in signals:
            raise KeyError(f"{path.name}: channel {args.channel!r} not found; available={list(signals.keys())}")
        arr = selected_sxm_map(signals, channel=args.channel, direction=args.direction, header=header)
        scan_size = tuple(args.scan_size_nm) if args.scan_size_nm else scan_size_nm_xy(header, default=args.default_scan_size_nm)
        source_info.update({"reader": "pysidam.core.nanonis_io.read_nanonis_file", "channel": args.channel, "direction": args.direction})
        return _ensure_2d(arr), scan_size, source_info

    if suffix == ".3ds":
        from pysidam.core.dataset_utils import prepare_3ds_dataset
        from pysidam.core.nanonis_io import read_nanonis_file

        nf = read_nanonis_file(path)
        obj = nf.obj
        signals = getattr(obj, "signals", {}) or {}
        header = getattr(obj, "header", {}) or {}
        _, _, scan_size_nm, topo = prepare_3ds_dataset(
            signals,
            header=header,
            divider=1.0,
            spectral_only=False,
        )
        arr, topo_key = _select_topography(topo, args.channel)
        scan_size = tuple(args.scan_size_nm) if args.scan_size_nm else _scan_size_pair(scan_size_nm)
        source_info.update(
            {
                "reader": "pysidam.core.nanonis_io.read_nanonis_file + pysidam.core.dataset_utils.prepare_3ds_dataset",
                "map_source": "topography",
                "topography_key": topo_key,
                "divider": 1.0,
            }
        )
        return _ensure_2d(arr), scan_size, source_info

    raise ValueError(f"Unsupported input suffix for phase lock-in: {suffix}")


def write_outputs(
    output_dir: Path,
    input_map: Any,
    processed_map: Any,
    package: dict[str, Any],
    source_info: dict[str, Any],
    preprocessing: dict[str, Any],
) -> dict[str, str]:
    import numpy as np

    output_dir = Path(output_dir).expanduser()
    data_dir = output_dir / "data"
    table_dir = output_dir / "tables"
    data_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)

    maps_npz = data_dir / "phase_lockin_maps.npz"
    np.savez_compressed(
        maps_npz,
        input_map_yx=np.asarray(input_map),
        processed_map_yx=np.asarray(processed_map),
        **package["maps"],
    )
    stats_csv = table_dir / "phase_lockin_stats.csv"
    _write_csv(stats_csv, package.get("stats_rows", []))

    report = {
        "schema_version": 1,
        "tool": "pysidam_agent/phase_lockin.py run",
        "analysis": {
            "workflow": "clean 2D lock-in extraction",
            "lockin_engine": package["metadata"]["lockin_engine"],
            "policy": "Downstream agents consume this package instead of reimplementing lock-in demodulation.",
        },
        "source": source_info,
        "data_contract": {
            "input_shape_yx": [int(x) for x in np.asarray(input_map).shape],
            "processed_shape_yx": [int(x) for x in np.asarray(processed_map).shape],
            "scan_size_nm_xy": package["metadata"]["scan_size_nm_xy"],
        },
        "preprocessing": preprocessing,
        "parameters": package["metadata"],
        "outputs": {
            "maps_npz": str(maps_npz),
            "stats_csv": str(stats_csv),
        },
    }
    report_json = output_dir / "report.json"
    write_json(report_json, report)
    return {"report_json": str(report_json), "maps_npz": str(maps_npz), "stats_csv": str(stats_csv)}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        if not keys:
            f.write("")
            return
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def _ensure_2d(arr: Any) -> Any:
    import numpy as np

    data = np.asarray(arr, dtype=float)
    if data.ndim != 2:
        raise ValueError(f"phase lock-in input must be a 2D map, got shape {data.shape}")
    return data


def _first_2d_npz_key(archive: Any) -> str:
    import numpy as np

    for key in archive.files:
        arr = np.asarray(archive[key])
        if arr.ndim == 2 and np.issubdtype(arr.dtype, np.number):
            return str(key)
    raise ValueError("NPZ does not contain a numeric 2D map; pass --npz-key")


def _scan_size_from_args(args: argparse.Namespace, archive: Any | None = None) -> tuple[float, float]:
    import numpy as np

    if args.scan_size_nm:
        return tuple(args.scan_size_nm)
    if archive is not None:
        for key in ("scan_size_nm_xy", "scan_size_nm"):
            if key in archive:
                val = np.asarray(archive[key], dtype=float).ravel()
                if val.size >= 2:
                    return (float(val[0]), float(val[1]))
                if val.size == 1:
                    return (float(val[0]), float(val[0]))
    raise ValueError("--scan-size-nm SX SY is required for array/table inputs without scan_size_nm metadata")


def _scan_size_pair(value: Any) -> tuple[float, float]:
    import numpy as np

    arr = np.asarray(value, dtype=float).ravel()
    if arr.size >= 2:
        return (float(arr[0]), float(arr[1]))
    if arr.size == 1:
        return (float(arr[0]), float(arr[0]))
    raise ValueError("could not determine scan size")


def _select_topography(topo: Any, requested: str) -> tuple[Any, str]:
    if isinstance(topo, dict):
        if requested in topo:
            return topo[requested], requested
        for key, value in topo.items():
            return value, str(key)
        raise ValueError("3ds topography dictionary is empty")
    return topo, "topography"


def command_run(args: argparse.Namespace) -> int:
    import json
    import numpy as np
    from pysidam_agent_core.phase_lockin import run_pysidam_lockin

    input_map, scan_size, source_info = load_input_map(args)
    preprocessing: dict[str, Any] = {"steps": []}
    processed_map = input_map
    if args.preprocess_topography:
        from pysidam_agent_core.bragg_phase import preprocess_topography

        processed_map, preprocessing = preprocess_topography(input_map)

    package = run_pysidam_lockin(
        processed_map,
        q_vectors_xy_cycles_per_nm=parse_q_args(args.q),
        scan_size_nm_xy=scan_size,
        sigma_px=args.sigma_px,
        window=args.window,
        threshold_fractions=parse_float_list(args.thresholds),
    )
    outputs = write_outputs(
        output_dir=Path(args.output_dir),
        input_map=input_map,
        processed_map=processed_map,
        package=package,
        source_info=source_info,
        preprocessing=preprocessing,
    )
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clean PySIDAM 2D lock-in extraction tool.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Run PySIDAM 2D lock-in on one input map.")
    run.add_argument("input", help="Input .sxm, .3ds, .npy, .npz, .csv, .tsv, or .txt 2D map source.")
    run.add_argument("--q", action="append", required=True, help="Q vector in cycles/nm as LABEL=QX,QY or QX,QY. Repeat for q1/q2.")
    run.add_argument("--output-dir", required=True)
    run.add_argument("--scan-size-nm", nargs=2, type=float, metavar=("SX", "SY"))
    run.add_argument("--npz-key", default="")
    run.add_argument("--channel", default="Z")
    run.add_argument("--direction", default="forward")
    run.add_argument("--default-scan-size-nm", type=float, default=100.0)
    run.add_argument("--sigma-px", type=float, default=3.0)
    run.add_argument("--window", default="hann")
    run.add_argument("--thresholds", default="0.1,0.2,0.3")
    run.add_argument("--preprocess-topography", action="store_true")
    run.set_defaults(func=command_run)
    return parser


def main() -> int:
    ensure_runtime(reexec=True)
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
