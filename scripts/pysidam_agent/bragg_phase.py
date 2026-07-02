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


def _parse_pair(text: str) -> list[float]:
    parts = [item.strip() for item in str(text).split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("expected two comma-separated numbers, e.g. 2.5,0.0")
    return [float(parts[0]), float(parts[1])]


def _parse_roi(values: list[str] | None) -> dict[str, float] | None:
    if not values:
        return None
    if len(values) != 4:
        raise argparse.ArgumentTypeError("--roi expects qx_min qx_max qy_min qy_max")
    qx_min, qx_max, qy_min, qy_max = [float(v) for v in values]
    return {"qx_min": qx_min, "qx_max": qx_max, "qy_min": qy_min, "qy_max": qy_max}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
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
        for row in rows:
            writer.writerow(row)


def _flatten(prefix: str, payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in payload.items():
        name = f"{prefix}_{key}" if prefix else str(key)
        if isinstance(value, (list, tuple)):
            out[name] = json.dumps(value)
        else:
            out[name] = value
    return out


def _load_sxm(path: Path, channel: str, direction: str) -> tuple[Any, dict[str, Any]]:
    from pysidam.core.nanonis_io import read_nanonis_file
    from pysidam_agent_core.bragg_phase import selected_sxm_map

    nf = read_nanonis_file(path)
    obj = nf.obj
    header = getattr(obj, "header", {}) or {}
    signals = getattr(obj, "signals", {}) or {}
    if channel not in signals:
        raise KeyError(f"{path.name}: channel {channel!r} not found; available={list(signals.keys())}")
    z_map = selected_sxm_map(signals, channel=channel, direction=direction, header=header)
    return z_map, header


def _resolve_source(raw_root: Path, name: str) -> Path:
    path = Path(name).expanduser()
    if path.is_absolute():
        return path
    return raw_root / name


def command_policy(args: argparse.Namespace) -> int:
    from pysidam_agent_core.bragg_phase import q_selection_policy

    roi = _parse_roi(args.roi)
    policy = q_selection_policy(
        user_q=args.user_q,
        user_roi=roi,
        allow_agent_search=args.allow_agent_search,
    )
    payload = {
        "tool": "pysidam_agent/bragg_phase.py policy",
        "policy": policy,
        "user_q": args.user_q,
        "user_roi": roi,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default))
    return 0


def command_inspect_roi(args: argparse.Namespace) -> int:
    import numpy as np
    from pysidam.core.fft_windowing import build_windowed_fft_complex
    from pysidam_agent_core.bragg_phase import (
        find_peak_in_roi,
        preprocess_topography,
        q_axes_cycles_per_nm,
        scan_size_nm_xy,
    )

    roi = _parse_roi(args.roi)
    if roi is None:
        raise SystemExit("--roi is required for inspect-roi")
    rows: list[dict[str, Any]] = []
    results: dict[str, Any] = {}
    for raw in args.paths:
        path = Path(raw).expanduser()
        z_map, header = _load_sxm(path, channel=args.channel, direction=args.direction)
        z_proc, preprocess_info = preprocess_topography(z_map)
        scan_size = scan_size_nm_xy(header, default=args.default_scan_size_nm)
        fft_complex = build_windowed_fft_complex(z_proc, window_name=args.window)
        log_amp = np.log(np.abs(fft_complex) + 1e-12)
        qx_axis, qy_axis = q_axes_cycles_per_nm(z_proc.shape, scan_size)
        plus = find_peak_in_roi(log_amp, qx_axis, qy_axis, roi, sign=1)
        minus = find_peak_in_roi(log_amp, qx_axis, qy_axis, roi, sign=-1)
        file_result = {
            "source_file": str(path),
            "channel": args.channel,
            "direction": args.direction,
            "window": args.window,
            "shape_yx": [int(z_proc.shape[0]), int(z_proc.shape[1])],
            "scan_size_nm_xy": [float(scan_size[0]), float(scan_size[1])],
            "q_resolution_cycles_per_nm_xy": [
                float(abs(qx_axis[1] - qx_axis[0])) if qx_axis.size > 1 else None,
                float(abs(qy_axis[1] - qy_axis[0])) if qy_axis.size > 1 else None,
            ],
            "roi_plus": roi,
            "preprocessing": preprocess_info,
            "q_plus": plus,
            "q_minus": minus,
            "plus_minus_q_abs_difference_cycles_per_nm": float(
                abs(plus["q_abs_cycles_per_nm"] - minus["q_abs_cycles_per_nm"])
            ),
            "plus_minus_log_amp_difference": float(plus["log_amp"] - minus["log_amp"]),
        }
        results[path.name] = file_result
        rows.append({"file": path.name, "sign": "q_plus", **_flatten("", plus)})
        rows.append({"file": path.name, "sign": "q_minus", **_flatten("", minus)})

    payload = {
        "tool": "pysidam_agent/bragg_phase.py inspect-roi",
        "count": len(results),
        "results": results,
    }
    if args.output_json:
        write_json(Path(args.output_json), payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default))
    if args.output_csv:
        _write_csv(Path(args.output_csv), rows)
    return 0


