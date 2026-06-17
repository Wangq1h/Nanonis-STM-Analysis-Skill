#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any


try:
    from .common import best_channel_name, backward_partner, ensure_runtime, finite_summary, write_json
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from pysidam_agent.common import best_channel_name, backward_partner, ensure_runtime, finite_summary, write_json


def load_spectrum(path: Path) -> tuple[dict[str, Any], str]:
    suffix = path.suffix.lower()
    if suffix in {".3ds", ".sxm"}:
        raise ValueError("plot_spectrum.py expects 1D spectra; use a map-specific adapter for grids or scans.")
    if suffix == ".dat":
        from pysidam.core.nanonis_io import read_nanonis_file

        nf = read_nanonis_file(path)
        return getattr(nf.obj, "signals", {}), "pysidam.core.nanonis_io.read_nanonis_file"
    if suffix in {".txt", ".csv", ".tsv", ".ibw"}:
        from pysidam.core.import_io import read_imported_file

        imported = read_imported_file(path)
        return getattr(imported.obj, "signals", {}), "pysidam.core.import_io.read_imported_file"
    raise ValueError(f"Unsupported spectrum suffix: {suffix}")


def scale_bias(x, name: str):
    import numpy as np

    arr = np.asarray(x, dtype=float)
    label = name
    if "(v)" in name.lower() and np.nanmax(np.abs(arr)) < 50:
        return arr * 1000.0, "Bias (mV)"
    return arr, label


def scale_signal(y, name: str, unit: str):
    import numpy as np

    arr = np.asarray(y, dtype=float)
    requested = unit.strip().lower()
    if requested == "pa":
        return arr * 1e12, "dI/dV (pA)"
    if requested == "na":
        return arr * 1e9, "Signal (nA)"
    return arr, name


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot 1D spectra with the PySIDAM-backed agent bridge.")
    parser.add_argument("paths", nargs="+", help="Input .dat, text, csv, tsv, or 1D .ibw spectra.")
    parser.add_argument("--bias-channel", default="Bias calc (V)", help="Bias or x-axis channel.")
    parser.add_argument("--channel", default="LI Demod 1 X", help="Signal channel.")
    parser.add_argument("--average-bwd", action="store_true", help="Average a matching backward trace when available.")
    parser.add_argument("--unit", default="pA", choices=["raw", "pA", "nA"], help="Display unit for y-axis.")
    parser.add_argument("--output", required=True, help="PNG output path.")
    parser.add_argument("--summary-json", default="", help="Optional JSON summary output.")
    args = parser.parse_args()

    runtime = ensure_runtime(reexec=True)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=(7.2, 4.4), constrained_layout=True)
    summary: dict[str, Any] = {
        "tool": "pysidam_agent/plot_spectrum.py",
        "runtime": runtime,
        "files": [],
        "errors": [],
    }

    for raw_path in args.paths:
        path = Path(raw_path).expanduser()
        try:
            signals, reader = load_spectrum(path)
            channels = [str(name) for name in signals.keys()]
            x_name = best_channel_name(channels, args.bias_channel, ["bias", "sweep"])
            y_name = best_channel_name(channels, args.channel, ["li demod 1 x", "didv", "current"])
            if not x_name or not y_name:
                raise ValueError("Could not select bias and signal channels.")
            x, x_label = scale_bias(signals[x_name], x_name)
            y_raw = np.asarray(signals[y_name], dtype=float)
            bwd_name = ""
            if args.average_bwd:
                bwd_name = backward_partner(channels, y_name)
                if bwd_name:
                    y_raw = np.nanmean(np.vstack([y_raw, np.asarray(signals[bwd_name], dtype=float)]), axis=0)
            y, y_label = scale_signal(y_raw, y_name, args.unit)
            n = min(len(x), len(y))
            if n <= 1:
                raise ValueError("Selected channels do not contain enough points.")
            ax.plot(x[:n], y[:n], lw=1.4, label=path.stem)
            summary["files"].append({
                "path": str(path),
                "reader": reader,
                "bias_channel": x_name,
                "signal_channel": y_name,
                "backward_channel": bwd_name,
                "point_count": int(n),
                "bias_summary": finite_summary(x[:n]),
                "signal_summary": finite_summary(y[:n]),
            })
            ax.set_xlabel(x_label)
            ax.set_ylabel(y_label)
        except Exception as exc:
            summary["errors"].append({
                "path": str(path),
                "error_type": type(exc).__name__,
                "error": str(exc),
            })

    if not summary["files"]:
        if args.summary_json:
            write_json(Path(args.summary_json), summary)
        return 1

    ax.axvline(0, color="0.72", lw=0.8)
    ax.grid(True, alpha=0.25, lw=0.6)
    ax.legend(frameon=False, fontsize=9)
    ax.set_title("Spectroscopy overview")
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180)
    plt.close(fig)
    summary["output"] = str(output)
    if args.summary_json:
        write_json(Path(args.summary_json), summary)
    return 0 if not summary["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
