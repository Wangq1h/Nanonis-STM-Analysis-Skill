from __future__ import annotations

from typing import Any

import numpy as np
from scipy.stats import gaussian_kde


HISTOGRAM_SOURCE_MAPPING = (
    "usefultools_histogram.HistogramWindow._apply_background_mode, "
    "_sample_fit_values, _build_trace_fit, _max_hist_bin_count, update_histograms"
)


def histogram_algorithm(engine: str = "analystm.histogram.compute_histogram") -> dict[str, str]:
    return {
        "name": "AnalySTM histogram backend",
        "engine": engine,
        "pysidam_source_mapping": HISTOGRAM_SOURCE_MAPPING,
    }


def _positive_floor(value: float = 0.0) -> float:
    try:
        val = abs(float(value)) * 1e-15
    except Exception:
        val = 0.0
    return max(np.nextafter(0.0, 1.0), val)


def apply_histogram_background(data: Any, mode: str = "Raw") -> np.ndarray:
    out = np.asarray(data, dtype=float).copy()
    if out.ndim != 2:
        raise ValueError("histogram background correction expects a 2D map")
    mode = str(mode or "Raw").strip()
    ny, nx = out.shape

    if mode == "Sub Global Mean":
        out -= np.nanmean(out)
    elif mode == "Sub Line Mean (0-order)":
        out -= np.nanmean(out, axis=1, keepdims=True)
    elif mode == "Sub Line Mean (Row+Col)":
        out -= np.nanmean(out, axis=1, keepdims=True)
        out -= np.nanmean(out, axis=0, keepdims=True)
    elif mode == "Sub Line Linear (1-order)":
        x = np.arange(nx, dtype=float)
        for i in range(ny):
            row = np.asarray(out[i], dtype=float)
            finite = np.isfinite(row)
            if np.count_nonzero(finite) < 2:
                continue
            fit = np.polyfit(x[finite], row[finite], 1)
            out[i] = row - np.polyval(fit, x)
    elif mode == "Sub Plane (Global)":
        yy, xx = np.indices(out.shape, dtype=float)
        finite = np.isfinite(out)
        if np.count_nonzero(finite) >= 3:
            a = np.c_[xx[finite], yy[finite], np.ones(np.count_nonzero(finite))]
            c, _, _, _ = np.linalg.lstsq(a, out[finite], rcond=None)
            out = out - (c[0] * xx + c[1] * yy + c[2])
    elif mode == "Sub Parabolic (Global)":
        yy, xx = np.indices(out.shape, dtype=float)
        finite = np.isfinite(out)
        if np.count_nonzero(finite) >= 6:
            xf = xx[finite]
            yf = yy[finite]
            a = np.c_[xf**2, yf**2, xf * yf, xf, yf, np.ones_like(xf)]
            c, _, _, _ = np.linalg.lstsq(a, out[finite], rcond=None)
            out = out - (c[0] * xx**2 + c[1] * yy**2 + c[2] * xx * yy + c[3] * xx + c[4] * yy + c[5])
    elif mode == "Differentiate (X-deriv)":
        out = np.gradient(out, axis=1)
    return np.asarray(out, dtype=float)


def sample_histogram_fit_values(values: Any, max_samples: int = 20000) -> np.ndarray:
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    if vals.size <= int(max_samples):
        return np.ascontiguousarray(vals, dtype=float)
    step = max(1, int(np.ceil(vals.size / float(max_samples))))
    return np.ascontiguousarray(vals[::step], dtype=float)


def build_histogram_trace_fit(
    values: Any,
    edges: Any,
    centers: Any,
    counts: Any,
    *,
    bandwidth_scale: float = 1.0,
    max_samples: int = 20000,
) -> tuple[np.ndarray, np.ndarray]:
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    curve_x = np.asarray(centers, dtype=float)
    curve_y = np.asarray(counts, dtype=float)
    if vals.size < 8 or curve_x.size < 5 or np.unique(vals).size < 5:
        return curve_x, np.clip(curve_y, 0.0, None)

    edge_arr = np.asarray(edges, dtype=float)
    dense_n = min(max(curve_x.size * 12, 400), 5000)
    fit_x = np.linspace(float(edge_arr[0]), float(edge_arr[-1]), int(dense_n))
    bin_width = float(np.median(np.diff(edge_arr)))
    fit_vals = sample_histogram_fit_values(vals, max_samples=max_samples)
    try:
        bw_scale = float(bandwidth_scale)
        kde = gaussian_kde(fit_vals, bw_method=lambda kde_obj: kde_obj.scotts_factor() * bw_scale)
        fit_y = kde(fit_x) * float(vals.size) * max(bin_width, np.nextafter(0.0, 1.0))
    except Exception:
        fit_y = np.interp(fit_x, curve_x, curve_y)
    return np.asarray(fit_x, dtype=float), np.clip(np.asarray(fit_y, dtype=float), 0.0, None)


