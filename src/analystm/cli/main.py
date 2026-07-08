from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

from analystm import __version__


def _json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _write_json(path: str | None, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n"
    if path:
        out = Path(path).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _finite_summary(array: Any) -> dict[str, Any]:
    arr = np.asarray(array)
    out: dict[str, Any] = {"shape": [int(x) for x in arr.shape], "dtype": str(arr.dtype)}
    if arr.size == 0:
        out.update({"finite_count": 0, "nan_count": 0})
        return out
    try:
        vals = np.asarray(arr, dtype=float)
    except Exception:
        out["numeric"] = False
        return out
    finite = np.isfinite(vals)
    out["numeric"] = True
    out["finite_count"] = int(np.count_nonzero(finite))
    out["nan_count"] = int(np.count_nonzero(~finite))
    if out["finite_count"]:
        good = vals[finite]
        out["min"] = float(np.nanmin(good))
        out["max"] = float(np.nanmax(good))
        out["mean"] = float(np.nanmean(good))
    return out


def _signals_summary(signals: Any, max_channels: int = 80) -> dict[str, Any]:
    if not isinstance(signals, dict):
        return {}
    out: dict[str, Any] = {}
    for idx, (name, raw) in enumerate(signals.items()):
        if idx >= max_channels:
            out["_truncated"] = True
            out["_channel_count"] = len(signals)
            break
        if isinstance(raw, dict):
            out[str(name)] = {str(k): _finite_summary(v) for k, v in raw.items()}
        else:
            out[str(name)] = _finite_summary(raw)
    return out


def _best_channel(signals: dict[str, Any], requested: str, fallbacks: tuple[str, ...]) -> str:
    names = [str(k) for k in signals.keys()]
    if requested and requested in signals:
        return requested
    low_req = requested.strip().lower()
    for name in names:
        if low_req and (name.lower() == low_req or name.lower().startswith(low_req)):
            return name
    for token in fallbacks:
        for name in names:
            if token.lower() in name.lower():
                return name
    return names[0] if names else ""


def _numeric_xy_from_signals(signals: dict[str, Any], x_channel: str, y_channel: str) -> tuple[np.ndarray, np.ndarray, str, str]:
    x_name = _best_channel(signals, x_channel, ("bias", "voltage", "Bias calc"))
    y_name = _best_channel(signals, y_channel, ("LI Demod 1 X", "LT Demod 1 X", "Current", "dI/dV"))
    if not x_name or not y_name:
        raise ValueError("Could not identify numeric x/y channels")
    x = np.asarray(signals[x_name], dtype=float).ravel()
    y = np.asarray(signals[y_name], dtype=float).ravel()
    n = min(x.size, y.size)
    if n == 0:
        raise ValueError("Selected channels are empty")
    return x[:n], y[:n], x_name, y_name


def cmd_read(args: argparse.Namespace) -> int:
    from analystm.io import build_read_parameters, load_signals

    signals, reader = load_signals(args.path)
    payload = {
        "schema_version": 1,
        "path": str(Path(args.path).expanduser()),
        "reader": reader,
        "read_parameters": build_read_parameters(divider=args.divider, divider_explicit=args.divider_explicit, quick=args.quick),
        "signals": _signals_summary(signals, max_channels=args.max_channels),
    }
    _write_json(args.output_json, payload)
    return 0


def cmd_plot_spectrum(args: argparse.Namespace) -> int:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from analystm.io import load_signals

    signals, reader = load_signals(args.path)
    x, y, x_name, y_name = _numeric_xy_from_signals(signals, args.x_channel, args.y_channel)
    fig, ax = plt.subplots(figsize=(5.0, 3.4), dpi=180)
    ax.plot(x, y, lw=1.2)
    ax.set_xlabel(x_name)
    ax.set_ylabel(y_name)
    ax.tick_params(direction="in", top=True, right=True)
    fig.tight_layout()
    out = Path(args.output).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    if args.summary_json:
        _write_json(
            args.summary_json,
            {
                "schema_version": 1,
                "path": str(Path(args.path).expanduser()),
                "reader": reader,
                "x_channel": x_name,
                "y_channel": y_name,
                "points": int(min(x.size, y.size)),
                "output": str(out),
            },
        )
    return 0


def cmd_fit_gap(args: argparse.Namespace) -> int:
    from analystm.gap_fitting import fit_gap_model_guarded
    from analystm.io import load_signals

    signals, reader = load_signals(args.path)
    x, y, x_name, y_name = _numeric_xy_from_signals(signals, args.x_channel, args.y_channel)
    result = fit_gap_model_guarded(
        x,
        y,
        model_name=args.model,
        fit_abs_max=args.fit_abs_max,
        fit_max_starts=args.fit_max_starts,
        time_budget_s=args.time_budget_s,
    )
    result.setdefault("inputs", {})
    result["inputs"].update({"path": str(Path(args.path).expanduser()), "reader": reader, "x_channel": x_name, "y_channel": y_name})
    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(str(out_dir / "report.json"), result)
    return 0


def _load_map(path: str) -> np.ndarray:
    p = Path(path).expanduser()
    if p.suffix.lower() == ".npy":
        return np.asarray(np.load(p), dtype=float)
    if p.suffix.lower() == ".npz":
        data = np.load(p)
        key = "map" if "map" in data.files else data.files[0]
        return np.asarray(data[key], dtype=float)
    return np.loadtxt(p, delimiter="," if p.suffix.lower() == ".csv" else None)


def _load_npz_array(path: str | Path, key: str, *, fallback_first: bool = False) -> np.ndarray:
    archive = np.load(Path(path).expanduser())
    if key and key in archive.files:
        return np.asarray(archive[key])
    if fallback_first and archive.files:
        return np.asarray(archive[archive.files[0]])
    raise KeyError(f"NPZ key not found: {key}")


def _select_gap_map_cube(cubes: dict[str, Any], requested: str) -> tuple[str, np.ndarray]:
    if not cubes:
        raise ValueError("No spectral 3DS cubes were found for gap-map extraction")
    if requested in cubes:
        return requested, np.asarray(cubes[requested], dtype=float)
    if requested and requested != "cube":
        raise KeyError(f"3DS spectral channel not found: {requested}; available channels: {list(cubes)}")
    if len(cubes) == 1:
        name = next(iter(cubes))
        return str(name), np.asarray(cubes[name], dtype=float)
    raise ValueError(f"Multiple 3DS spectral channels found; specify --cube-key. Available channels: {list(cubes)}")


def _load_gap_map_input(path: str | Path, bias_key: str, cube_key: str) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    in_path = Path(path).expanduser()
    if in_path.suffix.lower() == ".3ds":
        from analystm.dataset_utils import prepare_3ds_dataset
        from analystm.nanonis_io import read_nanonis_file

        nf = read_nanonis_file(in_path)
        grid = nf.obj
        cubes_xyb, bias_mv, scan_size_nm, _topo_xy = prepare_3ds_dataset(
            getattr(grid, "signals", {}),
            header=getattr(grid, "header", None),
            bias=getattr(grid, "bias", None),
            divider=1.0,
        )
        selected_channel, cube_xyb = _select_gap_map_cube(cubes_xyb, cube_key)
        bias_arr = np.asarray(bias_mv, dtype=float).ravel()
        cube_yxb = np.transpose(np.asarray(cube_xyb, dtype=float), (1, 0, 2))
        if bias_arr.size == cube_yxb.shape[2]:
            order = np.argsort(bias_arr)
            bias_arr = bias_arr[order]
            cube_yxb = cube_yxb[:, :, order]
        meta = {
            "path": str(in_path),
            "format": ".3ds",
            "reader": "analystm.nanonis_io.read_nanonis_file -> analystm.dataset_utils.prepare_3ds_dataset",
            "bias_key": str(bias_key or "bias"),
            "cube_key": str(cube_key or ""),
            "selected_channel": selected_channel,
            "available_channels": list(cubes_xyb),
            "scan_size_nm": float(scan_size_nm),
            "transforms": ["transpose internal (x, y, bias) to report-facing (y, x, bias)", "sort bias axis ascending"],
        }
        return bias_arr, np.ascontiguousarray(cube_yxb, dtype=float), meta

    bias = _load_npz_array(in_path, bias_key)
    cube = _load_npz_array(in_path, cube_key)
    meta = {"path": str(in_path), "format": in_path.suffix.lower() or "npz", "bias_key": bias_key, "cube_key": cube_key}
    return np.asarray(bias, dtype=float), np.asarray(cube, dtype=float), meta


def _parse_q(values: list[str]) -> dict[str, tuple[float, float]]:
    out: dict[str, tuple[float, float]] = {}
    for idx, item in enumerate(values or []):
        label = f"q{idx + 1}"
        raw = item
        if "=" in item:
            label, raw = item.split("=", 1)
        parts = [float(x) for x in raw.replace(";", ",").split(",") if x.strip()]
        if len(parts) != 2:
            raise ValueError(f"q vector must contain qx,qy: {item}")
        out[label.strip() or f"q{idx + 1}"] = (parts[0], parts[1])
    return out


def _read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).expanduser().open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_csv_rows(path: str | Path, rows: list[dict[str, Any]]) -> None:
    out = Path(path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                keys.append(key)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def _coords_from_rows(rows: list[dict[str, Any]], x_column: str, y_column: str) -> np.ndarray:
    coords = []
    for idx, row in enumerate(rows, start=1):
        try:
            coords.append([float(row[x_column]), float(row[y_column])])
        except KeyError as exc:
            raise KeyError(f"row {idx} is missing required coordinate column {exc}") from exc
        except ValueError as exc:
            raise ValueError(f"row {idx} has non-numeric coordinates") from exc
    return np.asarray(coords, dtype=float)


def _load_regions(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    regions = payload.get("regions", payload) if isinstance(payload, dict) else payload
    if not isinstance(regions, list):
        raise ValueError("regions JSON must be a list or an object with a 'regions' list")
    return [dict(item) for item in regions]


def _write_domain_wall_outputs(
    output_dir: str | Path,
    masks: dict[str, Any],
    source: dict[str, Any],
    policy: dict[str, Any],
    stats: dict[str, Any] | None = None,
    metric_source: dict[str, Any] | None = None,
    command: str = "build-masks",
) -> dict[str, str]:
    out_dir = Path(output_dir).expanduser()
    data_dir = out_dir / "data"
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
        "tool": f"analystm domain-wall {command}",
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
        "outputs": {"masks_npz": str(masks_npz)},
    }
    report_json = out_dir / "report.json"
    _write_json(str(report_json), report)
    return {"report_json": str(report_json), "masks_npz": str(masks_npz)}


def _first_2d_npz_key(archive: Any) -> str:
    for key in archive.files:
        arr = np.asarray(archive[key])
        if arr.ndim == 2 and np.issubdtype(arr.dtype, np.number):
            return str(key)
    raise ValueError("NPZ does not contain a numeric 2D map; pass --npz-key")


def cmd_phase_lockin(args: argparse.Namespace) -> int:
    from analystm.phase_lockin import run_lockin_phase

    input_path = Path(args.path).expanduser()
    image = _load_map(args.path)
    q_vectors = _parse_q(args.q)
    scan_size_nm_xy = (float(args.scan_size_nm[0]), float(args.scan_size_nm[1]))
    package = run_lockin_phase(
        image,
        q_vectors_xy_cycles_per_nm=q_vectors,
        scan_size_nm_xy=scan_size_nm_xy,
        sigma_px=args.sigma_px,
        window=args.window,
        threshold_fractions=args.threshold,
    )
    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_dir / "phase_lockin_maps.npz", **package["maps"])
    with (out_dir / "phase_lockin_stats.csv").open("w", newline="", encoding="utf-8") as handle:
        rows = package["stats_rows"]
        fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else ["q_label"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "schema_version": 1,
        "tool": "analystm phase-lockin",
        "input": {
            "path": str(input_path),
            "shape_yx": [int(x) for x in np.asarray(image).shape],
            "reader": "_load_map",
        },
        "analysis": {
            "workflow": "clean 2D lock-in extraction",
            "lockin_engine": package["metadata"]["lockin_engine"],
            "policy": "Use the AnalySTM public lock-in API and preserve phase, amplitude, complex, and mask outputs.",
        },
        "parameters": {
            "q_vectors_xy_cycles_per_nm": {label: [float(v[0]), float(v[1])] for label, v in q_vectors.items()},
            "scan_size_nm_xy": [float(scan_size_nm_xy[0]), float(scan_size_nm_xy[1])],
            "sigma_px": float(args.sigma_px),
            "window": args.window,
            "threshold_fractions": [float(x) for x in args.threshold],
        },
        "metadata": package["metadata"],
        "outputs": {
            "maps": "phase_lockin_maps.npz",
            "maps_npz": "phase_lockin_maps.npz",
            "stats_csv": "phase_lockin_stats.csv",
        },
    }
    _write_json(str(out_dir / "report.json"), report)
    return 0


def cmd_bragg(args: argparse.Namespace) -> int:
    from analystm.bragg_phase import q_selection_policy

    if args.bragg_command == "policy":
        user_q = [0.0, 0.0] if args.user_q else None
        user_roi = {} if args.user_roi else None
        _write_json(args.output_json, q_selection_policy(user_q=user_q, user_roi=user_roi, allow_agent_search=args.allow_agent_search))
        return 0
    raise SystemExit("bragg currently supports: policy")


