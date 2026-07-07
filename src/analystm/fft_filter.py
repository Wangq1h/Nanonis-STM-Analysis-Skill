from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from .fft_windowing import apply_fft_display_scale, canonical_fft_window_name, fft_window_2d
from .qpi import _signed_scale


FFT_FILTER_SOURCE_MAPPING = (
    "topography_filter.FFTFilterWindow.update_filtered, "
    "qpi_filter.QPIFilterWindow._build_mask_2d, "
    "qpi_filter.QPIFilterWindow._build_realspace_payload_cube"
)


def fft_filter_algorithm(engine: str = "analystm.fft_filter.run_fft_filter") -> dict[str, str]:
    return {"name": "AnalySTM FFT ROI filter backend", "engine": engine, "pysidam_source_mapping": FFT_FILTER_SOURCE_MAPPING}


def _scan_size_pair(scan_size_nm: float | Sequence[float]) -> tuple[float, float]:
    arr = np.asarray(scan_size_nm, dtype=float).ravel()
    if arr.size == 0:
        return 1.0, 1.0
    if arr.size == 1:
        value = float(arr[0])
        return value, value
    return float(arr[0]), float(arr[1])


def fft_filter_k_axes(shape_yx: Sequence[int], scan_size_nm: float | Sequence[float]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    ny, nx = int(shape_yx[0]), int(shape_yx[1])
    sx, sy = _scan_size_pair(scan_size_nm)
    dx = float(sx) / max(nx, 1)
    dy = float(sy) / max(ny, 1)
    if not np.isfinite(dx) or dx <= 0:
        dx = 1.0
    if not np.isfinite(dy) or dy <= 0:
        dy = 1.0
    kx_axis = np.fft.fftshift(np.fft.fftfreq(nx, d=dx)) * (2.0 * np.pi)
    ky_axis = np.fft.fftshift(np.fft.fftfreq(ny, d=dy)) * (2.0 * np.pi)
    kx_grid, ky_grid = np.meshgrid(kx_axis, ky_axis, indexing="xy")
    return np.asarray(kx_axis, dtype=float), np.asarray(ky_axis, dtype=float), kx_grid, ky_grid


def apply_filter_background_2d(data: Any, mode: str = "Raw") -> np.ndarray:
    out = np.asarray(data, dtype=float).copy()
    if out.ndim != 2:
        raise ValueError("background mode expects a 2D map")
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
            coeff = np.polyfit(x, out[i], 1)
            out[i] -= np.polyval(coeff, x)
    elif mode == "Sub Plane (Global)":
        xg, yg = np.meshgrid(np.arange(nx, dtype=float), np.arange(ny, dtype=float))
        a = np.c_[xg.ravel(), yg.ravel(), np.ones(xg.size)]
        coeff, _, _, _ = np.linalg.lstsq(a, out.ravel(), rcond=None)
        out -= coeff[0] * xg + coeff[1] * yg + coeff[2]
    elif mode == "Sub Parabolic (Global)":
        xg, yg = np.meshgrid(np.arange(nx, dtype=float), np.arange(ny, dtype=float))
        xf = xg.ravel()
        yf = yg.ravel()
        a = np.c_[xf**2, yf**2, xf * yf, xf, yf, np.ones(xf.size)]
        coeff, _, _, _ = np.linalg.lstsq(a, out.ravel(), rcond=None)
        out -= coeff[0] * xg**2 + coeff[1] * yg**2 + coeff[2] * xg * yg + coeff[3] * xg + coeff[4] * yg + coeff[5]
    elif mode == "Differentiate (X-deriv)":
        out = np.gradient(out, axis=1)
    return np.asarray(out, dtype=float)


def prepare_fft_filter_input(data: Any, *, window_name: str = "Hanning", subtract_mean: bool = True) -> np.ndarray:
    arr = np.asarray(data, dtype=float)
    if arr.ndim not in (2, 3):
        raise ValueError("FFT filter expects a 2D map or 3D cube")
    if subtract_mean:
        if arr.ndim == 2:
            mean_val = float(np.nanmean(arr))
            if not np.isfinite(mean_val):
                mean_val = 0.0
            out = np.nan_to_num(arr, nan=mean_val, posinf=mean_val, neginf=mean_val) - mean_val
        else:
            mean_val = np.nanmean(arr, axis=(0, 1), keepdims=True)
            mean_val = np.where(np.isfinite(mean_val), mean_val, 0.0)
            out = np.array(arr, copy=True)
            invalid = ~np.isfinite(out)
            if np.any(invalid):
                out[invalid] = np.broadcast_to(mean_val, out.shape)[invalid]
            out = out - mean_val
    else:
        out = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)

    win_name = canonical_fft_window_name(window_name)
    if win_name and win_name != "none":
        win = np.asarray(fft_window_2d(out.shape[:2], win_name), dtype=float)
        if out.ndim == 2:
            out = out * win
        else:
            out = out * win[:, :, None]
    return np.asarray(out, dtype=float)