def histogram_max_bin_count(values: Any, x_min: float, x_max: float, bin_size: float) -> float:
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return 0.0
    inside = vals[(vals >= float(x_min)) & (vals <= float(x_max))]
    if inside.size == 0:
        return 0.0
    span = max(float(x_max) - float(x_min), np.nextafter(0.0, 1.0))
    width = max(float(bin_size), np.nextafter(0.0, 1.0))
    max_idx = max(0, int(np.ceil(span / width)) - 1)
    idx = np.floor((inside - float(x_min)) / width).astype(np.int64)
    idx = np.clip(idx, 0, max_idx)
    if idx.size == 0:
        return 0.0
    _, counts = np.unique(idx, return_counts=True)
    return float(np.max(counts)) if counts.size else 0.0


def histogram_stats(values: Any) -> dict[str, float | int]:
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return {"count": 0}
    return {
        "count": int(vals.size),
        "mean": float(np.mean(vals)),
        "std": float(np.std(vals)),
        "median": float(np.median(vals)),
        "min": float(np.min(vals)),
        "max": float(np.max(vals)),
        "p05": float(np.percentile(vals, 5)),
        "p95": float(np.percentile(vals, 95)),
    }


def compute_histogram(
    data: Any,
    *,
    vmin: float | None = None,
    vmax: float | None = None,
    bin_size: float | None = None,
    background_mode: str = "Raw",
    fit_bandwidth_scale: float = 1.0,
    fit_max_samples: int = 20000,
) -> dict[str, Any]:
    arr = np.asarray(data, dtype=float)
    if arr.ndim != 2:
        raise ValueError("compute_histogram expects a 2D map")
    processed = apply_histogram_background(arr, background_mode)
    vals = np.asarray(processed, dtype=float).ravel()
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        raise ValueError("No finite data available.")

    x_min = float(np.min(vals)) if vmin is None else float(vmin)
    x_max = float(np.max(vals)) if vmax is None else float(vmax)
    if not np.isfinite(x_min) or not np.isfinite(x_max):
        raise ValueError("Invalid histogram range.")
    if x_max <= x_min:
        x_max = x_min + 1e-9

    span = float(x_max - x_min)
    bin_floor = _positive_floor(span)
    width = max(float(bin_size) if bin_size is not None else span / 120.0, bin_floor)
    bins = max(5, int(np.ceil(span / width)))
    hist, edges = np.histogram(vals, bins=bins, range=(x_min, x_max))
    centers = 0.5 * (edges[:-1] + edges[1:])
    fit_vals = vals[(vals >= edges[0]) & (vals <= edges[-1])]
    fit_x, fit_y = build_histogram_trace_fit(
        fit_vals,
        edges,
        centers,
        hist,
        bandwidth_scale=fit_bandwidth_scale,
        max_samples=fit_max_samples,
    )

    return {
        "processed": np.asarray(processed, dtype=float),
        "edges": np.asarray(edges, dtype=float),
        "centers": np.asarray(centers, dtype=float),
        "counts": np.asarray(hist, dtype=float),
        "fit_x": np.asarray(fit_x, dtype=float),
        "fit_y": np.asarray(fit_y, dtype=float),
        "stats": histogram_stats(vals),
        "algorithm": histogram_algorithm(),
        "parameters": {
            "background_mode": str(background_mode),
            "vmin": float(x_min),
            "vmax": float(x_max),
            "bin_size": float(width),
            "bins": int(bins),
            "fit_bandwidth_scale": float(fit_bandwidth_scale),
            "fit_max_samples": int(fit_max_samples),
        },
    }