def _circular_stats(phases: Any) -> dict[str, Any]:
    import math
    import numpy as np

    vals = np.asarray(phases, dtype=float)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return {"n": 0, "mean_angle_rad": None, "mean_angle_deg": None, "resultant_length": None}
    vec = np.exp(1j * vals)
    mean_vec = np.mean(vec)
    r = float(np.abs(mean_vec))
    mean_angle = float(np.angle(mean_vec))
    return {
        "n": int(vals.size),
        "mean_angle_rad": mean_angle,
        "mean_angle_deg": float(np.degrees(mean_angle)),
        "resultant_length": r,
        "circular_std_rad": float(math.sqrt(max(0.0, -2.0 * math.log(max(r, 1e-15))))) if r > 0 else None,
    }


def command_lockin_from_decision(args: argparse.Namespace) -> int:
    import numpy as np
    from pysidam.qpi_analysis.qpi_phase_analysis import _unwrap_phase_2d, lockin_phase_extraction
    from pysidam_agent_core.bragg_phase import amp_mask, preprocess_topography, scan_size_nm_xy, wrap_pi

    decision_path = Path(args.decision).expanduser()
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    approved = decision.get("approved_parameters", decision)
    q_vectors = approved["q_vectors"]
    lockin = approved.get("lockin_parameters", {})
    channel = args.channel or approved.get("channel", "Z")
    direction = args.direction or approved.get("direction", "forward")
    sigma_px = float(args.sigma_px if args.sigma_px is not None else lockin.get("sigma_px", 3.0))
    window = args.window or lockin.get("fourier_window", "hann")
    amp_cfg = lockin.get("amplitude_mask", {})
    thresholds = [float(x) for x in amp_cfg.get("record_threshold_sweep", [0.1, 0.2, 0.3])]
    primary_threshold = float(amp_cfg.get("suggested_threshold_fraction_of_max", 0.2))

    raw_root = Path(args.raw_root).expanduser()
    out_root = Path(args.output_dir).expanduser()
    data_dir = out_root / "data"
    table_dir = out_root / "tables"
    data_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)

    stats_rows: list[dict[str, Any]] = []
    results: dict[str, Any] = {}
    for name, q_info in q_vectors.items():
        path = _resolve_source(raw_root, name)
        z_map, header = _load_sxm(path, channel=channel, direction=direction)
        z_proc, preprocess_info = preprocess_topography(z_map)
        ny, nx = z_proc.shape
        scan_size = scan_size_nm_xy(header, default=args.default_scan_size_nm)
        center_yx = np.asarray(((ny - 1) / 2.0, (nx - 1) / 2.0), dtype=float)
        per_file: dict[str, Any] = {
            "source_file": str(path),
            "channel": channel,
            "direction": direction,
            "shape_yx": [int(ny), int(nx)],
            "scan_size_nm_xy": [float(scan_size[0]), float(scan_size[1])],
            "preprocessing": preprocess_info,
            "q_results": {},
        }
        save_payload: dict[str, Any] = {"z_map_yx": z_map, "z_processed_yx": z_proc}

        for sign_name in ("q_plus", "q_minus"):
            q_offset = np.asarray(q_info[f"{sign_name}_offset_px_yx"], dtype=float)
            q_abs_yx = center_yx + q_offset
            amp, phase_wrapped, complex_field = lockin_phase_extraction(
                z_proc,
                q_abs_yx,
                sigma_px=sigma_px,
                window=window,
                unwrap_phase=False,
            )
            phase_wrapped = wrap_pi(phase_wrapped)
            phase_unwrapped = np.asarray(_unwrap_phase_2d(phase_wrapped), dtype=float)
            save_payload[f"{sign_name}_amp"] = amp
            save_payload[f"{sign_name}_phase_wrapped"] = phase_wrapped
            save_payload[f"{sign_name}_phase_unwrapped"] = phase_unwrapped
            save_payload[f"{sign_name}_complex"] = complex_field

            masks = {str(thr): amp_mask(amp, thr) for thr in thresholds}
            for thr, mask in masks.items():
                suffix = str(float(thr)).rstrip("0").rstrip(".").replace(".", "p")
                save_payload[f"{sign_name}_mask_amp_{suffix}"] = mask
                stats_rows.append(
                    {
                        "file": name,
                        "sign": sign_name,
                        "threshold_fraction_of_amp_max": float(thr),
                        "pixels_in_mask": int(np.count_nonzero(mask)),
                        "mask_fraction": float(np.count_nonzero(mask) / mask.size),
                        "amp_max": float(np.nanmax(amp)),
                        **_circular_stats(phase_wrapped[mask]),
                    }
                )
            q_cycles = q_info.get(f"{sign_name}_cycles_per_nm_xy")
            per_file["q_results"][sign_name] = {
                "q_cycles_per_nm_xy": q_cycles,
                "q_offset_px_yx": q_offset.tolist(),
                "q_abs_px_yx_for_pysidam_lockin": q_abs_yx.tolist(),
                "sigma_px": sigma_px,
                "window": window,
                "primary_threshold_fraction_of_amp_max": primary_threshold,
            }

        stem = Path(name).stem.lower()
        npz_path = data_dir / f"{stem}_bragg_lockin_phase.npz"
        np.savez_compressed(npz_path, **save_payload)
        per_file["data_npz"] = str(npz_path)
        results[name] = per_file

    stats_csv = table_dir / "bragg_phase_distribution_stats.csv"
    _write_csv(stats_csv, stats_rows)
    report = {
        "schema_version": 1,
        "tool": "pysidam_agent/bragg_phase.py lockin-from-decision",
        "approval": {
            "decision_path": str(decision_path),
            "decision": decision.get("decision"),
            "approval_source": decision.get("approval_source"),
        },
        "parameters": {
            "channel": channel,
            "direction": direction,
            "sigma_px": sigma_px,
            "window": window,
            "threshold_sweep": thresholds,
            "primary_threshold_fraction_of_amp_max": primary_threshold,
        },
        "outputs": {"stats_csv": str(stats_csv), "data_dir": str(data_dir)},
        "results": results,
    }
    write_json(out_root / "report.json", report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reusable Bragg/q-selection and lock-in phase bridge.")
    sub = parser.add_subparsers(dest="command", required=True)

    policy = sub.add_parser("policy", help="Resolve whether q selection should ask the user first.")
    policy.add_argument("--user-q", type=_parse_pair, help="User-specified qx,qy in cycles/nm.")
    policy.add_argument("--roi", nargs=4, metavar=("QX_MIN", "QX_MAX", "QY_MIN", "QY_MAX"))
    policy.add_argument("--allow-agent-search", action="store_true")
    policy.set_defaults(func=command_policy)

    inspect = sub.add_parser("inspect-roi", help="Find plus/minus FFT peaks inside a user-specified ROI.")
    inspect.add_argument("paths", nargs="+", help="Input .sxm files.")
    inspect.add_argument("--roi", nargs=4, metavar=("QX_MIN", "QX_MAX", "QY_MIN", "QY_MAX"), required=True)
    inspect.add_argument("--channel", default="Z")
    inspect.add_argument("--direction", default="forward")
    inspect.add_argument("--window", default="hann")
    inspect.add_argument("--default-scan-size-nm", type=float, default=100.0)
    inspect.add_argument("--output-json", default="")
    inspect.add_argument("--output-csv", default="")
    inspect.set_defaults(func=command_inspect_roi)

    lockin = sub.add_parser("lockin-from-decision", help="Run approved lock-in phase extraction from a decision JSON.")
    lockin.add_argument("--decision", required=True)
    lockin.add_argument("--raw-root", required=True)
    lockin.add_argument("--output-dir", required=True)
    lockin.add_argument("--channel", default="")
    lockin.add_argument("--direction", default="")
    lockin.add_argument("--sigma-px", type=float)
    lockin.add_argument("--window", default="")
    lockin.add_argument("--default-scan-size-nm", type=float, default=100.0)
    lockin.set_defaults(func=command_lockin_from_decision)
    return parser


def main() -> int:
    ensure_runtime(reexec=True)
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