def compute_fft_filter_complex(data: Any, *, window_name: str = "Hanning", subtract_mean: bool = True) -> np.ndarray:
    prepared = prepare_fft_filter_input(data, window_name=window_name, subtract_mean=subtract_mean)
    return np.fft.fftshift(np.fft.fft2(prepared, axes=(0, 1)), axes=(0, 1))


def _region_bounds(region: dict[str, Any]) -> tuple[str, tuple[float, ...]]:
    shape = str(region.get("shape", "circle")).strip().lower()
    if shape.startswith("rect"):
        if "bounds" in region:
            vals = tuple(float(v) for v in np.asarray(region["bounds"], dtype=float).ravel()[:4])
        else:
            vals = (
                float(region.get("x0", 0.0)),
                float(region.get("x1", 0.0)),
                float(region.get("y0", 0.0)),
                float(region.get("y1", 0.0)),
            )
        if len(vals) != 4:
            raise ValueError("rect FFT ROI requires x0, x1, y0, y1")
        return "rect", vals
    center = region.get("center", region.get("center_kxy", (0.0, 0.0)))
    c = np.asarray(center, dtype=float).ravel()
    if c.size < 2:
        raise ValueError("circle FFT ROI requires center=[kx, ky]")
    radius = float(region.get("radius", region.get("r", 0.0)))
    return "circle", (float(c[0]), float(c[1]), radius)


def build_fft_roi_mask(
    kx_grid: Any,
    ky_grid: Any,
    regions: Sequence[dict[str, Any]] | None,
    *,
    include_neg: bool = True,
    mode: str = "pass",
    invert: bool = False,
) -> np.ndarray | None:
    kx = np.asarray(kx_grid, dtype=float)
    ky = np.asarray(ky_grid, dtype=float)
    if kx.shape != ky.shape:
        raise ValueError("kx_grid and ky_grid must have matching shape")
    if not regions:
        return None

    mask = np.zeros(kx.shape, dtype=bool)
    for region in regions:
        shape, vals = _region_bounds(dict(region))
        if shape == "rect":
            x0, x1, y0, y1 = vals
            if x0 > x1:
                x0, x1 = x1, x0
            if y0 > y1:
                y0, y1 = y1, y0
            mask |= (kx >= x0) & (kx <= x1) & (ky >= y0) & (ky <= y1)
            if include_neg:
                mask |= (kx >= -x1) & (kx <= -x0) & (ky >= -y1) & (ky <= -y0)
        else:
            cx, cy, radius = vals
            if radius <= 0:
                continue
            mask |= ((kx - cx) ** 2 + (ky - cy) ** 2) <= radius**2
            if include_neg:
                mask |= ((kx + cx) ** 2 + (ky + cy) ** 2) <= radius**2

    if invert:
        mask = ~mask
    if str(mode or "pass").strip().lower() == "stop":
        mask = ~mask
    return np.asarray(mask, dtype=bool)


