#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys
from typing import Any


try:
    from .common import best_channel_name, backward_partner, ensure_runtime, write_json
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from pysidam_agent.common import best_channel_name, backward_partner, ensure_runtime, write_json


DEFAULT_BIAS_CHANNEL = "Bias calc (V)"
DEFAULT_SIGNAL_CHANNEL = "LI Demod 1 X"
DEFAULT_MODEL = "Two Band s-wave"
DEFAULT_FIT_STRATEGY = "multistart_weighted"
PYSIDAM_FIT_ENGINE = (
    "pysidam.useful_tools.usefultools_deconvolution_point."
    "fit_selected_gap_dos_model_guarded"
)


def import_pysidam_fitter() -> tuple[Any | None, dict[str, Any]]:
    try:
        from pysidam.useful_tools.usefultools_deconvolution_point import (
            fit_selected_gap_dos_model_guarded,
        )
    except Exception as exc:
        return None, {
            "ok": False,
            "status": "pysidam_fitter_import_failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "fit_engine": PYSIDAM_FIT_ENGINE,
            "required_action": "Install or enable PySIDAM's UI-wrapped fitting dependencies in the isolated skill runtime.",
            "safe_bootstrap": "python3 scripts/bootstrap_runtime.py --groups headless,ui",
            "policy": "Do not write a new optimizer as fallback.",
        }
    return fit_selected_gap_dos_model_guarded, {
        "ok": True,
        "status": "ready",
        "fit_engine": PYSIDAM_FIT_ENGINE,
        "policy": "Do not write a new optimizer; this bridge delegates fitting to PySIDAM.",
    }


def load_signals(path: Path) -> tuple[dict[str, Any], str]:
    suffix = path.suffix.lower()
    if suffix == ".dat":
        from pysidam.core.nanonis_io import read_nanonis_file

        nf = read_nanonis_file(path)
        return getattr(nf.obj, "signals", {}), "pysidam.core.nanonis_io.read_nanonis_file"
    if suffix in {".txt", ".csv", ".tsv", ".ibw"}:
        from pysidam.core.import_io import read_imported_file

        imported = read_imported_file(path)
        return getattr(imported.obj, "signals", {}), "pysidam.core.import_io.read_imported_file"
    raise ValueError(f"Unsupported gap-fit input suffix: {suffix}")


def read_spectrum(
    path: Path,
    bias_channel: str,
    signal_channel: str,
    average_bwd: bool,
) -> dict[str, Any]:
    import numpy as np

    signals, reader = load_signals(path)
    channels = [str(name) for name in signals.keys()]
    x_name = best_channel_name(channels, bias_channel, ["bias", "sweep"])
    y_name = best_channel_name(channels, signal_channel, ["li demod 1 x", "didv", "current"])
    if not x_name or not y_name:
        raise ValueError("Could not select bias and signal channels.")

    bias = np.asarray(signals[x_name], dtype=float)
    if "(v)" in x_name.lower() and np.nanmax(np.abs(bias)) < 50:
        bias = bias * 1000.0

    y = np.asarray(signals[y_name], dtype=float)
    y_unit = "raw"
    if "(a)" in y_name.lower() and np.nanmax(np.abs(y)) < 1e-6:
        y = y * 1e12
        y_unit = "pA"

    bwd_name = ""
    if average_bwd:
        bwd_name = backward_partner(channels, y_name)
        if bwd_name:
            y_bwd = np.asarray(signals[bwd_name], dtype=float)
            if y_unit == "pA":
                y_bwd = y_bwd * 1e12
            y = np.nanmean(np.vstack([y, y_bwd]), axis=0)

    finite = np.isfinite(bias) & np.isfinite(y)
    bias = bias[finite]
    y = y[finite]
    order = np.argsort(bias)
    return {
        "path": str(path),
        "reader": reader,
        "bias_mV": np.asarray(bias[order], dtype=float),
        "signal": np.asarray(y[order], dtype=float),
        "signal_unit": y_unit,
        "bias_channel": x_name,
        "signal_channel": y_name,
        "backward_channel": bwd_name,
        "channels": channels,
    }


def parse_initial_params(raw: str) -> list[float] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    return [float(part.strip()) for part in text.replace(";", ",").split(",") if part.strip()]


def fit_one(fitter: Any, spectrum: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    fit_kwargs: dict[str, Any] = {
        "model_name": args.model,
        "fit_strategy": args.fit_strategy,
        "fit_max_starts": args.fit_max_starts,
        "curve_fit_maxfev": args.maxfev,
        "time_budget_s": args.time_budget_s,
    }
    if args.fit_abs_max is not None:
        fit_kwargs["fit_abs_max"] = args.fit_abs_max
        fit_kwargs["fit_abs_source_override"] = "manual"
    initial_params = parse_initial_params(args.initial_params)
    if initial_params is not None:
        fit_kwargs["initial_params"] = initial_params

    result = fitter(
        spectrum["bias_mV"],
        spectrum["signal"],
        **fit_kwargs,
    )
    result = dict(result)
    result["input"] = {
        "path": spectrum["path"],
        "reader": spectrum["reader"],
        "bias_channel": spectrum["bias_channel"],
        "signal_channel": spectrum["signal_channel"],
        "backward_channel": spectrum["backward_channel"],
        "signal_unit": spectrum["signal_unit"],
        "point_count": int(len(spectrum["bias_mV"])),
    }
    result["fit_engine"] = PYSIDAM_FIT_ENGINE
    result["fit_policy"] = {
        "delegated_to_pysidam": True,
        "no_local_optimizer": True,
        "initial_params": initial_params,
        "fit_strategy": args.fit_strategy,
        "fit_max_starts": args.fit_max_starts,
    }
    return result


def array_or_empty(result: dict[str, Any], key: str):
    import numpy as np

    value = result.get(key)
    if value is None:
        return np.asarray([], dtype=float)
    return np.asarray(value, dtype=float)


def save_curve_csv(result: dict[str, Any], path: Path) -> None:
    bias = array_or_empty(result, "bias_display")
    data = array_or_empty(result, "rho_data_display")
    model = array_or_empty(result, "rho_model_display")
    full = array_or_empty(result, "rho_model_display_full")
    path.parent.mkdir(parents=True, exist_ok=True)
    n = max(len(bias), len(data), len(model), len(full))
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["bias_mV", "data", "pysidam_model", "pysidam_model_full"])
        for idx in range(n):
            writer.writerow([
                bias[idx] if idx < len(bias) else "",
                data[idx] if idx < len(data) else "",
                model[idx] if idx < len(model) else "",
                full[idx] if idx < len(full) else "",
            ])


