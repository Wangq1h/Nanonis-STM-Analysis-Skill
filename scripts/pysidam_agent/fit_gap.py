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
PROFILE_STRICT = "strict-pysidam-compatible"
PROFILE_GAP_PRIORITY = "two_band_splusminus_gap_priority"
SKILL_ROOT = Path(__file__).resolve().parents[2]
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))
PYSIDAM_FIT_ENGINE = "pysidam_agent_core.gap_fitting.fit_gap_model_guarded"


def import_core_fitter() -> tuple[Any | None, dict[str, Any]]:
    try:
        from pysidam_agent_core.gap_fitting import fit_gap_model_guarded
    except Exception as exc:
        return None, {
            "ok": False,
            "status": "pysidam_agent_core_import_failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "fit_engine": PYSIDAM_FIT_ENGINE,
            "required_action": "Install or expose PySIDAM core modules in the isolated skill runtime.",
            "safe_bootstrap": "python3 scripts/bootstrap_runtime.py --groups headless,nanonis,ibw",
            "policy": "Do not write a task-local optimizer as fallback.",
        }
    return fit_gap_model_guarded, {
        "ok": True,
        "status": "ready",
        "fit_engine": PYSIDAM_FIT_ENGINE,
        "policy": "Do not write a task-local optimizer; this bridge delegates fitting to pysidam_agent_core.",
    }


def load_signals(path: Path) -> tuple[dict[str, Any], str]:
    from pysidam_agent_core.io import load_signals as core_load_signals

    return core_load_signals(path)


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


def parse_float_list(raw: str) -> list[float] | None:
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
        "delegated_to_pysidam_agent_core": True,
        "no_task_local_optimizer": True,
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


def save_gap_priority_curve_csv(result: dict[str, Any], path: Path) -> None:
    arrays = result.get("arrays", {})
    bias = array_or_empty(arrays, "bias_display")
    data = array_or_empty(arrays, "signal_display")
    model = array_or_empty(arrays, "model_display")
    weights = array_or_empty(arrays, "fit_weight")
    fit_mask = array_or_empty(arrays, "fit_mask")
    path.parent.mkdir(parents=True, exist_ok=True)
    n = max(len(bias), len(data), len(model), len(weights), len(fit_mask))
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["bias_mV", "signal", "model_fit_window_only", "fit_weight", "fit_mask"])
        for idx in range(n):
            writer.writerow([
                bias[idx] if idx < len(bias) else "",
                data[idx] if idx < len(data) else "",
                model[idx] if idx < len(model) else "",
                weights[idx] if idx < len(weights) else "",
                fit_mask[idx] if idx < len(fit_mask) else "",
            ])