def _display_fft_complex(fft_complex: Any, *, scale_mode: str, display_style: str) -> np.ndarray:
    mag = np.abs(np.asarray(fft_complex))
    if str(display_style).strip().lower().startswith("topo"):
        return np.asarray(apply_fft_display_scale(mag, scale_mode), dtype=np.float32)
    return np.asarray(_signed_scale(mag, scale_mode), dtype=np.float32)


def run_fft_filter(
    data: Any,
    *,
    scan_size_nm: float | Sequence[float],
    regions: Sequence[dict[str, Any]] | None = None,
    include_neg: bool = True,
    mode: str = "pass",
    invert: bool = False,
    window_name: str = "Hanning",
    scale_mode: str = "Linear",
    background_mode: str = "Raw",
    input_kind: str = "qpi_cube",
    display_style: str = "qpi",
    subtract_mean: bool = True,
) -> dict[str, Any]:
    arr = np.asarray(data, dtype=float)
    was_2d = arr.ndim == 2
    if arr.ndim not in (2, 3):
        raise ValueError("FFT filter expects a 2D map or 3D cube")
    processed = apply_filter_background_2d(arr, background_mode) if arr.ndim == 2 else np.asarray(arr, dtype=float)

    fft_complex = compute_fft_filter_complex(processed, window_name=window_name, subtract_mean=subtract_mean)
    kx_axis, ky_axis, kx_grid, ky_grid = fft_filter_k_axes(processed.shape[:2], scan_size_nm)
    mask = build_fft_roi_mask(kx_grid, ky_grid, regions, include_neg=include_neg, mode=mode, invert=invert)

    if mask is None or not np.any(mask):
        fft_filtered = np.array(fft_complex, copy=True)
        filtered = np.array(processed, copy=True)
    else:
        fft_filtered = np.array(fft_complex, copy=True)
        if processed.ndim == 2:
            fft_filtered = fft_filtered * mask
            filtered = np.real(np.fft.ifft2(np.fft.ifftshift(fft_filtered)))
        else:
            fft_filtered = fft_filtered * mask[:, :, None]
            filtered = np.real(np.fft.ifft2(np.fft.ifftshift(fft_filtered, axes=(0, 1)), axes=(0, 1)))

    summary_values = np.asarray(filtered, dtype=float)
    finite = summary_values[np.isfinite(summary_values)]
    return {
        "processed": np.asarray(processed, dtype=float),
        "filtered": np.asarray(filtered, dtype=float),
        "fft_complex": np.asarray(fft_complex),
        "fft_filtered_complex": np.asarray(fft_filtered),
        "fft_display": _display_fft_complex(fft_complex, scale_mode=scale_mode, display_style=display_style),
        "fft_filtered_display": _display_fft_complex(fft_filtered, scale_mode=scale_mode, display_style=display_style),
        "mask": np.asarray(mask, dtype=bool) if mask is not None else np.ones(processed.shape[:2], dtype=bool),
        "kx_axis": kx_axis,
        "ky_axis": ky_axis,
        "algorithm": fft_filter_algorithm(),
        "parameters": {
            "input_kind": str(input_kind),
            "scan_size_nm": [float(v) for v in _scan_size_pair(scan_size_nm)],
            "regions": [dict(r) for r in (regions or [])],
            "include_neg": bool(include_neg),
            "mode": str(mode or "pass"),
            "invert": bool(invert),
            "window_name": str(window_name),
            "scale_mode": str(scale_mode),
            "background_mode": str(background_mode),
            "display_style": str(display_style),
            "subtract_mean": bool(subtract_mean),
            "was_2d": bool(was_2d),
        },
        "summary": {
            "shape": [int(v) for v in processed.shape],
            "mask_true_count": int(np.count_nonzero(mask)) if mask is not None else int(np.prod(processed.shape[:2])),
            "finite_count": int(finite.size),
            "filtered_min": float(np.min(finite)) if finite.size else np.nan,
            "filtered_max": float(np.max(finite)) if finite.size else np.nan,
        },
    }
