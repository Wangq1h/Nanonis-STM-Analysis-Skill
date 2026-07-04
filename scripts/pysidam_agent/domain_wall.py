#!/usr/bin/env python3
from __future__ import annotations

import argparse
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


def load_numeric_map(path: Path, npz_key: str = "") -> tuple[Any, dict[str, Any]]:
    import numpy as np

    path = Path(path).expanduser()
    suffix = path.suffix.lower()
    source: dict[str, Any] = {"source_file": str(path), "source_suffix": suffix}
    if suffix == ".npy":
        arr = np.asarray(np.load(path), dtype=float)
        source["reader"] = "numpy.load"
        return _ensure_2d(arr), source
    if suffix == ".npz":
        archive = np.load(path)
        key = npz_key or _first_2d_npz_key(archive)
        arr = np.asarray(archive[key], dtype=float)
        source.update({"reader": "numpy.load", "npz_key": key})
        return _ensure_2d(arr), source
    if suffix in {".csv", ".tsv", ".txt"}:
        delimiter = "," if suffix == ".csv" else "\t" if suffix == ".tsv" else None
        arr = np.asarray(np.loadtxt(path, delimiter=delimiter), dtype=float)
        source["reader"] = "numpy.loadtxt"
        return _ensure_2d(arr), source
    raise ValueError(f"Unsupported numeric map suffix: {suffix}")


def write_mask_outputs(
    output_dir: Path,
    masks: dict[str, Any],
    source: dict[str, Any],
    policy: dict[str, Any],
    stats: dict[str, Any] | None = None,
    metric_source: dict[str, Any] | None = None,
    command: str = "build-masks",
) -> dict[str, str]:
    import numpy as np

    output_dir = Path(output_dir).expanduser()
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    masks_npz = data_dir / "domain_wall_masks.npz"
    np.savez_compressed(
        masks_npz,
        x_nm_yx=np.asarray(masks["x_nm_yx"], dtype=float),
        y_nm_yx=np.asarray(masks["y_nm_yx"], dtype=float),
        broad_dw_mask=np.asarray(masks["broad_dw_mask"], dtype=bool),
        on_dw_mask=np.asarray(masks["on_dw_mask"], dtype=bool),
        near_dw_mask=np.asarray(masks["near_dw_mask"], dtype=bool),
        away_mask=np.asarray(masks["away_mask"], dtype=bool),
        analysis_mask=np.asarray(masks["analysis_mask"], dtype=bool),
    )
    report = {
        "schema_version": 1,
        "tool": f"pysidam_agent/domain_wall.py {command}",
        "analysis": {
            "workflow": "Domain Wall broad/on/near/away mask package",
            "policy": policy.get("mode", ""),
            "message": policy.get("message", ""),
            "notes": [
                "Human-specified Domain Wall regions take priority over agent proposals.",
                "away_mask excludes the full broad DW region even when on_dw_mask is refined.",
            ],
        },
        "source": source,
        "metric_source": metric_source or {},
        "parameters": masks["metadata"],
        "counts": masks["counts"],
        "stats": stats or {},
        "outputs": {
            "masks_npz": str(masks_npz),
        },
    }
    report_json = output_dir / "report.json"
    write_json(report_json, report)
    return {"report_json": str(report_json), "masks_npz": str(masks_npz)}