def save_gap_priority_plot(result: dict[str, Any], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    arrays = result.get("arrays", {})
    bias = array_or_empty(arrays, "bias_display")
    data = array_or_empty(arrays, "signal_display")
    model = array_or_empty(arrays, "model_display")
    weights = array_or_empty(arrays, "fit_weight")
    residual = data - model if len(data) == len(model) else np.asarray([], dtype=float)
    fit_abs = float(result.get("fit_abs_mV", np.nan))
    mode = str(result.get("mode", ""))

    fig, axes = plt.subplots(3, 1, figsize=(7.2, 7.6), sharex=True, constrained_layout=True, gridspec_kw={"height_ratios": [3.2, 1.3, 1.0]})
    axes[0].plot(bias, data, color="0.15", lw=1.2, label="data")
    axes[0].plot(bias, model, color="#c43c35", lw=1.8, label="gap-priority fit")
    if fit_abs == fit_abs and fit_abs > 0:
        axes[0].axvspan(fit_abs, float(np.nanmax(bias)), color="0.90", alpha=0.65, lw=0)
        axes[0].axvspan(float(np.nanmin(bias)), -fit_abs, color="0.90", alpha=0.65, lw=0)
    axes[0].axvline(0, color="0.55", lw=0.8)
    bias_offset = result.get("parameters", {}).get("bias_offset_mV")
    if bias_offset is not None:
        axes[0].axvline(float(bias_offset), color="#3366aa", lw=0.8, ls="--")
    axes[0].set_ylabel("signal")
    axes[0].set_title(f"{Path(str(result.get('source_file', 'spectrum'))).name} {mode}")
    axes[0].legend(frameon=False)
    axes[0].grid(True, alpha=0.25)

    axes[1].plot(bias, residual, color="0.35", lw=1.0)
    axes[1].axhline(0, color="0.65", lw=0.8)
    axes[1].set_ylabel("residual")
    axes[1].grid(True, alpha=0.25)

    axes[2].plot(bias, weights, color="#3366aa", lw=1.0)
    axes[2].set_ylabel("weight")
    axes[2].set_xlabel("Bias (mV)")
    axes[2].grid(True, alpha=0.25)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_gap_priority_overview(results: list[dict[str, Any]], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    if not results:
        return
    fig, axes = plt.subplots(len(results), 1, figsize=(7.6, max(3.0, 2.2 * len(results))), sharex=True, constrained_layout=True)
    if len(results) == 1:
        axes = [axes]
    for ax, result in zip(axes, results):
        arrays = result.get("arrays", {})
        bias = array_or_empty(arrays, "bias_display")
        data = array_or_empty(arrays, "signal_display")
        model = array_or_empty(arrays, "model_display")
        ax.plot(bias, data, color="0.18", lw=1.0)
        ax.plot(bias, model, color="#c43c35", lw=1.6)
        fit_abs = float(result.get("fit_abs_mV", np.nan))
        if fit_abs == fit_abs and fit_abs > 0 and len(bias):
            ax.axvspan(fit_abs, float(np.nanmax(bias)), color="0.92", alpha=0.55, lw=0)
            ax.axvspan(float(np.nanmin(bias)), -fit_abs, color="0.92", alpha=0.55, lw=0)
        metrics = result.get("metrics", {})
        title = f"{Path(str(result.get('source_file', 'spectrum'))).name} {result.get('mode', '')} center={metrics.get('center_platform_rmse_pA', float('nan')):.4g} peak={metrics.get('coherence_peak_rmse_pA', float('nan')):.4g}"
        ax.set_title(title, fontsize=9)
        ax.set_ylabel("signal")
        ax.grid(True, alpha=0.22)
    axes[-1].set_xlabel("Bias (mV)")
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
        "residual_display",
    }
    return {key: value for key, value in result.items() if key not in array_keys}


def strip_gap_priority_arrays(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "arrays"}


def run_gap_priority_profile(args: argparse.Namespace, runtime: dict[str, Any], fitter_status: dict[str, Any]) -> int:
    from pysidam_agent_core.gap_priority import fit_gap_priority_modes

    args.output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = args.output_dir / "tables"
    figures_dir = args.output_dir / "figures"
    files: list[dict[str, Any]] = []
    full_results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    candidate_windows = parse_float_list(args.candidate_fit_abs_mV)
    for input_idx, path in enumerate(args.inputs):
        try:
            spectrum = read_spectrum(path.expanduser(), args.bias_channel, args.channel, args.average_bwd)
            results = fit_gap_priority_modes(
                spectrum["bias_mV"],
                spectrum["signal"],
                symmetry=args.symmetry,
                auto_fit_window=bool(args.auto_fit_window),
                candidate_fit_abs_mV=candidate_windows,
                random_starts=args.random_starts,
                max_nfev=args.maxfev,
                seed=1701 + input_idx * 100,
            )
            for result in results:
                result = dict(result)
                result["source_file"] = str(path)
                result["input"] = {
                    "path": str(path),
                    "reader": spectrum["reader"],
                    "bias_channel": spectrum["bias_channel"],
                    "signal_channel": spectrum["signal_channel"],
                    "backward_channel": spectrum["backward_channel"],
                    "signal_unit": spectrum["signal_unit"],
                    "point_count": int(len(spectrum["bias_mV"])),
                }
                stem = f"{path.stem}_{result.get('mode', 'fit')}"
                curve_path = tables_dir / f"{stem}_gap_priority_curve.csv"
                plot_path = figures_dir / f"{stem}_gap_priority_fit.png"
                save_gap_priority_curve_csv(result, curve_path)
                if not args.no_plots:
                    save_gap_priority_plot(result, plot_path)
                result["outputs"] = {
                    "curve_csv": str(curve_path),
                    "plot_png": str(plot_path) if not args.no_plots else "",
                }
                full_results.append(result)
                files.append(strip_gap_priority_arrays(result))
        except Exception as exc:
            errors.append({"path": str(path), "error_type": type(exc).__name__, "error": str(exc)})

    overview_path = ""
    if args.save_overview and not args.no_plots and full_results:
        overview = figures_dir / "fit_overlay_overview.png"
        save_gap_priority_overview(full_results, overview)
        overview_path = str(overview)

    payload = {
        "tool": "pysidam_agent/fit_gap.py",
        "profile": PROFILE_GAP_PRIORITY,
        "mode": "gap-priority experimental",
        "runtime": runtime,
        "fitter": fitter_status,
        "fit_policy": {
            "model_contract": "two-band s-wave / s+- DOS magnitude; scalar STS does not determine phase sign",
            "extended_observation_model": ["bias_offset", "linear/quadratic background", "independent gamma per band", "peak/center weights", "candidate fit window scan", "sym/unsym"],
            "auto_fit_window": bool(args.auto_fit_window),
            "symmetry": args.symmetry,
            "random_starts": args.random_starts,
        },
        "outputs": {
            "report_json": str(args.summary_json or args.output_dir / "report.json"),
            "overview_png": overview_path,
        },
        "files": files,
        "errors": errors,
    }
    write_json(args.summary_json or args.output_dir / "report.json", payload)
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Fit spectra through the bundled headless PySIDAM agent core.")
    parser.add_argument("inputs", nargs="*", type=Path, help="Input .dat, text, csv, tsv, or 1D .ibw spectra.")
    parser.add_argument("--probe-fitter", action="store_true", help="Only report whether the headless fit core can be imported.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/gap_fit"))
    parser.add_argument("--summary-json", type=Path, default=None)
    parser.add_argument("--profile", default=PROFILE_STRICT, choices=[PROFILE_STRICT, PROFILE_GAP_PRIORITY])
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--fit-strategy", default=DEFAULT_FIT_STRATEGY)
    parser.add_argument("--fit-max-starts", type=int, default=16)
    parser.add_argument("--maxfev", type=int, default=20000)
    parser.add_argument("--time-budget-s", type=float, default=30.0)
    parser.add_argument("--fit-abs-max", type=float, default=None)
    parser.add_argument("--candidate-fit-abs-mV", default="", help="Comma-separated candidate fit half-windows for gap-priority profile.")
    parser.add_argument("--symmetry", default="none", choices=["none", "sym", "both"], help="Gap-priority profile symmetry mode.")
    parser.add_argument("--auto-fit-window", action="store_true", help="Scan candidate fit windows for gap-priority profile.")
    parser.add_argument("--random-starts", type=int, default=24, help="Random starts per candidate window for gap-priority profile.")
    parser.add_argument("--save-overview", action="store_true", help="Save fit_overlay_overview.png for gap-priority profile.")
    parser.add_argument("--initial-params", default="", help="Comma-separated PySIDAM model initial parameters.")
    parser.add_argument("--bias-channel", default=DEFAULT_BIAS_CHANNEL)
    parser.add_argument("--channel", default=DEFAULT_SIGNAL_CHANNEL)
    parser.add_argument("--average-bwd", action="store_true")
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()

    runtime = ensure_runtime(reexec=True)
    fitter, fitter_status = import_core_fitter()
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

    if args.profile == PROFILE_GAP_PRIORITY:
        return run_gap_priority_profile(args, runtime, fitter_status)

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