def cmd_atom(args: argparse.Namespace) -> int:
    from analystm.atom_ai import apply_wipe_regions, lattice_qc, scale_recommendation

    if args.atom_command == "recommend-scale":
        _write_json(
            args.output_json,
            {
                "tool": "analystm atom recommend-scale",
                "result": scale_recommendation(
                    shape_yx=(args.shape_yx[0], args.shape_yx[1]),
                    scan_size_nm_xy=(args.scan_size_nm[0], args.scan_size_nm[1]),
                    resize_ratio=args.resize_ratio,
                    expected_spacing_nm=args.expected_spacing_nm,
                    target_inference_pixel_nm=args.target_inference_pixel_nm,
                ),
            },
        )
        return 0
    if args.atom_command == "lattice-qc":
        rows = _read_csv_rows(args.atoms_csv)
        coords = _coords_from_rows(rows, args.x_column, args.y_column)
        bounds = tuple(args.scan_size_nm) if args.scan_size_nm else None
        result = lattice_qc(coords, expected_spacing_nm=args.expected_spacing_nm, bounds_nm_xy=bounds)
        _write_json(
            args.output_json,
            {
                "tool": "analystm atom lattice-qc",
                "source_csv": str(Path(args.atoms_csv).expanduser()),
                "coordinate_columns": [args.x_column, args.y_column],
                "result": result,
            },
        )
        return 0 if result["passes"] or args.allow_qc_fail else 2
    if args.atom_command == "wipe-regions":
        rows = _read_csv_rows(args.atoms_csv)
        regions = _load_regions(args.regions_json)
        wiped, summary = apply_wipe_regions(
            rows,
            regions,
            class_key=args.class_key,
            output_key=args.output_key,
            wipe_prefix=args.wipe_prefix,
        )
        if args.output_csv:
            _write_csv_rows(args.output_csv, wiped)
        _write_json(
            args.output_json,
            {
                "tool": "analystm atom wipe-regions",
                "source_csv": str(Path(args.atoms_csv).expanduser()),
                "regions_json": str(Path(args.regions_json).expanduser()),
                "output_csv": str(Path(args.output_csv).expanduser()) if args.output_csv else "",
                "regions": regions,
                "summary": summary,
                "preview_rows": wiped[:5],
                "policy": "Human-specified wipe regions only exclude marked atoms; remaining AI A/B labels are preserved.",
            },
        )
        return 0
    raise SystemExit("atom supports: recommend-scale, lattice-qc, wipe-regions")


def cmd_domain_wall(args: argparse.Namespace) -> int:
    from analystm.domain_wall import build_domain_wall_masks, domain_wall_policy, region_stats

    if args.domain_wall_command == "policy":
        regions = _load_regions(args.regions_json) if args.regions_json else None
        _write_json(
            args.output_json,
            {
                "tool": "analystm domain-wall policy",
                "regions_json": str(Path(args.regions_json).expanduser()) if args.regions_json else "",
                "result": domain_wall_policy(regions=regions, allow_agent_proposal=args.allow_agent_proposal),
            },
        )
        return 0
    if args.domain_wall_command == "build-masks":
        regions = _load_regions(args.regions_json)
        refine_map = _load_map(args.refine_map) if args.refine_map else None
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
        outputs = _write_domain_wall_outputs(
            output_dir=args.output_dir,
            masks=masks,
            source={"regions_json": str(Path(args.regions_json).expanduser()), "regions": regions},
            policy=domain_wall_policy(regions=regions, allow_agent_proposal=False),
            metric_source={"refine_map": str(Path(args.refine_map).expanduser())} if args.refine_map else {},
            command="build-masks",
        )
        _write_json(args.output_json, outputs)
        return 0
    if args.domain_wall_command == "stats":
        metric = _load_map(args.map)
        if args.masks_npz:
            archive = np.load(Path(args.masks_npz).expanduser())
            masks = {
                "x_nm_yx": np.asarray(archive["x_nm_yx"], dtype=float),
                "y_nm_yx": np.asarray(archive["y_nm_yx"], dtype=float),
                "broad_dw_mask": np.asarray(archive["broad_dw_mask"], dtype=bool),
                "on_dw_mask": np.asarray(archive["on_dw_mask"], dtype=bool),
                "near_dw_mask": np.asarray(archive["near_dw_mask"], dtype=bool),
                "away_mask": np.asarray(archive["away_mask"], dtype=bool),
                "analysis_mask": np.asarray(archive["analysis_mask"], dtype=bool),
                "metadata": {"shape_yx": [int(x) for x in metric.shape], "source_masks_npz": str(Path(args.masks_npz).expanduser())},
                "counts": {},
            }
            mask_keys = {
                "broad_dw": "broad_dw_mask",
                "on_dw": "on_dw_mask",
                "near_dw": "near_dw_mask",
                "away": "away_mask",
                "analysis": "analysis_mask",
            }
            for count_key, mask_key in mask_keys.items():
                masks["counts"][count_key] = int(np.count_nonzero(masks[mask_key]))
            source = {"masks_npz": str(Path(args.masks_npz).expanduser())}
            policy = {"mode": "prebuilt_masks", "message": "Using a prebuilt Domain Wall mask package."}
        else:
            if not args.regions_json or not args.scan_size_nm:
                raise ValueError("stats requires --regions-json and --scan-size-nm when --masks-npz is not provided")
            regions = _load_regions(args.regions_json)
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
            source = {"regions_json": str(Path(args.regions_json).expanduser()), "regions": regions}
            policy = domain_wall_policy(regions=regions, allow_agent_proposal=False)
        stats = region_stats(metric, masks)
        stats["metric_name"] = args.metric_name
        outputs = _write_domain_wall_outputs(
            output_dir=args.output_dir,
            masks=masks,
            source=source,
            policy=policy,
            stats=stats,
            metric_source={"source_file": str(Path(args.map).expanduser())},
            command="stats",
        )
        _write_json(args.output_json, outputs)
        return 0
    raise SystemExit("domain-wall supports: policy, build-masks, stats")


def _write_summary_csv(path: str | Path, row: dict[str, Any]) -> None:
    out = Path(path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)


def _write_table_csv(path: str | Path, columns: dict[str, Any]) -> None:
    out = Path(path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    arrays = {str(key): np.asarray(value).ravel() for key, value in columns.items()}
    n_rows = max((arr.size for arr in arrays.values()), default=0)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(arrays.keys()))
        writer.writeheader()
        for idx in range(n_rows):
            writer.writerow({key: (arr[idx].item() if idx < arr.size and hasattr(arr[idx], "item") else (arr[idx] if idx < arr.size else "")) for key, arr in arrays.items()})


def _load_keyed_array(path: str | Path, key: str = "", *, fallback_first: bool = True) -> np.ndarray:
    p = Path(path).expanduser()
    if p.suffix.lower() == ".npz":
        return _load_npz_array(p, key, fallback_first=fallback_first)
    if p.suffix.lower() == ".npy":
        return np.asarray(np.load(p))
    return _load_map(str(p))


def _fft_filter_regions_from_args(args: argparse.Namespace) -> list[dict[str, Any]]:
    regions: list[dict[str, Any]] = []
    for vals in getattr(args, "circle", None) or []:
        regions.append({"shape": "circle", "center": [float(vals[0]), float(vals[1])], "radius": float(vals[2])})
    for vals in getattr(args, "rect", None) or []:
        regions.append({"shape": "rect", "bounds": [float(vals[0]), float(vals[1]), float(vals[2]), float(vals[3])]})
    return regions


def _load_json_argument(value: str) -> Any:
    if not value:
        return None
    path = Path(value).expanduser()
    text = path.read_text(encoding="utf-8") if path.exists() else value
    return json.loads(text)


def _load_int_map_argument(value: str) -> dict[int, int] | None:
    raw = _load_json_argument(value)
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("peak-count-map must be a JSON object mapping row index to peak count")
    return {int(k): int(v) for k, v in raw.items()}


def _load_center_map_argument(value: str) -> dict[int, list[float]] | None:
    raw = _load_json_argument(value)
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("manual-init-centers must be a JSON object mapping row index to center list")
    return {int(k): [float(x) for x in np.asarray(v, dtype=float).ravel()] for k, v in raw.items()}


def cmd_gap_map(args: argparse.Namespace) -> int:
    from analystm.gap_map import extract_gap_map

    bias, cube, input_meta = _load_gap_map_input(args.path, args.bias_key, args.cube_key)
    package = extract_gap_map(
        bias,
        cube,
        left_range=(args.left_window[0], args.left_window[1]),
        right_range=(args.right_window[0], args.right_window[1]),
        interp_factor=args.interp_factor,
        interp_kind=args.interp_kind,
        smooth_param=args.smooth_param,
        smooth_method=args.smooth_method,
    )
    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_dir / "gap_map_outputs.npz",
        left_peak_mV=package["left_peak_mV"],
        right_peak_mV=package["right_peak_mV"],
        gap_map_mV=package["gap_map_mV"],
        status_map=package["status_map"],
    )
    _write_summary_csv(out_dir / "gap_map_summary.csv", package["summary"])
    report = {
        "schema_version": 1,
        "tool": "analystm gap-map",
        "input": input_meta,
        "algorithm": package["algorithm"],
        "parameters": package["parameters"],
        "summary": package["summary"],
        "outputs": {
            "data_npz": str(out_dir / "gap_map_outputs.npz"),
            "summary_csv": str(out_dir / "gap_map_summary.csv"),
        },
    }
    _write_json(str(out_dir / "report.json"), report)
    if args.output_json:
        _write_json(args.output_json, report)
    return 0


def cmd_multipeak(args: argparse.Namespace) -> int:
    from analystm.multipeak import run_multipeak_fit

    if args.multipeak_command != "fit":
        raise ValueError(f"unknown multipeak command: {args.multipeak_command}")

    bias = _load_npz_array(args.path, args.bias_key)
    position = _load_npz_array(args.path, args.position_key)
    data = _load_npz_array(args.path, args.data_key)
    package = run_multipeak_fit(
        bias,
        position,
        data,
        n_peaks=args.n_peaks,
        peak_count_map=_load_int_map_argument(args.peak_count_map),
        fit_range=(args.fit_range[0], args.fit_range[1]),
        retry_count=args.retry_count,
        r2_threshold=args.r2_threshold,
        peak_snr_min=args.peak_snr_min,
        peak_amp_frac_min=args.peak_amp_frac_min,
        row_start=args.row_start,
        row_end=args.row_end,
        manual_init_centers=_load_center_map_argument(args.manual_init_centers),
        fixed_sigma=args.fixed_sigma,
        peak_profile=args.peak_profile,
        background_mode=args.background_mode,
        random_seed=args.random_seed,
    )
    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = package["outputs"]
    np.savez_compressed(out_dir / "multipeak_outputs.npz", **payload)
    _write_summary_csv(out_dir / "multipeak_summary.csv", package["summary"])
    report = {
        "schema_version": 1,
        "tool": "analystm multipeak fit",
        "input": {
            "path": str(Path(args.path).expanduser()),
            "bias_key": args.bias_key,
            "position_key": args.position_key,
            "data_key": args.data_key,
        },
        "algorithm": package["algorithm"],
        "parameters": package["parameters"],
        "summary": package["summary"],
        "outputs": {
            "data_npz": str(out_dir / "multipeak_outputs.npz"),
            "summary_csv": str(out_dir / "multipeak_summary.csv"),
        },
    }
    _write_json(str(out_dir / "report.json"), report)
    if args.output_json:
        _write_json(args.output_json, report)
    return 0


def cmd_sjtm(args: argparse.Namespace) -> int:
    from analystm.sjtm import compute_sjtm_package

    bias = _load_npz_array(args.path, args.bias_key)
    current = _load_npz_array(args.path, args.cube_key)
    rn_cube = _load_npz_array(args.path, args.rn_cube_key) if args.rn_cube_key else current
    g0_cube = _load_npz_array(args.path, args.g0_cube_key) if args.g0_cube_key else current
    package = compute_sjtm_package(
        bias,
        current,
        neg_window=(args.neg_window[0], args.neg_window[1]),
        pos_window=(args.pos_window[0], args.pos_window[1]),
        rn_cube=rn_cube,
        g0_cube=g0_cube,
        rn_window=(args.rn_window[0], args.rn_window[1]) if args.rn_window else None,
        g0_window=(args.g0_window[0], args.g0_window[1]),
        min_points=args.min_points,
        ic_fit_mode=args.ic_fit_mode,
        random_seed=args.random_seed,
    )
    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_dir / "sjtm_outputs.npz",
        ic_map=package["ic_map"],
        rn_map=package["rn_map"],
        g0_map=package["g0_map"],
        ns_map=package["ns_map"],
        slope_map=package["slope_map"],
        fit_params_neg=package["fit_params_neg"],
        fit_params_pos=package["fit_params_pos"],
        g0_fit_params=package["g0_fit_params"],
    )
    summary_src = package.get("summary", {})
    summary = dict(summary_src.get("superfluid", summary_src) if isinstance(summary_src, dict) else {})
    if isinstance(summary_src, dict) and isinstance(summary_src.get("ic"), dict):
        summary["ic_valid_count"] = summary_src["ic"].get("valid_count", package.get("valid_count", 0))
        summary["ic_failed_count"] = summary_src["ic"].get("failed_count", package.get("failed_count", 0))
        summary["ic_mean_A"] = summary_src["ic"].get("ic_mean_A", np.nan)
    elif "valid_count" in package:
        summary["ic_valid_count"] = package["valid_count"]
    _write_summary_csv(out_dir / "sjtm_summary.csv", summary)
    parameters = package.get("parameters", {})
    report = {
        "schema_version": 1,
        "tool": "analystm sjtm",
        "input": {
            "path": str(Path(args.path).expanduser()),
            "bias_key": args.bias_key,
            "cube_key": args.cube_key,
            "rn_cube_key": args.rn_cube_key or args.cube_key,
            "g0_cube_key": args.g0_cube_key or args.cube_key,
        },
        "algorithm": package["algorithm"],
        "parameters": {
            "ic": parameters.get("ic", {}) if isinstance(parameters, dict) else {},
            "rn_g0_ns": parameters.get("superfluid", {}) if isinstance(parameters, dict) else {},
            "neg_window_mV": [float(args.neg_window[0]), float(args.neg_window[1])],
            "pos_window_mV": [float(args.pos_window[0]), float(args.pos_window[1])],
            "rn_window_mV": [float(args.rn_window[0]), float(args.rn_window[1])] if args.rn_window else [],
            "g0_window_mV": [float(args.g0_window[0]), float(args.g0_window[1])],
            "min_points": int(args.min_points),
            "random_seed": None if args.random_seed is None else int(args.random_seed),
        },
        "summary": summary,
        "outputs": {
            "data_npz": str(out_dir / "sjtm_outputs.npz"),
            "summary_csv": str(out_dir / "sjtm_summary.csv"),
        },
    }
    _write_json(str(out_dir / "report.json"), report)
    if args.output_json:
        _write_json(args.output_json, report)
    return 0