def save_plot(result: dict[str, Any], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    bias = array_or_empty(result, "bias_display")
    data = array_or_empty(result, "rho_data_display")
    model = array_or_empty(result, "rho_model_display")
    residual = data - model if len(data) == len(model) else []

    fig, axes = plt.subplots(2, 1, figsize=(7.2, 5.8), sharex=True, constrained_layout=True)
    axes[0].plot(bias, data, color="0.15", lw=1.2, label="data")
    axes[0].plot(bias, model, color="#c43c35", lw=1.8, label="PySIDAM fit")
    axes[0].set_ylabel("signal")
    axes[0].legend(frameon=False)
    axes[0].grid(True, alpha=0.25)

    axes[1].plot(bias, residual, color="0.35", lw=1.0)
    axes[1].axhline(0, color="0.65", lw=0.8)
    axes[1].set_xlabel("Bias (mV)")
    axes[1].set_ylabel("residual")
    axes[1].grid(True, alpha=0.25)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def strip_arrays(result: dict[str, Any]) -> dict[str, Any]:
    array_keys = {
        "bias_display",
        "rho_data_display",
        "rho_model_display",
        "rho_model_display_full",
        "bias_fit",
        "rho_data_fit",
        "rho_model_fit",
    }
    return {key: value for key, value in result.items() if key not in array_keys}


def main() -> int:
    parser = argparse.ArgumentParser(description="Fit spectra through PySIDAM's existing gap-model fitter.")
    parser.add_argument("inputs", nargs="*", type=Path, help="Input .dat, text, csv, tsv, or 1D .ibw spectra.")
    parser.add_argument("--probe-fitter", action="store_true", help="Only report whether the PySIDAM fitter can be imported.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/gap_fit"))
    parser.add_argument("--summary-json", type=Path, default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--fit-strategy", default=DEFAULT_FIT_STRATEGY)
    parser.add_argument("--fit-max-starts", type=int, default=16)
    parser.add_argument("--maxfev", type=int, default=20000)
    parser.add_argument("--time-budget-s", type=float, default=30.0)
    parser.add_argument("--fit-abs-max", type=float, default=None)
    parser.add_argument("--initial-params", default="", help="Comma-separated PySIDAM model initial parameters.")
    parser.add_argument("--bias-channel", default=DEFAULT_BIAS_CHANNEL)
    parser.add_argument("--channel", default=DEFAULT_SIGNAL_CHANNEL)
    parser.add_argument("--average-bwd", action="store_true")
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()

    runtime = ensure_runtime(reexec=True)
    fitter, fitter_status = import_pysidam_fitter()
    if args.probe_fitter:
        write_json(args.summary_json or Path("fit_gap_probe.json"), {"runtime": runtime, "fitter": fitter_status})
        return 0 if fitter_status["ok"] else 3
    if fitter is None:
        payload = {
            "tool": "pysidam_agent/fit_gap.py",
            "runtime": runtime,
            "fitter": fitter_status,
            "files": [],
            "errors": [],
        }
        write_json(args.summary_json or args.output_dir / "fit_summary.json", payload)
        return 3
    if not args.inputs:
        raise SystemExit("No input spectra provided.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    files = []
    errors = []
    for path in args.inputs:
        try:
            spectrum = read_spectrum(path.expanduser(), args.bias_channel, args.channel, args.average_bwd)
            result = fit_one(fitter, spectrum, args)
            stem = path.stem
            curve_path = args.output_dir / f"{stem}_pysidam_fit_curve.csv"
            save_curve_csv(result, curve_path)
            plot_path = None
            if not args.no_plots:
                plot_path = args.output_dir / f"{stem}_pysidam_fit.png"
                save_plot(result, plot_path)
            clean = strip_arrays(result)
            clean["outputs"] = {
                "curve_csv": str(curve_path),
                "plot_png": str(plot_path) if plot_path is not None else "",
            }
            files.append(clean)
        except Exception as exc:
            errors.append({
                "path": str(path),
                "error_type": type(exc).__name__,
                "error": str(exc),
            })

    payload = {
        "tool": "pysidam_agent/fit_gap.py",
        "runtime": runtime,
        "fitter": fitter_status,
        "files": files,
        "errors": errors,
    }
    write_json(args.summary_json or args.output_dir / "fit_summary.json", payload)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
