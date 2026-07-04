from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

import numpy as np


LOCKIN_ENGINE = "pysidam.qpi_analysis.qpi_phase_analysis.lockin_phase_extraction"


def q_cycles_to_pysidam_px_yx(
    q_xy_cycles_per_nm: tuple[float, float] | list[float],
    shape_yx: tuple[int, int],
    scan_size_nm_xy: tuple[float, float],
) -> list[float]:
    """Convert q=(qx,qy) cycles/nm to PySIDAM absolute FFT pixel coordinates."""
    ny, nx = map(int, shape_yx)
    sx_nm, sy_nm = map(float, scan_size_nm_xy)
    qx, qy = map(float, q_xy_cycles_per_nm)
    if ny <= 0 or nx <= 0:
        raise ValueError("shape_yx must contain positive dimensions")
    if sx_nm <= 0 or sy_nm <= 0:
        raise ValueError("scan_size_nm_xy must contain positive scan sizes")
    center_y = (ny - 1) / 2.0
    center_x = (nx - 1) / 2.0
    return [float(center_y + qy * sy_nm), float(center_x + qx * sx_nm)]


def run_pysidam_lockin(
    image_yx: Any,
    q_vectors_xy_cycles_per_nm: Mapping[str, tuple[float, float] | list[float]],
    scan_size_nm_xy: tuple[float, float],
    sigma_px: float = 3.0,
    window: str = "hann",
    threshold_fractions: Iterable[float] = (0.1, 0.2, 0.3),
    engine: Callable[..., tuple[Any, Any, Any]] | None = None,
    unwrap_func: Callable[[Any], Any] | None = None,
) -> dict[str, Any]:
    """Run PySIDAM 2D lock-in extraction and return a standard map package."""
    image = np.asarray(image_yx, dtype=float)
    if image.ndim != 2:
        raise ValueError("image_yx must be a 2D map")
    if not q_vectors_xy_cycles_per_nm:
        raise ValueError("at least one q vector is required")

    if engine is None:
        from pysidam.qpi_analysis.qpi_phase_analysis import lockin_phase_extraction

        engine = lockin_phase_extraction
    if unwrap_func is None:
        from pysidam.qpi_analysis.qpi_phase_analysis import _unwrap_phase_2d

        unwrap_func = _unwrap_phase_2d

    thresholds = [float(x) for x in threshold_fractions]
    maps: dict[str, Any] = {}
    q_results: dict[str, Any] = {}
    stats_rows: list[dict[str, Any]] = []

    for label, q_xy in q_vectors_xy_cycles_per_nm.items():
        safe = _safe_label(str(label))
        q_xy_pair = [float(q_xy[0]), float(q_xy[1])]
        q_abs_px_yx = q_cycles_to_pysidam_px_yx(q_xy_pair, image.shape, scan_size_nm_xy)
        amp, phase_wrapped, complex_field = engine(
            image,
            q_abs_px_yx,
            sigma_px=float(sigma_px),
            window=window,
            unwrap_phase=False,
        )
        amp_arr = np.asarray(amp, dtype=float)
        phase_wrapped_arr = wrap_pi(np.asarray(phase_wrapped, dtype=float))
        phase_unwrapped_arr = np.asarray(unwrap_func(phase_wrapped_arr), dtype=float)
        complex_arr = np.asarray(complex_field)

        maps[f"{safe}_amp"] = amp_arr
        maps[f"{safe}_phase_wrapped"] = phase_wrapped_arr
        maps[f"{safe}_phase_unwrapped"] = phase_unwrapped_arr
        maps[f"{safe}_complex"] = complex_arr

        threshold_keys = []
        for threshold in thresholds:
            suffix = _threshold_suffix(threshold)
            mask = amplitude_mask(amp_arr, threshold)
            key = f"{safe}_mask_amp_{suffix}"
            maps[key] = mask
            threshold_keys.append(key)
            stats_rows.append(
                {
                    "q_label": safe,
                    "threshold_fraction_of_amp_max": threshold,
                    "pixels_in_mask": int(np.count_nonzero(mask)),
                    "mask_fraction": float(np.count_nonzero(mask) / mask.size),
                    "amp_max": _finite_max(amp_arr),
                    **circular_stats(phase_wrapped_arr[mask]),
                }
            )

        q_results[safe] = {
            "q_cycles_per_nm_xy": q_xy_pair,
            "q_abs_px_yx_for_pysidam_lockin": q_abs_px_yx,
            "sigma_px": float(sigma_px),
            "window": window,
            "threshold_mask_keys": threshold_keys,
        }

    return {
        "metadata": {
            "schema_version": 1,
            "lockin_engine": LOCKIN_ENGINE,
            "shape_yx": [int(image.shape[0]), int(image.shape[1])],
            "scan_size_nm_xy": [float(scan_size_nm_xy[0]), float(scan_size_nm_xy[1])],
            "sigma_px": float(sigma_px),
            "window": window,
            "threshold_fractions": thresholds,
            "q_results": q_results,
        },
        "maps": maps,
        "stats_rows": stats_rows,
    }


def wrap_pi(phi: Any) -> np.ndarray:
    return (np.asarray(phi, dtype=float) + np.pi) % (2.0 * np.pi) - np.pi


def amplitude_mask(amp: Any, threshold_fraction: float) -> np.ndarray:
    arr = np.asarray(amp, dtype=float)
    finite = np.isfinite(arr)
    if not finite.any():
        return np.zeros(arr.shape, dtype=bool)
    max_val = float(np.nanmax(arr[finite]))
    if not np.isfinite(max_val) or max_val <= 0:
        return np.zeros(arr.shape, dtype=bool)
    return finite & (arr >= float(threshold_fraction) * max_val)


def circular_stats(values: Any) -> dict[str, Any]:
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return {"n": 0, "mean_angle_rad": None, "mean_angle_deg": None, "resultant_length": None}
    vec = np.exp(1j * vals)
    mean_vec = np.mean(vec)
    mean = float(np.angle(mean_vec))
    return {
        "n": int(vals.size),
        "mean_angle_rad": mean,
        "mean_angle_deg": float(np.degrees(mean)),
        "resultant_length": float(np.abs(mean_vec)),
    }


def _finite_max(values: Any) -> float | None:
    arr = np.asarray(values, dtype=float)
    finite = arr[np.isfinite(arr)]
    return float(np.max(finite)) if finite.size else None


def _threshold_suffix(value: float) -> str:
    return str(float(value)).rstrip("0").rstrip(".").replace(".", "p")


def _safe_label(text: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in text).strip("_") or "q"