def cmd_deconvolve(args: argparse.Namespace) -> int:
    from analystm.deconvolution import run_grid_deconvolution, run_sis_didv_deconvolution

    bias = _load_npz_array(args.path, args.bias_key)
    didv = _load_npz_array(args.path, args.didv_key)
    mode = str(args.mode).strip().lower()
    if mode != "sis":
        raise ValueError("current public deconvolve CLI supports real SIS deconvolution; use --mode sis")
    kwargs = {
        "temperature_K": args.temperature_k,
        "tip_delta_meV": args.tip_delta_mev,
        "tip_gamma_meV": args.tip_gamma_mev,
        "pinv_rcond": args.pinv_rcond,
        "dos_broad_sigma_mV": args.dos_broad_sigma_mv,
        "n_grid": args.n_grid,
    }
    if didv.ndim == 1:
        package = run_sis_didv_deconvolution(bias, didv, **kwargs)
        arrays = {
            "bias_mV": package["v_common"],
            "sample_dos": package["sample_dos"],
            "sample_dos_raw": package["sample_dos_raw"],
            "reconvolved_didv": package["reconvolved_didv"],
            "measured_didv": package["measured_didv"],
            "residual": package["residual"],
            "v_solve": package["v_solve"],
            "didv_matrix_solve": package["didv_matrix_solve"],
            "rho_tip_support": package["rho_tip_support"],
            "tip_support_bias": package["tip_support_bias"],
        }
        summary = {
            "mode": "point_sis",
            "r2": package["r2"],
            "tip_delta_meV": package["tip_delta_meV"],
            "tip_gamma_meV": package["tip_gamma_meV"],
            "temperature_K": package["temperature_K"],
        }
    elif didv.ndim == 3:
        package = run_grid_deconvolution(bias, didv, **kwargs)
        arrays = {
            "bias_mV": package["v_common"],
            "sample_dos_cube": package["sample_dos_cube"],
            "r2_map": package["r2_map"],
            "status_map": package["status_map"],
        }
        summary = {
            "mode": "grid_sis",
            "valid_count": int(np.count_nonzero(np.asarray(package["status_map"]) == 0)),
            "failed_count": int(np.count_nonzero(np.asarray(package["status_map"]) != 0)),
            "r2_mean": float(np.nanmean(package["r2_map"])) if np.isfinite(package["r2_map"]).any() else np.nan,
        }
    else:
        raise ValueError("deconvolve input must be a 1D spectrum or 3D spectral cube")

    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_dir / "deconvolution_outputs.npz", **arrays)
    _write_summary_csv(out_dir / "deconvolution_summary.csv", summary)
    report = {
        "schema_version": 1,
        "tool": "analystm deconvolve",
        "input": {"path": str(Path(args.path).expanduser()), "bias_key": args.bias_key, "didv_key": args.didv_key},
        "algorithm": package["algorithm"],
        "parameters": {
            "mode": mode,
            "temperature_K": float(args.temperature_k),
            "tip_delta_meV": float(args.tip_delta_mev),
            "tip_gamma_meV": float(args.tip_gamma_mev),
            "pinv_rcond": float(args.pinv_rcond),
            "dos_broad_sigma_mV": float(args.dos_broad_sigma_mv),
            "n_grid": int(args.n_grid) if args.n_grid else None,
        },
        "summary": summary,
        "outputs": {
            "data_npz": str(out_dir / "deconvolution_outputs.npz"),
            "summary_csv": str(out_dir / "deconvolution_summary.csv"),
        },
    }
    _write_json(str(out_dir / "report.json"), report)
    if args.output_json:
        _write_json(args.output_json, report)
    return 0


def cmd_intensity(args: argparse.Namespace) -> int:
    from analystm.intensity import compute_z_ratio_map, peak_align_zero_cube, process_intensity_matrix

    bias = _load_npz_array(args.path, args.bias_key)
    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.intensity_command == "process":
        data = _load_npz_array(args.path, args.data_key)
        bias_range = (float(args.bias_range[0]), float(args.bias_range[1])) if args.bias_range else None
        package = process_intensity_matrix(
            bias,
            data,
            signal_mode=args.mode,
            smooth_method=args.smooth_method,
            smooth_value=args.smooth_value,
            line_interp_factor=args.line_interp_factor,
            bias_interp_factor=args.bias_interp_factor,
            bias_range=bias_range,
            remove_linear_baseline=bool(args.remove_linear_baseline),
            bias_scale_factor=args.bias_scale_factor,
        )
        np.savez_compressed(
            out_dir / "intensity_outputs.npz",
            processed_data=package["processed_data"],
            processed_bias=package["processed_bias"],
            processed_bias_scaled=package["processed_bias_scaled"],
            h_axis=package["h_axis"],
        )
        summary = {
            "mode": package["parameters"]["signal_mode"],
            "n_lines": int(package["processed_data"].shape[0]),
            "n_bias": int(package["processed_data"].shape[1]),
            "finite_count": int(np.count_nonzero(np.isfinite(package["processed_data"]))),
        }
        _write_summary_csv(out_dir / "intensity_summary.csv", summary)
        report = {
            "schema_version": 1,
            "tool": "analystm intensity process",
            "input": {"path": str(Path(args.path).expanduser()), "bias_key": args.bias_key, "data_key": args.data_key},
            "algorithm": package["algorithm"],
            "parameters": package["parameters"],
            "summary": summary,
            "outputs": {
                "data_npz": str(out_dir / "intensity_outputs.npz"),
                "summary_csv": str(out_dir / "intensity_summary.csv"),
            },
        }
    elif args.intensity_command == "z-ratio":
        cube = _load_npz_array(args.path, args.cube_key)
        package = compute_z_ratio_map(
            bias,
            cube,
            energy_mV=args.energy_mv,
            numerator=args.numerator,
            eps_rel=args.eps_rel,
        )
        np.savez_compressed(
            out_dir / "intensity_z_ratio_outputs.npz",
            z_ratio_map=package["z_ratio_map"],
            numerator_map=package["numerator_map"],
            denominator_map=package["denominator_map"],
            mask_zero=package["mask_zero"],
        )
        summary = {
            "energy_mV": float(args.energy_mv),
            "positive_bias_mV": package["positive_bias_mV"],
            "negative_bias_mV": package["negative_bias_mV"],
            "finite_count": int(np.count_nonzero(np.isfinite(package["z_ratio_map"]))),
            "mean": float(np.nanmean(package["z_ratio_map"])) if np.isfinite(package["z_ratio_map"]).any() else np.nan,
        }
        _write_summary_csv(out_dir / "intensity_z_ratio_summary.csv", summary)
        report = {
            "schema_version": 1,
            "tool": "analystm intensity z-ratio",
            "input": {"path": str(Path(args.path).expanduser()), "bias_key": args.bias_key, "cube_key": args.cube_key},
            "algorithm": package["algorithm"],
            "parameters": package["parameters"],
            "summary": summary,
            "outputs": {
                "data_npz": str(out_dir / "intensity_z_ratio_outputs.npz"),
                "summary_csv": str(out_dir / "intensity_z_ratio_summary.csv"),
            },
        }
    elif args.intensity_command == "peak-align-zero":
        cube = _load_npz_array(args.path, args.cube_key)
        package = peak_align_zero_cube(
            bias,
            cube,
            neg_window=(args.neg_window[0], args.neg_window[1]),
            pos_window=(args.pos_window[0], args.pos_window[1]),
        )
        np.savez_compressed(
            out_dir / "intensity_aligned_outputs.npz",
            aligned_cube=package["aligned_cube"],
            aligned_bias_mV=package["aligned_bias_mV"],
            offset_map_mV=package["offset_map_mV"],
            v_minus_map_mV=package["v_minus_map_mV"],
            v_plus_map_mV=package["v_plus_map_mV"],
            valid_z_mask=package["valid_z_mask"],
        )
        summary = {
            "n_bias_in": int(np.asarray(bias).size),
            "n_bias_out": int(np.asarray(package["aligned_bias_mV"]).size),
            "offset_mean_mV": float(np.nanmean(package["offset_map_mV"])),
            "offset_std_mV": float(np.nanstd(package["offset_map_mV"])),
        }
        _write_summary_csv(out_dir / "intensity_aligned_summary.csv", summary)
        report = {
            "schema_version": 1,
            "tool": "analystm intensity peak-align-zero",
            "input": {"path": str(Path(args.path).expanduser()), "bias_key": args.bias_key, "cube_key": args.cube_key},
            "algorithm": package["algorithm"],
            "parameters": package["parameters"],
            "summary": summary,
            "outputs": {
                "data_npz": str(out_dir / "intensity_aligned_outputs.npz"),
                "summary_csv": str(out_dir / "intensity_aligned_summary.csv"),
            },
        }
    else:
        raise ValueError(f"unknown intensity command: {args.intensity_command}")

    _write_json(str(out_dir / "report.json"), report)
    if args.output_json:
        _write_json(args.output_json, report)
    return 0


def cmd_qpi(args: argparse.Namespace) -> int:
    from analystm.fft_filter import run_fft_filter
    from analystm.qpi import compute_pr_qpi_volume, compute_qpi_1d_fft, compute_real_phase_pll, run_qpi_fft, run_qpi_symmetry

    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.qpi_command == "symmetry":
        qpi = _load_npz_array(args.path, args.qpi_key, fallback_first=True)
        center = (float(args.center[0]), float(args.center[1])) if args.center else None
        package = run_qpi_symmetry(qpi, order=args.order, center=center, nan_policy=args.nan_policy)
        np.savez_compressed(out_dir / "qpi_symmetry_outputs.npz", symmetrized_qpi=package["symmetrized_qpi"])
        summary = dict(package["summary"])
        _write_summary_csv(out_dir / "qpi_symmetry_summary.csv", summary)
        report = {
            "schema_version": 1,
            "tool": "analystm qpi symmetry",
            "input": {"path": str(Path(args.path).expanduser()), "qpi_key": args.qpi_key},
            "algorithm": package["algorithm"],
            "parameters": package["parameters"],
            "summary": summary,
            "outputs": {
                "data_npz": str(out_dir / "qpi_symmetry_outputs.npz"),
                "summary_csv": str(out_dir / "qpi_symmetry_summary.csv"),
            },
        }
    elif args.qpi_command == "pr-qpi":
        cube = _load_npz_array(args.path, args.cube_key)
        bias = _load_npz_array(args.path, args.bias_key)
        package = compute_pr_qpi_volume(
            cube,
            bias,
            slider_min=args.slider_min,
            slider_max=args.slider_max,
            is_multi_impurity=bool(args.multi_impurity),
            window_name=args.window,
            mask_dc=not bool(args.no_mask_dc),
            mask_radius_px=args.mask_radius_px,
            scale_mode=args.scale_mode,
        )
        np.savez_compressed(
            out_dir / "qpi_pr_outputs.npz",
            fft_stack=package["fft_stack"],
            pr_qpi_pos=package["pr_qpi_pos"],
            pr_qpi_neg=package["pr_qpi_neg"],
            bias=package["bias"],
            positive_indices=package["positive_indices"],
            negative_indices=package["negative_indices"],
            positive_bias_mV=package["positive_bias_mV"],
            negative_bias_mV=package["negative_bias_mV"],
        )
        summary = dict(package["summary"])
        _write_summary_csv(out_dir / "qpi_pr_summary.csv", summary)
        report = {
            "schema_version": 1,
            "tool": "analystm qpi pr-qpi",
            "input": {"path": str(Path(args.path).expanduser()), "cube_key": args.cube_key, "bias_key": args.bias_key},
            "algorithm": package["algorithm"],
            "parameters": package["parameters"],
            "summary": summary,
            "outputs": {
                "data_npz": str(out_dir / "qpi_pr_outputs.npz"),
                "summary_csv": str(out_dir / "qpi_pr_summary.csv"),
            },
        }
    elif args.qpi_command == "fft-volume":
        cube = _load_npz_array(args.path, args.cube_key, fallback_first=True)
        package = run_qpi_fft(
            cube,
            window_name=args.window,
            mask_dc=not bool(args.no_mask_dc),
            mask_radius_px=args.mask_radius_px,
            scale_mode=args.scale_mode,
        )
        np.savez_compressed(
            out_dir / "qpi_fft_outputs.npz",
            fft_base=package["fft_base"],
            fft_display=package["fft_display"],
        )
        summary = dict(package["summary"])
        _write_summary_csv(out_dir / "qpi_fft_summary.csv", summary)
        report = {
            "schema_version": 1,
            "tool": "analystm qpi fft-volume",
            "input": {"path": str(Path(args.path).expanduser()), "cube_key": args.cube_key},
            "algorithm": package["algorithm"],
            "parameters": package["parameters"],
            "summary": summary,
            "outputs": {
                "data_npz": str(out_dir / "qpi_fft_outputs.npz"),
                "summary_csv": str(out_dir / "qpi_fft_summary.csv"),
            },
        }
    elif args.qpi_command == "1d-fft":
        cube = _load_npz_array(args.path, args.cube_key)
        bias = _load_npz_array(args.path, args.bias_key)
        package = compute_qpi_1d_fft(
            cube,
            bias=bias,
            scan_size_nm=(float(args.scan_size_nm[0]), float(args.scan_size_nm[1])),
            p1_nm=(float(args.p1[0]), float(args.p1[1])) if args.p1 else None,
            p2_nm=(float(args.p2[0]), float(args.p2[1])) if args.p2 else None,
            cube_order=args.cube_order,
            background_mode=args.background_mode,
            window_name=args.window,
            mask_q0=not bool(args.no_mask_q0),
            mask_radius_px=args.mask_radius_px,
            scale_mode=args.scale_mode,
            smooth_size=args.smooth_size,
        )
        np.savez_compressed(
            out_dir / "qpi_1d_fft_outputs.npz",
            line_matrix_raw=package["line_matrix_raw"],
            line_matrix_display=package["line_matrix_display"],
            line_distance_nm=package["line_distance_nm"],
            line_distance_fft_nm=package["line_distance_fft_nm"],
            line_x_nm=package["line_x_nm"],
            line_y_nm=package["line_y_nm"],
            fft_map_raw=package["fft_map_raw"],
            fft_map_display=package["fft_map_display"],
            q_axis=package["q_axis"],
            bias=package["bias"],
        )
        summary = dict(package["summary"])
        _write_summary_csv(out_dir / "qpi_1d_fft_summary.csv", summary)
        report = {
            "schema_version": 1,
            "tool": "analystm qpi 1d-fft",
            "input": {"path": str(Path(args.path).expanduser()), "cube_key": args.cube_key, "bias_key": args.bias_key},
            "algorithm": package["algorithm"],
            "parameters": package["parameters"],
            "summary": summary,
            "outputs": {
                "data_npz": str(out_dir / "qpi_1d_fft_outputs.npz"),
                "summary_csv": str(out_dir / "qpi_1d_fft_summary.csv"),
            },
        }
    elif args.qpi_command == "fft-filter":
        cube = _load_npz_array(args.path, args.cube_key)
        package = run_fft_filter(
            cube,
            scan_size_nm=(float(args.scan_size_nm[0]), float(args.scan_size_nm[1])),
            regions=_fft_filter_regions_from_args(args),
            include_neg=not bool(args.no_include_neg),
            mode=args.mode,
            invert=bool(args.invert),
            window_name=args.window,
            scale_mode=args.scale_mode,
            background_mode="Raw",
            input_kind="qpi_cube",
            display_style="qpi",
            subtract_mean=True,
        )
        np.savez_compressed(
            out_dir / "qpi_fft_filter_outputs.npz",
            processed=package["processed"],
            filtered=package["filtered"],
            mask=package["mask"],
            kx_axis=package["kx_axis"],
            ky_axis=package["ky_axis"],
            fft_display=package["fft_display"],
            fft_filtered_display=package["fft_filtered_display"],
        )
        summary = dict(package["summary"])
        _write_summary_csv(out_dir / "qpi_fft_filter_summary.csv", summary)
        report = {
            "schema_version": 1,
            "tool": "analystm qpi fft-filter",
            "input": {"path": str(Path(args.path).expanduser()), "cube_key": args.cube_key},
            "algorithm": package["algorithm"],
            "parameters": package["parameters"],
            "summary": summary,
            "outputs": {
                "data_npz": str(out_dir / "qpi_fft_filter_outputs.npz"),
                "summary_csv": str(out_dir / "qpi_fft_filter_summary.csv"),
            },
        }
    elif args.qpi_command == "real-phase":
        ref = _load_npz_array(args.path, args.ref_key)
        target = _load_npz_array(args.path, args.target_key)
        package = compute_real_phase_pll(
            ref,
            target,
            q1_yx=(float(args.q1[0]), float(args.q1[1])),
            q2_yx=(float(args.q2[0]), float(args.q2[1])),
            sigma_px=args.sigma_px,
            window=args.window,
            detrend_target=bool(args.detrend_target),
        )
        np.savez_compressed(
            out_dir / "qpi_real_phase_outputs.npz",
            pll=package["pll"],
            delta1=package["delta1"],
            delta2=package["delta2"],
            amp_ref1=package["amp_ref1"],
            amp_ref2=package["amp_ref2"],
            amp_tar1=package["amp_tar1"],
            amp_tar2=package["amp_tar2"],
            phi_ref1=package["phi_ref1"],
            phi_ref2=package["phi_ref2"],
            phi_tar1=package["phi_tar1"],
            phi_tar2=package["phi_tar2"],
        )
        summary = dict(package["summary"])
        _write_summary_csv(out_dir / "qpi_real_phase_summary.csv", summary)
        report = {
            "schema_version": 1,
            "tool": "analystm qpi real-phase",
            "input": {"path": str(Path(args.path).expanduser()), "ref_key": args.ref_key, "target_key": args.target_key},
            "algorithm": package["algorithm"],
            "parameters": package["parameters"],
            "summary": summary,
            "outputs": {
                "data_npz": str(out_dir / "qpi_real_phase_outputs.npz"),
                "summary_csv": str(out_dir / "qpi_real_phase_summary.csv"),
            },
        }
    else:
        raise ValueError(f"unknown qpi command: {args.qpi_command}")

    _write_json(str(out_dir / "report.json"), report)
    if args.output_json:
        _write_json(args.output_json, report)
    return 0