def load_masks_npz(path: Path) -> dict[str, Any]:
    import numpy as np

    archive = np.load(Path(path).expanduser())
    out = {
        "x_nm_yx": np.asarray(archive["x_nm_yx"], dtype=float),
        "y_nm_yx": np.asarray(archive["y_nm_yx"], dtype=float),
        "broad_dw_mask": np.asarray(archive["broad_dw_mask"], dtype=bool),
        "on_dw_mask": np.asarray(archive["on_dw_mask"], dtype=bool),
        "near_dw_mask": np.asarray(archive["near_dw_mask"], dtype=bool),
        "away_mask": np.asarray(archive["away_mask"], dtype=bool),
        "analysis_mask": np.asarray(archive["analysis_mask"], dtype=bool),
    }
    out["counts"] = {
        "broad_dw": int(np.count_nonzero(out["broad_dw_mask"])),
        "on_dw": int(np.count_nonzero(out["on_dw_mask"])),
        "near_dw": int(np.count_nonzero(out["near_dw_mask"])),
        "away": int(np.count_nonzero(out["away_mask"])),
        "analysis": int(np.count_nonzero(out["analysis_mask"])),
    }
    out["metadata"] = {
        "shape_yx": [int(x) for x in out["on_dw_mask"].shape],
        "source_masks_npz": str(Path(path).expanduser()),
    }
    return out


def command_policy(args: argparse.Namespace) -> int:
    from pysidam_agent_core.domain_wall import domain_wall_policy

    regions = _load_regions(Path(args.regions_json)) if args.regions_json else None
    payload = {
        "tool": "pysidam_agent/domain_wall.py policy",
        "regions_json": str(Path(args.regions_json).expanduser()) if args.regions_json else "",
        "result": domain_wall_policy(regions=regions, allow_agent_proposal=args.allow_agent_proposal),
    }
    _emit_payload(payload, args.output_json)
    return 0


def command_build_masks(args: argparse.Namespace) -> int:
    from pysidam_agent_core.domain_wall import build_domain_wall_masks, domain_wall_policy

    regions = _load_regions(Path(args.regions_json))
    refine_map = None
    refine_source: dict[str, Any] = {}
    if args.refine_map:
        refine_map, refine_source = load_numeric_map(Path(args.refine_map), npz_key=args.refine_npz_key)
    masks = build_domain_wall_masks(
        shape_yx=(args.shape_yx[0], args.shape_yx[1]),
        scan_size_nm_xy=(args.scan_size_nm[0], args.scan_size_nm[1]),
        regions=regions,
        near_width_nm=args.near_width_nm,
        edge_exclude_nm=args.edge_exclude_nm,
        refine_map_yx=refine_map,
        refine_percentile=args.refine_percentile,
        refine_mode=args.refine_mode,
    )
    policy = domain_wall_policy(regions=regions, allow_agent_proposal=False)
    outputs = write_mask_outputs(
        output_dir=Path(args.output_dir),
        masks=masks,
        source={"regions_json": str(Path(args.regions_json).expanduser()), "regions": regions},
        policy=policy,
        metric_source=refine_source,
        command="build-masks",
    )
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


def command_stats(args: argparse.Namespace) -> int:
    from pysidam_agent_core.domain_wall import build_domain_wall_masks, domain_wall_policy, region_stats

    metric, metric_source = load_numeric_map(Path(args.map), npz_key=args.npz_key)
    if args.masks_npz:
        masks = load_masks_npz(Path(args.masks_npz))
        policy = {"mode": "prebuilt_masks", "message": "Using a prebuilt Domain Wall mask package."}
        source = {"masks_npz": str(Path(args.masks_npz).expanduser())}
    else:
        regions = _load_regions(Path(args.regions_json))
        masks = build_domain_wall_masks(
            shape_yx=metric.shape,
            scan_size_nm_xy=(args.scan_size_nm[0], args.scan_size_nm[1]),
            regions=regions,
            near_width_nm=args.near_width_nm,
            edge_exclude_nm=args.edge_exclude_nm,
            refine_map_yx=metric if args.refine_with_metric else None,
            refine_percentile=args.refine_percentile,
            refine_mode=args.refine_mode,
        )
        policy = domain_wall_policy(regions=regions, allow_agent_proposal=False)
        source = {"regions_json": str(Path(args.regions_json).expanduser()), "regions": regions}
    stats = region_stats(metric, masks)
    stats["metric_name"] = args.metric_name
    outputs = write_mask_outputs(
        output_dir=Path(args.output_dir),
        masks=masks,
        source=source,
        policy=policy,
        stats=stats,
        metric_source=metric_source,
        command="stats",
    )
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