def cmd_spstm(args: argparse.Namespace) -> int:
    from analystm.spstm import build_qpi_r90_contrast, build_qpi_spin_contrast, process_didv_contrast

    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.spstm_command == "didv":
        x = _load_npz_array(args.path, args.x_key)
        y_a = _load_npz_array(args.path, args.a_key)
        y_b = _load_npz_array(args.path, args.b_key) if args.b_key else None
        x_b = _load_npz_array(args.path, args.x_b_key) if args.x_b_key else None
        package = process_didv_contrast(
            x,
            y_a,
            x_b=x_b,
            y_b=y_b,
            bias_scale_a=args.bias_scale_a,
            bias_scale_b=args.bias_scale_b,
            offset=args.offset,
            symmetrize=bool(args.symmetrize),
            smooth_method_a=args.smooth_method_a,
            smooth_method_b=args.smooth_method_b,
            smooth_param_a=args.smooth_param_a,
            smooth_param_b=args.smooth_param_b,
            norm_mode_a=args.norm_mode_a,
            norm_mode_b=args.norm_mode_b,
        )
        np.savez_compressed(out_dir / "spstm_didv_outputs.npz", x=package["x"], y_a=package["y_a"], y_b=package["y_b"])
        summary = dict(package["summary"])
        _write_summary_csv(out_dir / "spstm_didv_summary.csv", summary)
        report = {
            "schema_version": 1,
            "tool": "analystm spstm didv",
            "input": {"path": str(Path(args.path).expanduser()), "x_key": args.x_key, "a_key": args.a_key, "b_key": args.b_key},
            "algorithm": package["algorithm"],
            "parameters": package["parameters"],
            "summary": summary,
            "outputs": {"data_npz": str(out_dir / "spstm_didv_outputs.npz"), "summary_csv": str(out_dir / "spstm_didv_summary.csv")},
        }
    elif args.spstm_command == "qpi-r90":
        qpi = _load_npz_array(args.path, args.map_key)
        package = build_qpi_r90_contrast(qpi, operation=args.operation, rotation=args.rotation)
        np.savez_compressed(
            out_dir / "spstm_qpi_r90_outputs.npz",
            result=package["result"],
            input_map=package["input_map"],
            rotated_map=package["rotated_map"],
        )
        summary = dict(package["summary"])
        _write_summary_csv(out_dir / "spstm_qpi_r90_summary.csv", summary)
        report = {
            "schema_version": 1,
            "tool": "analystm spstm qpi-r90",
            "input": {"path": str(Path(args.path).expanduser()), "map_key": args.map_key},
            "algorithm": package["algorithm"],
            "parameters": package["parameters"],
            "summary": summary,
            "outputs": {"data_npz": str(out_dir / "spstm_qpi_r90_outputs.npz"), "summary_csv": str(out_dir / "spstm_qpi_r90_summary.csv")},
        }
    elif args.spstm_command == "qpi-spin":
        pos = _load_npz_array(args.path, args.pos_key)
        neg = _load_npz_array(args.path, args.neg_key)
        package = build_qpi_spin_contrast(pos, neg)
        np.savez_compressed(
            out_dir / "spstm_qpi_spin_outputs.npz",
            contrast=package["contrast"],
            average=package["average"],
            matched_pos=package["matched_pos"],
            matched_neg=package["matched_neg"],
        )
        summary = dict(package["summary"])
        _write_summary_csv(out_dir / "spstm_qpi_spin_summary.csv", summary)
        report = {
            "schema_version": 1,
            "tool": "analystm spstm qpi-spin",
            "input": {"path": str(Path(args.path).expanduser()), "pos_key": args.pos_key, "neg_key": args.neg_key},
            "algorithm": package["algorithm"],
            "parameters": package["parameters"],
            "summary": summary,
            "outputs": {"data_npz": str(out_dir / "spstm_qpi_spin_outputs.npz"), "summary_csv": str(out_dir / "spstm_qpi_spin_summary.csv")},
        }
    else:
        raise ValueError(f"unknown spstm command: {args.spstm_command}")

    _write_json(str(out_dir / "report.json"), report)
    if args.output_json:
        _write_json(args.output_json, report)
    return 0


def cmd_topography(args: argparse.Namespace) -> int:
    from analystm.fft_filter import run_fft_filter
    from analystm.topography_display import compute_topography_fft_display
    from analystm.topography import estimate_lf_displacement, estimate_lf_displacement_from_q_vectors

    image = _load_npz_array(args.path, args.image_key, fallback_first=True)
    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.topography_command == "lf-drift":
        if args.q1 and args.q2:
            package = estimate_lf_displacement_from_q_vectors(
                image,
                q1_yx=(float(args.q1[0]), float(args.q1[1])),
                q2_yx=(float(args.q2[0]), float(args.q2[1])),
                sigma=float(args.sigma),
            )
        elif args.q_point1 and args.q_point2:
            package = estimate_lf_displacement(
                image,
                q_points_px=[(float(args.q_point1[0]), float(args.q_point1[1])), (float(args.q_point2[0]), float(args.q_point2[1]))],
                sigma=float(args.sigma),
                search_r=int(args.search_r),
                use_local_max=not bool(args.no_local_max),
                use_gaussian=bool(args.gaussian),
                gaussian_r=int(args.gaussian_r),
            )
        else:
            raise ValueError("lf-drift requires either --q1/--q2 qy qx vectors or --q-point1/--q-point2 px py points")

        np.savez_compressed(
            out_dir / "topography_lf_outputs.npz",
            corrected_image=package["corrected_image"],
            ux_field=package["ux_field"],
            uy_field=package["uy_field"],
            corr_coords_y=package["corr_coords_y"],
            corr_coords_x=package["corr_coords_x"],
            q_vectors_yx=package["q_vectors_yx"],
        )
        summary = dict(package["summary"])
        _write_summary_csv(out_dir / "topography_lf_summary.csv", summary)
        report = {
            "schema_version": 1,
            "tool": "analystm topography lf-drift",
            "input": {"path": str(Path(args.path).expanduser()), "image_key": args.image_key},
            "algorithm": package["algorithm"],
            "parameters": package["parameters"],
            "summary": summary,
            "outputs": {
                "data_npz": str(out_dir / "topography_lf_outputs.npz"),
                "summary_csv": str(out_dir / "topography_lf_summary.csv"),
            },
        }
    elif args.topography_command == "fft-filter":
        package = run_fft_filter(
            image,
            scan_size_nm=(float(args.scan_size_nm[0]), float(args.scan_size_nm[1])),
            regions=_fft_filter_regions_from_args(args),
            include_neg=not bool(args.no_include_neg),
            mode=args.mode,
            invert=bool(args.invert),
            window_name=args.window,
            scale_mode=args.scale_mode,
            background_mode=args.background_mode,
            input_kind="topography",
            display_style="topography",
            subtract_mean=True,
        )
        np.savez_compressed(
            out_dir / "topography_fft_filter_outputs.npz",
            processed=package["processed"],
            filtered=package["filtered"],
            mask=package["mask"],
            kx_axis=package["kx_axis"],
            ky_axis=package["ky_axis"],
            fft_display=package["fft_display"],
            fft_filtered_display=package["fft_filtered_display"],
        )
        summary = dict(package["summary"])
        _write_summary_csv(out_dir / "topography_fft_filter_summary.csv", summary)
        report = {
            "schema_version": 1,
            "tool": "analystm topography fft-filter",
            "input": {"path": str(Path(args.path).expanduser()), "image_key": args.image_key},
            "algorithm": package["algorithm"],
            "parameters": package["parameters"],
            "summary": summary,
            "outputs": {
                "data_npz": str(out_dir / "topography_fft_filter_outputs.npz"),
                "summary_csv": str(out_dir / "topography_fft_filter_summary.csv"),
            },
        }
    elif args.topography_command == "display-fft":
        package = compute_topography_fft_display(
            image,
            scan_size_nm=float(args.scan_size_nm),
            window_name=args.window,
            scale_mode=args.scale_mode,
            background_mode=args.background_mode,
        )
        np.savez_compressed(
            out_dir / "topography_display_fft_outputs.npz",
            processed=package["processed"],
            fft_complex=package["fft_complex"],
            fft_display=package["fft_display"],
            k_extent=np.asarray(package["k_extent"], dtype=float),
        )
        summary = {
            "shape_yx": [int(v) for v in np.asarray(package["processed"]).shape],
            "k_extent": [float(v) for v in package["k_extent"]],
            "fft_display_min": float(np.nanmin(package["fft_display"])),
            "fft_display_max": float(np.nanmax(package["fft_display"])),
        }
        _write_summary_csv(out_dir / "topography_display_fft_summary.csv", summary)
        report = {
            "schema_version": 1,
            "tool": "analystm topography display-fft",
            "input": {"path": str(Path(args.path).expanduser()), "image_key": args.image_key},
            "algorithm": package["algorithm"],
            "parameters": package["parameters"],
            "summary": summary,
            "outputs": {
                "data_npz": str(out_dir / "topography_display_fft_outputs.npz"),
                "summary_csv": str(out_dir / "topography_display_fft_summary.csv"),
            },
        }
    else:
        raise ValueError(f"unknown topography command: {args.topography_command}")

    _write_json(str(out_dir / "report.json"), report)
    if args.output_json:
        _write_json(args.output_json, report)
    return 0


def cmd_spectroscopy(args: argparse.Namespace) -> int:
    from analystm.spectroscopy import auto_detect_offset, build_spectroscopy_export_payload, process_spectrum

    x = _load_npz_array(args.path, args.x_key)
    y = _load_npz_array(args.path, args.y_key)
    ref_current = _load_npz_array(args.path, args.ref_current_key) if args.ref_current_key else None
    offset = float(args.offset)
    offset_report: dict[str, Any] = {}
    if args.auto_offset:
        offset_report = auto_detect_offset(x, y)
        offset = float(offset_report["offset"])
    package = process_spectrum(
        x,
        y,
        offset=offset,
        x_scale=args.x_scale,
        symmetrize=bool(args.symmetrize),
        smooth_method=args.smooth_method,
        smooth_param=args.smooth_param,
        norm_mode=args.norm_mode,
        ref_current=ref_current,
        derivative_order=args.derivative_order,
        derivative_smooth=args.derivative_smooth,
    )
    payload = build_spectroscopy_export_payload(
        package["processed_x"],
        package["processed_y"],
        derivative_y=package["derivative_y"],
        derivative_order=args.derivative_order,
        export_kind=args.export_kind,
        channel_name=args.y_key,
    )
    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    data_npz = out_dir / "spectroscopy_outputs.npz"
    np.savez_compressed(
        data_npz,
        processed_x=package["processed_x"],
        processed_y=package["processed_y"],
        derivative_y=package["derivative_y"],
    )
    _write_table_csv(
        out_dir / "spectroscopy_processed.csv",
        {"bias_mV": package["processed_x"], "signal": package["processed_y"], "derivative": package["derivative_y"]},
    )
    report = {
        "schema_version": 1,
        "tool": "analystm spectroscopy process",
        "input": {"path": str(Path(args.path).expanduser()), "x_key": args.x_key, "y_key": args.y_key},
        "algorithm": package["algorithm"],
        "parameters": package["parameters"],
        "auto_offset": offset_report,
        "summary": package["summary"],
        "export_payload": {
            "columns": [name for name, _ in payload["columns"]],
            "comments": payload["comments"],
        },
        "outputs": {"data_npz": str(data_npz), "processed_csv": str(out_dir / "spectroscopy_processed.csv")},
    }
    _write_json(str(out_dir / "report.json"), report)
    if args.output_json:
        _write_json(args.output_json, report)
    return 0


def cmd_path_viz(args: argparse.Namespace) -> int:
    from analystm.path_viz import autoscale_bounds, build_path_from_batches, path_log_rows

    if args.path_viz_command != "build":
        raise ValueError(f"unknown path-viz command: {args.path_viz_command}")
    payload = _load_json_argument(args.path)
    batches = payload.get("batches", payload) if isinstance(payload, dict) else payload
    if not isinstance(batches, list):
        raise ValueError("path-viz input must be a list of batches or an object with batches")
    start = payload.get("start", [0.0, 0.0]) if isinstance(payload, dict) else [0.0, 0.0]
    package = build_path_from_batches(batches, start=start)
    rows = path_log_rows(package["steps"])
    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    log_csv = out_dir / "path_log.csv"
    points_json = out_dir / "path_points.json"
    if rows:
        _write_csv_rows(log_csv, rows)
    else:
        _write_csv_rows(log_csv, [{"#": "", "Move": "", "+Z": "", "End (x,y)": "", "Arrived": "", "Current": "", "Mark": ""}])
    package_out = {
        **package,
        "bounds": {
            "fit": autoscale_bounds(package["points"], mode="fit"),
            "origin": autoscale_bounds(package["points"], mode="origin"),
        },
    }
    _write_json(str(points_json), package_out)
    report = {
        "schema_version": 1,
        "tool": "analystm path-viz build",
        "input": {"path": str(Path(args.path).expanduser())},
        "algorithm": package["algorithm"],
        "summary": package["summary"],
        "outputs": {"path_log_csv": str(log_csv), "path_points_json": str(points_json)},
    }
    _write_json(str(out_dir / "report.json"), report)
    if args.output_json:
        _write_json(args.output_json, report)
    return 0


def cmd_publication(args: argparse.Namespace) -> int:
    from analystm.publication import FigurePayload, ImagePayload, LinePayload, apply_image_contrast, payload_summary, regularize_image_extent, suggest_scalebar_length

    if args.publication_command != "payload":
        raise ValueError(f"unknown publication command: {args.publication_command}")
    archive = np.load(Path(args.path).expanduser())
    images = []
    if args.image_key:
        image = np.asarray(archive[args.image_key])
        extent = tuple(float(v) for v in args.image_extent) if args.image_extent else None
        extent = regularize_image_extent(image, extent)
        contrast = apply_image_contrast(image, mode=args.contrast_mode)
        images.append(ImagePayload(data=image, extent=extent, vmin=(contrast[0] if contrast else None), vmax=(contrast[1] if contrast else None)))
    lines = []
    if args.x_key and args.y_key:
        lines.append(LinePayload(x=np.asarray(archive[args.x_key], dtype=float), y=np.asarray(archive[args.y_key], dtype=float), label=args.line_label or args.y_key))
    payload = FigurePayload(title=args.title, xlabel=args.xlabel, ylabel=args.ylabel, images=images, lines=lines)
    summary = payload_summary(payload)
    image_infos = []
    for image in images:
        image_infos.append(
            {
                "shape": [int(v) for v in np.asarray(image.data).shape],
                "extent": list(image.extent) if image.extent is not None else [],
                "vmin": image.vmin,
                "vmax": image.vmax,
                "suggested_scalebar_length": suggest_scalebar_length(image),
            }
        )
    line_infos = []
    for line in lines:
        line_infos.append({"label": line.label, "points": int(min(np.asarray(line.x).size, np.asarray(line.y).size))})
    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    payload_json = out_dir / "publication_payload.json"
    payload_out = {
        "schema_version": 1,
        "algorithm": summary["algorithm"],
        "title": payload.title,
        "xlabel": payload.xlabel,
        "ylabel": payload.ylabel,
        "summary": {k: v for k, v in summary.items() if k != "algorithm"},
        "images": image_infos,
        "lines": line_infos,
    }
    _write_json(str(payload_json), payload_out)
    report = {
        "schema_version": 1,
        "tool": "analystm publication payload",
        "input": {"path": str(Path(args.path).expanduser()), "image_key": args.image_key, "x_key": args.x_key, "y_key": args.y_key},
        "algorithm": summary["algorithm"],
        "summary": {k: v for k, v in summary.items() if k != "algorithm"},
        "outputs": {"payload_json": str(payload_json)},
    }
    _write_json(str(out_dir / "report.json"), report)
    if args.output_json:
        _write_json(args.output_json, report)
    return 0


def cmd_histogram(args: argparse.Namespace) -> int:
    from analystm.histogram import compute_histogram

    arr = _load_keyed_array(args.path, args.data_key, fallback_first=True)
    if arr.ndim == 3:
        idx = int(np.clip(args.layer_index, 0, arr.shape[2] - 1))
        arr = np.asarray(arr[:, :, idx], dtype=float)
    package = compute_histogram(
        arr,
        vmin=args.vmin,
        vmax=args.vmax,
        bin_size=args.bin_size,
        background_mode=args.background_mode,
        fit_bandwidth_scale=args.fit_bw_scale,
        fit_max_samples=args.fit_max_samples,
    )
    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    hist_csv = out_dir / "histogram.csv"
    fit_csv = out_dir / "fit_curve.csv"
    _write_table_csv(hist_csv, {"left_edge": package["edges"][:-1], "right_edge": package["edges"][1:], "center": package["centers"], "count": package["counts"]})
    _write_table_csv(fit_csv, {"x": package["fit_x"], "count": package["fit_y"]})
    np.savez_compressed(
        out_dir / "histogram_outputs.npz",
        processed=package["processed"],
        edges=package["edges"],
        centers=package["centers"],
        counts=package["counts"],
        fit_x=package["fit_x"],
        fit_y=package["fit_y"],
    )
    report = {
        "schema_version": 1,
        "tool": "analystm histogram",
        "input": {"path": str(Path(args.path).expanduser()), "data_key": args.data_key, "layer_index": int(args.layer_index)},
        "algorithm": package["algorithm"],
        "parameters": package["parameters"],
        "stats": package["stats"],
        "outputs": {
            "data_npz": str(out_dir / "histogram_outputs.npz"),
            "histogram_csv": str(hist_csv),
            "fit_curve_csv": str(fit_csv),
        },
    }
    _write_json(str(out_dir / "report.json"), report)
    if args.output_json:
        _write_json(args.output_json, report)
    return 0


def cmd_crop(args: argparse.Namespace) -> int:
    from analystm.map_crop import (
        build_generated_header,
        compute_square_crop_geometry,
        crop_3ds_signals,
        crop_sxm_signals,
        extract_sxm_display_map,
        sample_display_patch,
        source_size_xy_nm,
        undo_sxm_display_orientation,
    )

    if args.crop_command != "map":
        raise ValueError(f"unknown crop command: {args.crop_command}")

    arr = _load_keyed_array(args.path, args.data_key, fallback_first=True)
    header = _load_json_argument(args.header_json) if getattr(args, "header_json", None) else {}
    scan_size_nm_xy = source_size_xy_nm(header, scan_size_nm=args.scan_size_nm)
    kind = str(args.kind or "map").strip().lower()
    if kind == "3ds":
        preview_shape = (int(arr.shape[1]), int(arr.shape[0])) if arr.ndim == 3 else tuple(np.asarray(arr).shape[:2])
    else:
        preview_shape = tuple(np.asarray(arr).shape[:2])
    geometry = compute_square_crop_geometry(
        preview_shape_yx=preview_shape,
        center_xy_px=(float(args.center_px[0]), float(args.center_px[1])),
        side_px=float(args.side_px),
        angle_deg=float(args.angle_deg),
        source_size_nm_xy=scan_size_nm_xy,
    )

    if kind == "3ds":
        cropped = crop_3ds_signals({args.data_key or "data": arr}, geometry)
        if not cropped:
            raise ValueError("3DS crop produced no valid output")
        arrays = cropped
        header_out = build_generated_header(
            header,
            geometry,
            dtype="3ds",
            bias_len=int(next(iter(cropped.values())).shape[2]),
            source_file=str(Path(args.path).expanduser()),
            source_channel=args.data_key,
        )
    elif kind == "sxm":
        packet = {args.direction: arr}
        cropped_sxm = crop_sxm_signals({args.data_key or "data": packet}, geometry, header=header)
        if not cropped_sxm:
            raise ValueError("SXM crop produced no valid output")
        first = cropped_sxm[args.data_key or "data"]
        arrays = {str(key): np.asarray(value, dtype=float) for key, value in first.items()} if isinstance(first, dict) else {args.data_key or "data": first}
        header_out = build_generated_header(header, geometry, dtype="sxm", source_file=str(Path(args.path).expanduser()), source_channel=args.data_key)
    else:
        display = np.asarray(arr, dtype=float)
        if display.ndim != 2:
            display = extract_sxm_display_map({args.direction: display}, header=header)
        patch = sample_display_patch(display, geometry)
        if patch is None:
            raise ValueError("map crop produced no valid output")
        arrays = {args.data_key or "data": undo_sxm_display_orientation(patch, args.direction, header=header) if args.undo_orientation else patch}
        header_out = build_generated_header(header, geometry, dtype="map", source_file=str(Path(args.path).expanduser()), source_channel=args.data_key)

    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    data_npz = out_dir / "cropped_data.npz"
    np.savez_compressed(data_npz, **arrays)
    header_json = out_dir / "cropped_header.json"
    _write_json(str(header_json), header_out)
    report = {
        "schema_version": 1,
        "tool": "analystm crop map",
        "input": {
            "path": str(Path(args.path).expanduser()),
            "data_key": args.data_key,
            "kind": kind,
        },
        "algorithm": geometry["algorithm"],
        "parameters": {
            "center_xy_px": [float(args.center_px[0]), float(args.center_px[1])],
            "side_px": float(args.side_px),
            "angle_deg": float(args.angle_deg),
            "scan_size_nm_xy": [float(scan_size_nm_xy[0]), float(scan_size_nm_xy[1])],
            "crop_size_nm": [float(geometry["crop_size_nm"][0]), float(geometry["crop_size_nm"][1])],
            "out_shape_yx": [int(v) for v in geometry["out_shape"]],
        },
        "outputs": {
            "data_npz": str(data_npz),
            "header_json": str(header_json),
        },
    }
    _write_json(str(out_dir / "report.json"), report)
    if args.output_json:
        _write_json(args.output_json, report)
    return 0


def cmd_waterfall(args: argparse.Namespace) -> int:
    from analystm.waterfall import (
        export_waterfall_table,
        linecut_flat_indices,
        peak_align_zero_grid,
        run_waterfall_fit,
        spatial_interpolate_grid,
        waterfall_points_payload,
    )

    cube = _load_npz_array(args.path, args.cube_key)
    bias = _load_npz_array(args.path, args.bias_key)
    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.waterfall_command == "peak-align-zero":
        package = peak_align_zero_grid(
            cube,
            bias,
            neg_range=(float(args.neg_range[0]), float(args.neg_range[1])),
            pos_range=(float(args.pos_range[0]), float(args.pos_range[1])),
        )
        data_npz = out_dir / "waterfall_peak_align_outputs.npz"
        np.savez_compressed(
            data_npz,
            aligned_grid=package["aligned_grid"],
            aligned_bias_mV=package["aligned_bias_mV"],
            offset_map_mV=package["offset_map_mV"],
        )
        summary = {
            "input_shape": [int(v) for v in np.asarray(cube).shape],
            "aligned_shape": [int(v) for v in package["aligned_grid"].shape],
            "bias_points": int(package["aligned_bias_mV"].size),
        }
        report = {
            "schema_version": 1,
            "tool": "analystm waterfall peak-align-zero",
            "input": {"path": str(Path(args.path).expanduser()), "cube_key": args.cube_key, "bias_key": args.bias_key},
            "algorithm": package["algorithm"],
            "parameters": package["parameters"],
            "summary": summary,
            "outputs": {"data_npz": str(data_npz)},
        }
    elif args.waterfall_command == "fit":
        work_cube = spatial_interpolate_grid(cube, scale=float(args.spatial_scale)) if float(args.spatial_scale) != 1.0 else np.asarray(cube, dtype=float)
        if args.indices:
            selected_indices = np.asarray(args.indices, dtype=int)
        elif args.linecut:
            selected_indices = linecut_flat_indices(
                work_cube.shape[:2],
                p1_xy=(float(args.linecut[0]), float(args.linecut[1])),
                p2_xy=(float(args.linecut[2]), float(args.linecut[3])),
            )
        elif args.allow_full_grid:
            selected_indices = np.arange(work_cube.shape[0] * work_cube.shape[1], dtype=int)
        else:
            raise ValueError("waterfall fit requires --linecut, --indices, or --allow-full-grid")
        package = run_waterfall_fit(
            work_cube,
            bias,
            selected_indices=selected_indices,
            neg_range=(float(args.neg_range[0]), float(args.neg_range[1])),
            pos_range=(float(args.pos_range[0]), float(args.pos_range[1])),
            offset=args.offset,
            use_fit=bool(args.use_fit),
            subtract_left_baseline=bool(args.subtract_left_baseline),
            smooth_method=args.smooth_method,
            smooth_value=float(args.smooth_value),
            bias_scale_factor=float(args.bias_scale_factor),
        )
        results = package["results"]
        data_npz = out_dir / "waterfall_outputs.npz"
        np.savez_compressed(
            data_npz,
            indices=results["indices"],
            neg_v=results["neg"]["v"],
            neg_y_vis=results["neg"]["y_vis"],
            pos_v=results["pos"]["v"],
            pos_y_vis=results["pos"]["y_vis"],
        )
        table = export_waterfall_table(results)
        table_csv = out_dir / "waterfall_table.csv"
        if table is not None:
            _write_table_csv(
                table_csv,
                {
                    "global_index": table[:, 0].astype(int),
                    "neg_v_mV": table[:, 1],
                    "neg_y_vis": table[:, 2],
                    "pos_v_mV": table[:, 3],
                    "pos_y_vis": table[:, 4],
                },
            )
        payload = waterfall_points_payload(
            results,
            set_index=0,
            name="Waterfall Set 1",
            offset=float(package["parameters"]["offset"]),
            neg_range=package["parameters"]["neg_range"],
            pos_range=package["parameters"]["pos_range"],
            use_fit=bool(args.use_fit),
            bias_scale_factor=float(args.bias_scale_factor),
        )
        points_json = out_dir / "waterfall_points.json"
        _write_json(str(points_json), payload or {})
        report = {
            "schema_version": 1,
            "tool": "analystm waterfall fit",
            "input": {"path": str(Path(args.path).expanduser()), "cube_key": args.cube_key, "bias_key": args.bias_key},
            "algorithm": package["algorithm"],
            "parameters": {
                **package["parameters"],
                "spatial_scale": float(args.spatial_scale),
                "linecut": [float(v) for v in args.linecut] if args.linecut else [],
                "indices": [int(v) for v in np.asarray(selected_indices, dtype=int).ravel()],
            },
            "summary": package["summary"],
            "outputs": {
                "data_npz": str(data_npz),
                "table_csv": str(table_csv),
                "points_json": str(points_json),
            },
        }
    else:
        raise ValueError(f"unknown waterfall command: {args.waterfall_command}")

    _write_json(str(out_dir / "report.json"), report)
    if args.output_json:
        _write_json(args.output_json, report)
    return 0