def _ensure_2d(arr: Any) -> Any:
    import numpy as np

    data = np.asarray(arr, dtype=float)
    if data.ndim != 2:
        raise ValueError(f"numeric map must be 2D, got shape {data.shape}")
    return data


def _first_2d_npz_key(archive: Any) -> str:
    import numpy as np

    for key in archive.files:
        arr = np.asarray(archive[key])
        if arr.ndim == 2 and np.issubdtype(arr.dtype, np.number):
            return str(key)
    raise ValueError("NPZ does not contain a numeric 2D map; pass --npz-key")


def _load_regions(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    regions = payload.get("regions", payload) if isinstance(payload, dict) else payload
    if not isinstance(regions, list):
        raise ValueError("regions JSON must be a list or an object with a 'regions' list")
    return [dict(item) for item in regions]


def _emit_payload(payload: dict[str, Any], output_json: str) -> None:
    if output_json:
        write_json(Path(output_json), payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Domain Wall region policy, mask, and map-stat helpers.")
    sub = parser.add_subparsers(dest="command", required=True)

    policy = sub.add_parser("policy", help="Check whether DW regions are human-specified or require asking.")
    policy.add_argument("--regions-json", default="")
    policy.add_argument("--allow-agent-proposal", action="store_true")
    policy.add_argument("--output-json", default="")
    policy.set_defaults(func=command_policy)

    build = sub.add_parser("build-masks", help="Build broad/on/near/away Domain Wall masks from regions.")
    build.add_argument("--shape-yx", nargs=2, type=int, metavar=("NY", "NX"), required=True)
    build.add_argument("--scan-size-nm", nargs=2, type=float, metavar=("SX", "SY"), required=True)
    build.add_argument("--regions-json", required=True)
    build.add_argument("--near-width-nm", type=float, default=0.0)
    build.add_argument("--edge-exclude-nm", type=float, default=0.0)
    build.add_argument("--refine-map", default="", help="Optional 2D map used to refine on-DW inside the broad strip.")
    build.add_argument("--refine-npz-key", default="")
    build.add_argument("--refine-percentile", type=float, default=None)
    build.add_argument("--refine-mode", choices=("above", "below"), default="above")
    build.add_argument("--output-dir", required=True)
    build.set_defaults(func=command_build_masks)

    stats = sub.add_parser("stats", help="Compute DW/near/away statistics for one 2D map.")
    stats.add_argument("map", help="Input .npy, .npz, .csv, .tsv, or .txt 2D metric map.")
    stats.add_argument("--npz-key", default="")
    stats.add_argument("--masks-npz", default="", help="Use an existing domain_wall_masks.npz package.")
    stats.add_argument("--regions-json", default="", help="Regions JSON when not using --masks-npz.")
    stats.add_argument("--scan-size-nm", nargs=2, type=float, metavar=("SX", "SY"))
    stats.add_argument("--near-width-nm", type=float, default=0.0)
    stats.add_argument("--edge-exclude-nm", type=float, default=0.0)
    stats.add_argument("--refine-with-metric", action="store_true")
    stats.add_argument("--refine-percentile", type=float, default=None)
    stats.add_argument("--refine-mode", choices=("above", "below"), default="above")
    stats.add_argument("--metric-name", default="metric")
    stats.add_argument("--output-dir", required=True)
    stats.set_defaults(func=command_stats)
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if getattr(args, "command", "") == "stats" and not args.masks_npz:
        if not args.regions_json:
            raise SystemExit("stats requires --regions-json when --masks-npz is not provided")
        if not args.scan_size_nm:
            raise SystemExit("stats requires --scan-size-nm when --masks-npz is not provided")


def main() -> int:
    ensure_runtime(reexec=True)
    parser = build_parser()
    args = parser.parse_args()
    _validate_args(args)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