def _parse_name_key_pairs(values: list[str], label: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for value in values or []:
        if "=" not in str(value):
            raise ValueError(f"{label} must use NAME=KEY syntax")
        name, key = str(value).split("=", 1)
        name = name.strip()
        key = key.strip()
        if not name or not key:
            raise ValueError(f"{label} must include a non-empty NAME and KEY")
        pairs.append((name, key))
    return pairs


def cmd_export(args: argparse.Namespace) -> int:
    from analystm.export import export_algorithm, write_ibw_wave, write_nanonis_grid_3ds, write_nanonis_spec_dat

    npz_path = Path(args.path).expanduser()
    data = np.load(npz_path, allow_pickle=False)
    output = Path(args.output).expanduser()
    header = _load_json_argument(args.header_json) if getattr(args, "header_json", None) else {}

    if args.export_command == "spec-dat":
        pairs = _parse_name_key_pairs(args.column, "--column")
        columns = []
        for name, key in pairs:
            if key not in data.files:
                raise KeyError(f"NPZ key not found for export column: {key}")
            columns.append((name, np.asarray(data[key], dtype=float)))
        write_nanonis_spec_dat(
            output,
            columns,
            header=header,
            extra_comments=args.comment or [],
            experiment=args.experiment,
            saved_date=args.saved_date,
            precision=args.precision,
        )
        report = {
            "schema_version": 1,
            "tool": "analystm export spec-dat",
            "input": {"path": str(npz_path), "columns": [{"name": name, "key": key} for name, key in pairs]},
            "algorithm": export_algorithm("analystm.export.write_nanonis_spec_dat"),
            "parameters": {"precision": int(args.precision), "experiment": args.experiment, "saved_date": args.saved_date},
            "outputs": {"path": str(output)},
        }
    elif args.export_command == "grid-3ds":
        pairs = _parse_name_key_pairs(args.channel, "--channel")
        signals = {}
        for name, key in pairs:
            if key not in data.files:
                raise KeyError(f"NPZ key not found for export channel: {key}")
            signals[name] = np.asarray(data[key], dtype=float)
        bias = np.asarray(data[args.bias_key], dtype=float) if args.bias_key in data.files else None
        topo = np.asarray(data[args.topo_key], dtype=float) if args.topo_key and args.topo_key in data.files else None
        write_nanonis_grid_3ds(
            output,
            signals,
            header=header,
            bias_mV=bias,
            scan_size_nm=args.scan_size_nm,
            topo_map=topo,
        )
        report = {
            "schema_version": 1,
            "tool": "analystm export grid-3ds",
            "input": {"path": str(npz_path), "channels": [{"name": name, "key": key} for name, key in pairs], "bias_key": args.bias_key},
            "algorithm": export_algorithm("analystm.export.write_nanonis_grid_3ds"),
            "parameters": {"scan_size_nm": float(args.scan_size_nm) if args.scan_size_nm is not None else None},
            "outputs": {"path": str(output)},
        }
    elif args.export_command == "ibw":
        arr = _load_npz_array(args.path, args.data_key)
        write_ibw_wave(output, arr, name=args.wave_name)
        report = {
            "schema_version": 1,
            "tool": "analystm export ibw",
            "input": {"path": str(npz_path), "data_key": args.data_key},
            "algorithm": export_algorithm("analystm.export.write_ibw_wave"),
            "parameters": {"wave_name": args.wave_name},
            "outputs": {"path": str(output)},
        }
    else:
        raise ValueError(f"unknown export command: {args.export_command}")

    if args.output_json:
        _write_json(args.output_json, report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="analystm", description="AnalySTM headless STM/SJTM analysis backend")
    parser.add_argument("--version", action="version", version=f"analystm {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_read = sub.add_parser("read", help="Read a spectrum-like file and emit a compact JSON contract")
    p_read.add_argument("path")
    p_read.add_argument("--quick", action="store_true")
    p_read.add_argument("--divider", type=float, default=1.0)
    p_read.add_argument("--divider-explicit", action="store_true")
    p_read.add_argument("--max-channels", type=int, default=80)
    p_read.add_argument("--output-json")
    p_read.set_defaults(func=cmd_read)

    p_plot = sub.add_parser("plot-spectrum", help="Plot one spectrum to a publication-friendly figure")
    p_plot.add_argument("path")
    p_plot.add_argument("--output", required=True)
    p_plot.add_argument("--summary-json")
    p_plot.add_argument("--x-channel", default="")
    p_plot.add_argument("--y-channel", default="")
    p_plot.set_defaults(func=cmd_plot_spectrum)

    p_fit = sub.add_parser("fit-gap", help="Fit a superconducting gap model to one spectrum")
    p_fit.add_argument("path")
    p_fit.add_argument("--output-dir", required=True)
    p_fit.add_argument("--model", default="Two Band s-wave")
    p_fit.add_argument("--fit-abs-max", type=float)
    p_fit.add_argument("--fit-max-starts", type=int, default=16)
    p_fit.add_argument("--time-budget-s", type=float, default=30.0)
    p_fit.add_argument("--x-channel", default="")
    p_fit.add_argument("--y-channel", default="")
    p_fit.set_defaults(func=cmd_fit_gap)

    p_gap = sub.add_parser("gap-map", help="Extract left/right peak and gap maps with the AnalySTM peak fitter")
    p_gap.add_argument("path")
    p_gap.add_argument("--bias-key", default="bias")
    p_gap.add_argument("--cube-key", default="cube")
    p_gap.add_argument("--left-window", nargs=2, type=float, required=True, metavar=("MIN", "MAX"))
    p_gap.add_argument("--right-window", nargs=2, type=float, required=True, metavar=("MIN", "MAX"))
    p_gap.add_argument("--interp-factor", type=int, default=5)
    p_gap.add_argument("--interp-kind", default="cubic")
    p_gap.add_argument("--smooth-param", type=float, default=0.0)
    p_gap.add_argument("--smooth-method", default="Gaussian")
    p_gap.add_argument("--output-dir", required=True)
    p_gap.add_argument("--output-json")
    p_gap.set_defaults(func=cmd_gap_map)

    p_multipeak = sub.add_parser("multipeak", help="Run AnalySTM multipeak linecut fitting")
    multipeak_sub = p_multipeak.add_subparsers(dest="multipeak_command", required=True)
    p_multipeak_fit = multipeak_sub.add_parser("fit", help="Fit Gaussian/Lorentzian multipeak spectra by linecut row")
    p_multipeak_fit.add_argument("path")
    p_multipeak_fit.add_argument("--bias-key", default="bias")
    p_multipeak_fit.add_argument("--position-key", default="position")
    p_multipeak_fit.add_argument("--data-key", default="data")
    p_multipeak_fit.add_argument("--n-peaks", type=int, default=4)
    p_multipeak_fit.add_argument("--peak-count-map", default="", help="JSON object or JSON file mapping row index to peak count")
    p_multipeak_fit.add_argument("--fit-range", nargs=2, type=float, default=(-2.0, 2.0), metavar=("MIN", "MAX"))
    p_multipeak_fit.add_argument("--retry-count", type=int, default=2)
    p_multipeak_fit.add_argument("--r2-threshold", type=float, default=0.8)
    p_multipeak_fit.add_argument("--peak-snr-min", type=float, default=2.0)
    p_multipeak_fit.add_argument("--peak-amp-frac-min", type=float, default=0.03)
    p_multipeak_fit.add_argument("--row-start", type=int, default=None)
    p_multipeak_fit.add_argument("--row-end", type=int, default=None)
    p_multipeak_fit.add_argument("--manual-init-centers", default="", help="JSON object or JSON file mapping row index to initial centers")
    p_multipeak_fit.add_argument("--fixed-sigma", type=float, default=None)
    p_multipeak_fit.add_argument("--peak-profile", choices=("gaussian", "lorentzian"), default="gaussian")
    p_multipeak_fit.add_argument(
        "--background-mode",
        choices=("offset", "full_trace_linear", "igor_cubic"),
        default="offset",
    )
    p_multipeak_fit.add_argument("--random-seed", type=int, default=None)
    p_multipeak_fit.add_argument("--output-dir", required=True)
    p_multipeak_fit.add_argument("--output-json")
    p_multipeak_fit.set_defaults(func=cmd_multipeak)

    p_sjtm = sub.add_parser("sjtm", help="Compute SJTM Ic and superfluid-density metrics without GUI")
    p_sjtm.add_argument("path")
    p_sjtm.add_argument("--bias-key", default="bias")
    p_sjtm.add_argument("--cube-key", default="current")
    p_sjtm.add_argument("--rn-cube-key", default="")
    p_sjtm.add_argument("--g0-cube-key", default="")
    p_sjtm.add_argument("--neg-window", nargs=2, type=float, required=True, metavar=("MIN", "MAX"))
    p_sjtm.add_argument("--pos-window", nargs=2, type=float, required=True, metavar=("MIN", "MAX"))
    p_sjtm.add_argument("--rn-window", nargs=2, type=float, metavar=("MIN", "MAX"))
    p_sjtm.add_argument("--g0-window", nargs=2, type=float, required=True, metavar=("MIN", "MAX"))
    p_sjtm.add_argument("--min-points", type=int, default=5)
    p_sjtm.add_argument("--ic-fit-mode", choices=("quick", "accurate"), default="quick")
    p_sjtm.add_argument("--random-seed", type=int, default=None)
    p_sjtm.add_argument("--output-dir", required=True)
    p_sjtm.add_argument("--output-json")
    p_sjtm.set_defaults(func=cmd_sjtm)

    p_deconv = sub.add_parser("deconvolve", help="Run AnalySTM SIS dI/dV deconvolution without GUI")
    p_deconv.add_argument("path")
    p_deconv.add_argument("--bias-key", default="bias")
    p_deconv.add_argument("--didv-key", default="didv")
    p_deconv.add_argument("--mode", choices=("sis",), default="sis")
    p_deconv.add_argument("--temperature-k", type=float, required=True)
    p_deconv.add_argument("--tip-delta-mev", type=float, default=1.2)
    p_deconv.add_argument("--tip-gamma-mev", type=float, default=0.006)
    p_deconv.add_argument("--pinv-rcond", type=float, default=1e-2)
    p_deconv.add_argument("--dos-broad-sigma-mv", type=float, default=0.17)
    p_deconv.add_argument("--n-grid", type=int, default=0)
    p_deconv.add_argument("--output-dir", required=True)
    p_deconv.add_argument("--output-json")
    p_deconv.set_defaults(func=cmd_deconvolve)

    p_int = sub.add_parser("intensity", help="Linecut intensity, Z-ratio, and peak-align-zero helpers")
    int_sub = p_int.add_subparsers(dest="intensity_command", required=True)
    p_int_process = int_sub.add_parser("process", help="Process a spectra-by-bias intensity matrix")
    p_int_process.add_argument("path")
    p_int_process.add_argument("--bias-key", default="bias")
    p_int_process.add_argument("--data-key", default="spectra")
    p_int_process.add_argument("--mode", choices=("didv", "d2", "neg_d3"), default="didv")
    p_int_process.add_argument("--smooth-method", default="")
    p_int_process.add_argument("--smooth-value", type=float, default=0.0)
    p_int_process.add_argument("--line-interp-factor", type=float, default=1.0)
    p_int_process.add_argument("--bias-interp-factor", type=float, default=1.0)
    p_int_process.add_argument("--bias-range", nargs=2, type=float, metavar=("MIN", "MAX"))
    p_int_process.add_argument("--remove-linear-baseline", action="store_true")
    p_int_process.add_argument("--bias-scale-factor", type=float, default=1.0)
    p_int_process.add_argument("--output-dir", required=True)
    p_int_process.add_argument("--output-json")
    p_int_process.set_defaults(func=cmd_intensity)

    p_int_z = int_sub.add_parser("z-ratio", help="Compute a negative/positive or positive/negative Z-ratio map")
    p_int_z.add_argument("path")
    p_int_z.add_argument("--bias-key", default="bias")
    p_int_z.add_argument("--cube-key", default="cube")
    p_int_z.add_argument("--energy-mv", type=float, required=True)
    p_int_z.add_argument("--numerator", choices=("negative", "positive"), default="negative")
    p_int_z.add_argument("--eps-rel", type=float, default=1e-6)
    p_int_z.add_argument("--output-dir", required=True)
    p_int_z.add_argument("--output-json")
    p_int_z.set_defaults(func=cmd_intensity)

    p_int_align = int_sub.add_parser("peak-align-zero", help="Run AnalySTM peak-align-zero bias calibration")
    p_int_align.add_argument("path")
    p_int_align.add_argument("--bias-key", default="bias")
    p_int_align.add_argument("--cube-key", default="cube")
    p_int_align.add_argument("--neg-window", nargs=2, type=float, required=True, metavar=("MIN", "MAX"))
    p_int_align.add_argument("--pos-window", nargs=2, type=float, required=True, metavar=("MIN", "MAX"))
    p_int_align.add_argument("--output-dir", required=True)
    p_int_align.add_argument("--output-json")
    p_int_align.set_defaults(func=cmd_intensity)

    p_qpi = sub.add_parser("qpi", help="QPI symmetry and PR-QPI/PQPI headless helpers")
    qpi_sub = p_qpi.add_subparsers(dest="qpi_command", required=True)
    p_qpi_sym = qpi_sub.add_parser("symmetry", help="Rotate-average a QPI image or energy stack")
    p_qpi_sym.add_argument("path")
    p_qpi_sym.add_argument("--qpi-key", default="qpi")
    p_qpi_sym.add_argument("--order", type=int, choices=(2, 3, 4, 6), default=4)
    p_qpi_sym.add_argument("--center", nargs=2, type=float, metavar=("X", "Y"))
    p_qpi_sym.add_argument("--nan-policy", choices=("ignore", "zero"), default="ignore")
    p_qpi_sym.add_argument("--output-dir", required=True)
    p_qpi_sym.add_argument("--output-json")
    p_qpi_sym.set_defaults(func=cmd_qpi)

    p_qpi_pr = qpi_sub.add_parser("pr-qpi", help="Compute AnalySTM PR-QPI/PQPI positive and negative volumes")
    p_qpi_pr.add_argument("path")
    p_qpi_pr.add_argument("--cube-key", default="cube")
    p_qpi_pr.add_argument("--bias-key", default="bias")
    p_qpi_pr.add_argument("--slider-min", type=int, required=True)
    p_qpi_pr.add_argument("--slider-max", type=int, required=True)
    p_qpi_pr.add_argument("--multi-impurity", action="store_true")
    p_qpi_pr.add_argument("--window", default="Hanning")
    p_qpi_pr.add_argument("--no-mask-dc", action="store_true")
    p_qpi_pr.add_argument("--mask-radius-px", type=float, default=1.5)
    p_qpi_pr.add_argument("--scale-mode", default="Signed Sqrt")
    p_qpi_pr.add_argument("--output-dir", required=True)
    p_qpi_pr.add_argument("--output-json")
    p_qpi_pr.set_defaults(func=cmd_qpi)

    p_qpi_fft = qpi_sub.add_parser("fft-volume", help="Compute AnalySTM QPI display FFT magnitude volume")
    p_qpi_fft.add_argument("path")
    p_qpi_fft.add_argument("--cube-key", default="cube")
    p_qpi_fft.add_argument("--window", default="Hanning")
    p_qpi_fft.add_argument("--no-mask-dc", action="store_true")
    p_qpi_fft.add_argument("--mask-radius-px", type=float, default=1.5)
    p_qpi_fft.add_argument("--scale-mode", default="Linear")
    p_qpi_fft.add_argument("--output-dir", required=True)
    p_qpi_fft.add_argument("--output-json")
    p_qpi_fft.set_defaults(func=cmd_qpi)

    p_qpi_1d = qpi_sub.add_parser("1d-fft", help="Compute AnalySTM 1D-QPI linecut K-E FFT")
    p_qpi_1d.add_argument("path")
    p_qpi_1d.add_argument("--cube-key", default="cube")
    p_qpi_1d.add_argument("--bias-key", default="bias")
    p_qpi_1d.add_argument("--scan-size-nm", nargs=2, type=float, required=True, metavar=("SX", "SY"))
    p_qpi_1d.add_argument("--p1", nargs=2, type=float, metavar=("X_NM", "Y_NM"))
    p_qpi_1d.add_argument("--p2", nargs=2, type=float, metavar=("X_NM", "Y_NM"))
    p_qpi_1d.add_argument("--cube-order", choices=("xyb", "yxb"), default="xyb")
    p_qpi_1d.add_argument("--background-mode", default="None")
    p_qpi_1d.add_argument("--window", default="none")
    p_qpi_1d.add_argument("--no-mask-q0", action="store_true")
    p_qpi_1d.add_argument("--mask-radius-px", type=float, default=1.5)
    p_qpi_1d.add_argument("--scale-mode", default="Sqrt")
    p_qpi_1d.add_argument("--smooth-size", type=int, default=0)
    p_qpi_1d.add_argument("--output-dir", required=True)
    p_qpi_1d.add_argument("--output-json")
    p_qpi_1d.set_defaults(func=cmd_qpi)

    p_qpi_filter = qpi_sub.add_parser("fft-filter", help="Apply AnalySTM QPI FFT ROI filter to a cube")
    p_qpi_filter.add_argument("path")
    p_qpi_filter.add_argument("--cube-key", default="cube")
    p_qpi_filter.add_argument("--scan-size-nm", nargs=2, type=float, required=True, metavar=("SX", "SY"))
    p_qpi_filter.add_argument("--circle", nargs=3, type=float, action="append", metavar=("KX", "KY", "RADIUS"))
    p_qpi_filter.add_argument("--rect", nargs=4, type=float, action="append", metavar=("X0", "X1", "Y0", "Y1"))
    p_qpi_filter.add_argument("--no-include-neg", action="store_true")
    p_qpi_filter.add_argument("--mode", choices=("pass", "stop"), default="pass")
    p_qpi_filter.add_argument("--invert", action="store_true")
    p_qpi_filter.add_argument("--window", default="Hanning")
    p_qpi_filter.add_argument("--scale-mode", default="Linear")
    p_qpi_filter.add_argument("--output-dir", required=True)
    p_qpi_filter.add_argument("--output-json")
    p_qpi_filter.set_defaults(func=cmd_qpi)

    p_qpi_real = qpi_sub.add_parser("real-phase", help="Compute AnalySTM qpi_real_phase p_LL map from reference and target images")
    p_qpi_real.add_argument("path")
    p_qpi_real.add_argument("--ref-key", default="ref")
    p_qpi_real.add_argument("--target-key", default="target")
    p_qpi_real.add_argument("--q1", nargs=2, type=float, required=True, metavar=("QY", "QX"))
    p_qpi_real.add_argument("--q2", nargs=2, type=float, required=True, metavar=("QY", "QX"))
    p_qpi_real.add_argument("--sigma-px", type=float, default=3.0)
    p_qpi_real.add_argument("--window", default="none")
    p_qpi_real.add_argument("--detrend-target", action="store_true")
    p_qpi_real.add_argument("--output-dir", required=True)
    p_qpi_real.add_argument("--output-json")
    p_qpi_real.set_defaults(func=cmd_qpi)

    p_spstm = sub.add_parser("spstm", help="SPSTM spectrum, map, and QPI contrast helpers")
    spstm_sub = p_spstm.add_subparsers(dest="spstm_command", required=True)
    p_spstm_didv = spstm_sub.add_parser("didv", help="Process SPSTM dI/dV contrast spectra")
    p_spstm_didv.add_argument("path")
    p_spstm_didv.add_argument("--x-key", default="x")
    p_spstm_didv.add_argument("--x-b-key", default="")
    p_spstm_didv.add_argument("--a-key", default="a")
    p_spstm_didv.add_argument("--b-key", default="")
    p_spstm_didv.add_argument("--bias-scale-a", type=float, default=1.0)
    p_spstm_didv.add_argument("--bias-scale-b", type=float, default=1.0)
    p_spstm_didv.add_argument("--offset", type=float, default=0.0)
    p_spstm_didv.add_argument("--symmetrize", action="store_true")
    p_spstm_didv.add_argument("--smooth-method-a", default="None")
    p_spstm_didv.add_argument("--smooth-method-b", default="None")
    p_spstm_didv.add_argument("--smooth-param-a", type=float, default=0.0)
    p_spstm_didv.add_argument("--smooth-param-b", type=float, default=0.0)
    p_spstm_didv.add_argument("--norm-mode-a", default="None")
    p_spstm_didv.add_argument("--norm-mode-b", default="None")
    p_spstm_didv.add_argument("--output-dir", required=True)
    p_spstm_didv.add_argument("--output-json")
    p_spstm_didv.set_defaults(func=cmd_spstm)

    p_spstm_r90 = spstm_sub.add_parser("qpi-r90", help="Compute SPSTM QPI R90 anisotropy")
    p_spstm_r90.add_argument("path")
    p_spstm_r90.add_argument("--map-key", default="qpi")
    p_spstm_r90.add_argument("--operation", choices=("diff", "sym"), default="diff")
    p_spstm_r90.add_argument("--rotation", choices=("ccw", "clockwise"), default="ccw")
    p_spstm_r90.add_argument("--output-dir", required=True)
    p_spstm_r90.add_argument("--output-json")
    p_spstm_r90.set_defaults(func=cmd_spstm)

    p_spstm_spin = spstm_sub.add_parser("qpi-spin", help="Compute SPSTM +/- bias spin contrast")
    p_spstm_spin.add_argument("path")
    p_spstm_spin.add_argument("--pos-key", default="pos")
    p_spstm_spin.add_argument("--neg-key", default="neg")
    p_spstm_spin.add_argument("--output-dir", required=True)
    p_spstm_spin.add_argument("--output-json")
    p_spstm_spin.set_defaults(func=cmd_spstm)

    p_topo = sub.add_parser("topography", help="Topography correction and LF drift helpers")
    topo_sub = p_topo.add_subparsers(dest="topography_command", required=True)
    p_topo_lf = topo_sub.add_parser("lf-drift", help="Run AnalySTM low-frequency drift correction")
    p_topo_lf.add_argument("path")
    p_topo_lf.add_argument("--image-key", default="topo")
    p_topo_lf.add_argument("--q1", nargs=2, type=float, metavar=("QY", "QX"))
    p_topo_lf.add_argument("--q2", nargs=2, type=float, metavar=("QY", "QX"))
    p_topo_lf.add_argument("--q-point1", nargs=2, type=float, metavar=("PX", "PY"))
    p_topo_lf.add_argument("--q-point2", nargs=2, type=float, metavar=("PX", "PY"))
    p_topo_lf.add_argument("--sigma", type=float, default=3.0)
    p_topo_lf.add_argument("--search-r", type=int, default=3)
    p_topo_lf.add_argument("--no-local-max", action="store_true")
    p_topo_lf.add_argument("--gaussian", action="store_true")
    p_topo_lf.add_argument("--gaussian-r", type=int, default=3)
    p_topo_lf.add_argument("--output-dir", required=True)
    p_topo_lf.add_argument("--output-json")
    p_topo_lf.set_defaults(func=cmd_topography)

    p_topo_filter = topo_sub.add_parser("fft-filter", help="Apply AnalySTM topography FFT ROI filter")
    p_topo_filter.add_argument("path")
    p_topo_filter.add_argument("--image-key", default="topo")
    p_topo_filter.add_argument("--scan-size-nm", nargs=2, type=float, required=True, metavar=("SX", "SY"))
    p_topo_filter.add_argument("--circle", nargs=3, type=float, action="append", metavar=("KX", "KY", "RADIUS"))
    p_topo_filter.add_argument("--rect", nargs=4, type=float, action="append", metavar=("X0", "X1", "Y0", "Y1"))
    p_topo_filter.add_argument("--no-include-neg", action="store_true")
    p_topo_filter.add_argument("--mode", choices=("pass", "stop"), default="pass")
    p_topo_filter.add_argument("--invert", action="store_true")
    p_topo_filter.add_argument("--background-mode", default="Raw")
    p_topo_filter.add_argument("--window", default="Hanning")
    p_topo_filter.add_argument("--scale-mode", default="Log")
    p_topo_filter.add_argument("--output-dir", required=True)
    p_topo_filter.add_argument("--output-json")
    p_topo_filter.set_defaults(func=cmd_topography)

    p_topo_display = topo_sub.add_parser("display-fft", help="Compute AnalySTM topography display background and FFT payload")
    p_topo_display.add_argument("path")
    p_topo_display.add_argument("--image-key", default="topo")
    p_topo_display.add_argument("--scan-size-nm", type=float, required=True)
    p_topo_display.add_argument("--background-mode", default="Raw")
    p_topo_display.add_argument("--window", default="Hanning")
    p_topo_display.add_argument("--scale-mode", default="Log")
    p_topo_display.add_argument("--output-dir", required=True)
    p_topo_display.add_argument("--output-json")
    p_topo_display.set_defaults(func=cmd_topography)

    p_spec = sub.add_parser("spectroscopy", help="Point-spectroscopy display processing helpers")
    spec_sub = p_spec.add_subparsers(dest="spectroscopy_command", required=True)
    p_spec_process = spec_sub.add_parser("process", help="Run AnalySTM spectroscopy display pipeline")
    p_spec_process.add_argument("path")
    p_spec_process.add_argument("--x-key", default="bias")
    p_spec_process.add_argument("--y-key", default="didv")
    p_spec_process.add_argument("--ref-current-key", default="")
    p_spec_process.add_argument("--offset", type=float, default=0.0)
    p_spec_process.add_argument("--auto-offset", action="store_true")
    p_spec_process.add_argument("--x-scale", type=float, default=1.0)
    p_spec_process.add_argument("--symmetrize", action="store_true")
    p_spec_process.add_argument("--smooth-method", default="")
    p_spec_process.add_argument("--smooth-param", type=float, default=0.0)
    p_spec_process.add_argument("--norm-mode", default="")
    p_spec_process.add_argument("--derivative-order", type=int, choices=(1, 2), default=1)
    p_spec_process.add_argument("--derivative-smooth", type=float, default=0.0)
    p_spec_process.add_argument("--export-kind", choices=("spectrum", "derivative"), default="spectrum")
    p_spec_process.add_argument("--output-dir", required=True)
    p_spec_process.add_argument("--output-json")
    p_spec_process.set_defaults(func=cmd_spectroscopy)

    p_path_viz = sub.add_parser("path-viz", help="Surface survey path table helpers")
    path_viz_sub = p_path_viz.add_subparsers(dest="path_viz_command", required=True)
    p_path_build = path_viz_sub.add_parser("build", help="Build a path log from move batches JSON")
    p_path_build.add_argument("path")
    p_path_build.add_argument("--output-dir", required=True)
    p_path_build.add_argument("--output-json")
    p_path_build.set_defaults(func=cmd_path_viz)

    p_publication = sub.add_parser("publication", help="Publication figure payload helpers")
    publication_sub = p_publication.add_subparsers(dest="publication_command", required=True)
    p_pub_payload = publication_sub.add_parser("payload", help="Build a headless publication payload summary from NPZ arrays")
    p_pub_payload.add_argument("path")
    p_pub_payload.add_argument("--image-key", default="")
    p_pub_payload.add_argument("--image-extent", nargs=4, type=float, metavar=("X0", "X1", "Y0", "Y1"))
    p_pub_payload.add_argument("--contrast-mode", choices=("source", "robust", "symmetric", "full"), default="full")
    p_pub_payload.add_argument("--x-key", default="")
    p_pub_payload.add_argument("--y-key", default="")
    p_pub_payload.add_argument("--line-label", default="")
    p_pub_payload.add_argument("--title", default="")
    p_pub_payload.add_argument("--xlabel", default="")
    p_pub_payload.add_argument("--ylabel", default="")
    p_pub_payload.add_argument("--output-dir", required=True)
    p_pub_payload.add_argument("--output-json")
    p_pub_payload.set_defaults(func=cmd_publication)

    p_waterfall = sub.add_parser("waterfall", help="Linecut-map waterfall fitting and peak-align-zero helpers")
    waterfall_sub = p_waterfall.add_subparsers(dest="waterfall_command", required=True)
    p_wf_fit = waterfall_sub.add_parser("fit", help="Run AnalySTM waterfall peak extraction for selected spectra")
    p_wf_fit.add_argument("path")
    p_wf_fit.add_argument("--cube-key", default="cube")
    p_wf_fit.add_argument("--bias-key", default="bias")
    p_wf_fit.add_argument("--linecut", nargs=4, type=float, metavar=("X0", "Y0", "X1", "Y1"))
    p_wf_fit.add_argument("--indices", nargs="*", type=int)
    p_wf_fit.add_argument("--allow-full-grid", action="store_true")
    p_wf_fit.add_argument("--neg-range", nargs=2, type=float, required=True, metavar=("MIN", "MAX"))
    p_wf_fit.add_argument("--pos-range", nargs=2, type=float, required=True, metavar=("MIN", "MAX"))
    p_wf_fit.add_argument("--offset", type=float, default=None)
    p_wf_fit.add_argument("--use-fit", action="store_true")
    p_wf_fit.add_argument("--subtract-left-baseline", action="store_true")
    p_wf_fit.add_argument("--smooth-method", default="")
    p_wf_fit.add_argument("--smooth-value", type=float, default=0.0)
    p_wf_fit.add_argument("--bias-scale-factor", type=float, default=1.0)
    p_wf_fit.add_argument("--spatial-scale", type=float, default=1.0)
    p_wf_fit.add_argument("--output-dir", required=True)
    p_wf_fit.add_argument("--output-json")
    p_wf_fit.set_defaults(func=cmd_waterfall)

    p_wf_align = waterfall_sub.add_parser("peak-align-zero", help="Apply AnalySTM waterfall peak-align-zero calibration to a grid")
    p_wf_align.add_argument("path")
    p_wf_align.add_argument("--cube-key", default="cube")
    p_wf_align.add_argument("--bias-key", default="bias")
    p_wf_align.add_argument("--neg-range", nargs=2, type=float, required=True, metavar=("MIN", "MAX"))
    p_wf_align.add_argument("--pos-range", nargs=2, type=float, required=True, metavar=("MIN", "MAX"))
    p_wf_align.add_argument("--output-dir", required=True)
    p_wf_align.add_argument("--output-json")
    p_wf_align.set_defaults(func=cmd_waterfall)

    p_hist = sub.add_parser("histogram", help="Compute AnalySTM histogram stats and KDE trace")
    p_hist.add_argument("path")
    p_hist.add_argument("--data-key", default="")
    p_hist.add_argument("--layer-index", type=int, default=0)
    p_hist.add_argument("--background-mode", default="Raw")
    p_hist.add_argument("--vmin", type=float, default=None)
    p_hist.add_argument("--vmax", type=float, default=None)
    p_hist.add_argument("--bin-size", type=float, default=None)
    p_hist.add_argument("--fit-bw-scale", type=float, default=1.0)
    p_hist.add_argument("--fit-max-samples", type=int, default=20000)
    p_hist.add_argument("--output-dir", required=True)
    p_hist.add_argument("--output-json")
    p_hist.set_defaults(func=cmd_histogram)

    p_crop = sub.add_parser("crop", help="Headless map/cube crop helpers")
    crop_sub = p_crop.add_subparsers(dest="crop_command", required=True)
    p_crop_map = crop_sub.add_parser("map", help="Crop a 2D map, SXM channel, or 3DS cube with AnalySTM map-crop geometry")
    p_crop_map.add_argument("path")
    p_crop_map.add_argument("--data-key", default="")
    p_crop_map.add_argument("--kind", choices=("map", "sxm", "3ds"), default="map")
    p_crop_map.add_argument("--center-px", nargs=2, type=float, required=True, metavar=("X", "Y"))
    p_crop_map.add_argument("--side-px", type=float, required=True)
    p_crop_map.add_argument("--angle-deg", type=float, default=0.0)
    p_crop_map.add_argument("--scan-size-nm", nargs=2, type=float, default=[100.0, 100.0], metavar=("SX", "SY"))
    p_crop_map.add_argument("--direction", choices=("forward", "backward"), default="forward")
    p_crop_map.add_argument("--undo-orientation", action="store_true")
    p_crop_map.add_argument("--header-json", default="")
    p_crop_map.add_argument("--output-dir", required=True)
    p_crop_map.add_argument("--output-json")
    p_crop_map.set_defaults(func=cmd_crop)

    p_export = sub.add_parser("export", help="Nanonis/Igor headless export helpers")
    export_sub = p_export.add_subparsers(dest="export_command", required=True)
    p_export_dat = export_sub.add_parser("spec-dat", help="Write a Nanonis-style spectroscopy .dat file")
    p_export_dat.add_argument("path")
    p_export_dat.add_argument("--output", required=True)
    p_export_dat.add_argument("--column", action="append", required=True, help="Column mapping as NAME=NPZ_KEY")
    p_export_dat.add_argument("--header-json")
    p_export_dat.add_argument("--comment", action="append")
    p_export_dat.add_argument("--experiment")
    p_export_dat.add_argument("--saved-date")
    p_export_dat.add_argument("--precision", type=int, default=7)
    p_export_dat.add_argument("--output-json")
    p_export_dat.set_defaults(func=cmd_export)

    p_export_grid = export_sub.add_parser("grid-3ds", help="Write a Nanonis-style grid .3ds file from (x,y,bias) cubes")
    p_export_grid.add_argument("path")
    p_export_grid.add_argument("--output", required=True)
    p_export_grid.add_argument("--channel", action="append", required=True, help="Channel mapping as NAME=NPZ_KEY")
    p_export_grid.add_argument("--bias-key", default="bias")
    p_export_grid.add_argument("--topo-key", default="")
    p_export_grid.add_argument("--scan-size-nm", type=float)
    p_export_grid.add_argument("--header-json")
    p_export_grid.add_argument("--output-json")
    p_export_grid.set_defaults(func=cmd_export)

    p_export_ibw = export_sub.add_parser("ibw", help="Write an Igor Binary Wave using optional igorwriter")
    p_export_ibw.add_argument("path")
    p_export_ibw.add_argument("--output", required=True)
    p_export_ibw.add_argument("--data-key", default="data")
    p_export_ibw.add_argument("--wave-name")
    p_export_ibw.add_argument("--output-json")
    p_export_ibw.set_defaults(func=cmd_export)

    p_phase = sub.add_parser("phase-lockin", help="Run complex 2D lock-in phase extraction")
    p_phase.add_argument("path")
    p_phase.add_argument("--q", action="append", required=True, help="q vector as label=qx,qy cycles/nm")
    p_phase.add_argument("--scan-size-nm", nargs=2, type=float, required=True, metavar=("SX", "SY"))
    p_phase.add_argument("--sigma-px", type=float, default=3.0)
    p_phase.add_argument("--window", default="hann")
    p_phase.add_argument("--threshold", nargs="*", type=float, default=[0.1, 0.2, 0.3])
    p_phase.add_argument("--output-dir", required=True)
    p_phase.set_defaults(func=cmd_phase_lockin)

    p_bragg = sub.add_parser("bragg", help="Bragg/QPI policy and q-selection helpers")
    bragg_sub = p_bragg.add_subparsers(dest="bragg_command", required=True)
    p_bragg_policy = bragg_sub.add_parser("policy")
    p_bragg_policy.add_argument("--user-q", action="store_true")
    p_bragg_policy.add_argument("--user-roi", action="store_true")
    p_bragg_policy.add_argument("--allow-agent-search", action="store_true")
    p_bragg_policy.add_argument("--output-json")
    p_bragg_policy.set_defaults(func=cmd_bragg)

    p_atom = sub.add_parser("atom", help="AI atom-detection adjacent helpers")
    atom_sub = p_atom.add_subparsers(dest="atom_command", required=True)
    p_atom_scale = atom_sub.add_parser("recommend-scale")
    p_atom_scale.add_argument("--shape-yx", nargs=2, type=int, required=True, metavar=("Y", "X"))
    p_atom_scale.add_argument("--scan-size-nm", nargs=2, type=float, required=True, metavar=("SX", "SY"))
    p_atom_scale.add_argument("--resize-ratio", type=float, required=True)
    p_atom_scale.add_argument("--expected-spacing-nm", type=float, required=True)
    p_atom_scale.add_argument("--target-inference-pixel-nm", type=float, default=0.026)
    p_atom_scale.add_argument("--output-json")
    p_atom_scale.set_defaults(func=cmd_atom)

    p_atom_qc = atom_sub.add_parser("lattice-qc")
    p_atom_qc.add_argument("atoms_csv")
    p_atom_qc.add_argument("--x-column", default="x_nm")
    p_atom_qc.add_argument("--y-column", default="y_nm")
    p_atom_qc.add_argument("--expected-spacing-nm", type=float, default=None)
    p_atom_qc.add_argument("--scan-size-nm", nargs=2, type=float, metavar=("SX", "SY"), default=None)
    p_atom_qc.add_argument("--allow-qc-fail", action="store_true")
    p_atom_qc.add_argument("--output-json")
    p_atom_qc.set_defaults(func=cmd_atom)

    p_atom_wipe = atom_sub.add_parser("wipe-regions")
    p_atom_wipe.add_argument("atoms_csv")
    p_atom_wipe.add_argument("--regions-json", required=True)
    p_atom_wipe.add_argument("--output-csv", default="")
    p_atom_wipe.add_argument("--class-key", default="class")
    p_atom_wipe.add_argument("--output-key", default="analysis_class")
    p_atom_wipe.add_argument("--wipe-prefix", default="excluded")
    p_atom_wipe.add_argument("--output-json")
    p_atom_wipe.set_defaults(func=cmd_atom)

    p_dw = sub.add_parser("domain-wall", help="Domain-wall mask and policy helpers")
    dw_sub = p_dw.add_subparsers(dest="domain_wall_command", required=True)
    p_dw_policy = dw_sub.add_parser("policy")
    p_dw_policy.add_argument("--regions-json", default="")
    p_dw_policy.add_argument("--allow-agent-proposal", action="store_true")
    p_dw_policy.add_argument("--output-json")
    p_dw_policy.set_defaults(func=cmd_domain_wall)

    p_dw_build = dw_sub.add_parser("build-masks")
    p_dw_build.add_argument("--shape-yx", nargs=2, type=int, metavar=("Y", "X"), required=True)
    p_dw_build.add_argument("--scan-size-nm", nargs=2, type=float, metavar=("SX", "SY"), required=True)
    p_dw_build.add_argument("--regions-json", required=True)
    p_dw_build.add_argument("--near-width-nm", type=float, default=0.0)
    p_dw_build.add_argument("--edge-exclude-nm", type=float, default=0.0)
    p_dw_build.add_argument("--refine-map", default="")
    p_dw_build.add_argument("--refine-percentile", type=float, default=None)
    p_dw_build.add_argument("--refine-mode", choices=("above", "below"), default="above")
    p_dw_build.add_argument("--output-dir", required=True)
    p_dw_build.add_argument("--output-json")
    p_dw_build.set_defaults(func=cmd_domain_wall)

    p_dw_stats = dw_sub.add_parser("stats")
    p_dw_stats.add_argument("map")
    p_dw_stats.add_argument("--masks-npz", default="")
    p_dw_stats.add_argument("--regions-json", default="")
    p_dw_stats.add_argument("--scan-size-nm", nargs=2, type=float, metavar=("SX", "SY"))
    p_dw_stats.add_argument("--near-width-nm", type=float, default=0.0)
    p_dw_stats.add_argument("--edge-exclude-nm", type=float, default=0.0)
    p_dw_stats.add_argument("--refine-with-metric", action="store_true")
    p_dw_stats.add_argument("--refine-percentile", type=float, default=None)
    p_dw_stats.add_argument("--refine-mode", choices=("above", "below"), default="above")
    p_dw_stats.add_argument("--metric-name", default="metric")
    p_dw_stats.add_argument("--output-dir", required=True)
    p_dw_stats.add_argument("--output-json")
    p_dw_stats.set_defaults(func=cmd_domain_wall)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
