from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from scipy.ndimage import map_coordinates

from .fft_windowing import apply_fft_display_scale, build_windowed_fft_complex


TOPOGRAPHY_DISPLAY_SOURCE_MAPPING = (
    "topography_display.TopographyWindow.reprocess_data, reprocess_fft, "
    "update_linecut_topo, update_linecut_fft, calculate_lattice"
)


def topography_display_algorithm(engine: str = "analystm.topography_display.compute_topography_fft_display") -> dict[str, str]:
    return {
        "name": "AnalySTM topography display backend",
        "engine": engine,
        "pysidam_source_mapping": TOPOGRAPHY_DISPLAY_SOURCE_MAPPING,
    }


def process_topography_display_map(data: Any, background_mode: str = "Raw") -> np.ndarray:
    out = np.asarray(data, dtype=float).copy()
    if out.ndim != 2:
        raise ValueError("topography display map expects a 2D image")
    mode = str(background_mode or "Raw").strip()
    ny, nx = out.shape
    if mode == "Sub Global Mean":
        out -= np.mean(out)
    elif mode == "Sub Line Mean (0-order)":
        out -= np.mean(out, axis=1, keepdims=True)
    elif mode == "Sub Line Mean (Row+Col)":
        out -= np.mean(out, axis=1, keepdims=True)
        out -= np.mean(out, axis=0, keepdims=True)
    elif mode == "Sub Line Linear (1-order)":
        x = np.arange(nx, dtype=float)
        for i in range(ny):
            fit = np.polyfit(x, out[i], 1)
            out[i] -= np.polyval(fit, x)
    elif mode == "Sub Plane (Global)":
        xg, yg = np.meshgrid(np.arange(nx, dtype=float), np.arange(ny, dtype=float))
        a = np.c_[xg.ravel(), yg.ravel(), np.ones(xg.size)]
        c, _, _, _ = np.linalg.lstsq(a, out.ravel(), rcond=None)
        out -= c[0] * xg + c[1] * yg + c[2]
    elif mode == "Sub Parabolic (Global)":
        xg, yg = np.meshgrid(np.arange(nx, dtype=float), np.arange(ny, dtype=float))
        xf = xg.ravel()
        yf = yg.ravel()
        a = np.c_[xf**2, yf**2, xf * yf, xf, yf, np.ones(xf.size)]
        c, _, _, _ = np.linalg.lstsq(a, out.ravel(), rcond=None)
        out -= c[0] * xg**2 + c[1] * yg**2 + c[2] * xg * yg + c[3] * xg + c[4] * yg + c[5]
    elif mode == "Differentiate (X-deriv)":
        out = np.gradient(out, axis=1)
    return np.asarray(out, dtype=float)


def compute_topography_fft_display(
    data: Any,
    *,
    scan_size_nm: float,
    window_name: str = "Hanning",
    scale_mode: str = "Log",
    background_mode: str = "Raw",
) -> dict[str, Any]:
    processed = process_topography_display_map(data, background_mode=background_mode)
    fft_complex = build_windowed_fft_complex(processed, window_name=window_name)
    mag = np.abs(fft_complex)
    display = apply_fft_display_scale(mag, scale_mode)
    nx = int(processed.shape[1])
    k_max = (float(nx) / 2.0) * (2.0 * np.pi / float(scan_size_nm))
    return {
        "processed": processed,
        "fft_complex": np.asarray(fft_complex),
        "fft_display": np.asarray(display, dtype=float),
        "k_extent": [-float(k_max), float(k_max), -float(k_max), float(k_max)],
        "algorithm": topography_display_algorithm(),
        "parameters": {
            "scan_size_nm": float(scan_size_nm),
            "window_name": str(window_name),
            "scale_mode": str(scale_mode),
            "background_mode": str(background_mode),
        },
    }


def sample_topography_linecut(data: Any, *, scan_size_nm: float, p1_nm: Sequence[float], p2_nm: Sequence[float]) -> dict[str, Any]:
    arr = np.asarray(data, dtype=float)
    if arr.ndim != 2:
        raise ValueError("topography linecut expects a 2D image")
    p1 = np.asarray(p1_nm, dtype=float).ravel()
    p2 = np.asarray(p2_nm, dtype=float).ravel()
    if p1.size < 2 or p2.size < 2:
        raise ValueError("linecut endpoints must be x,y")
    ny, nx = arr.shape
    sx = nx / float(scan_size_nm)
    sy = ny / float(scan_size_nm)
    x0, y0 = float(p1[0]) * sx, float(p1[1]) * sy
    x1, y1 = float(p2[0]) * sx, float(p2[1]) * sy
    length_px = np.hypot(x1 - x0, y1 - y0)
    n = max(2, int(length_px))
    xs = np.linspace(x0, x1, n)
    ys = np.linspace(y0, y1, n)
    values = map_coordinates(arr, np.vstack((ys, xs)), order=1)
    distance = np.linspace(0.0, float(np.hypot(float(p1[0]) - float(p2[0]), float(p1[1]) - float(p2[1]))), n)
    return {
        "distance_nm": np.asarray(distance, dtype=float),
        "values": np.asarray(values, dtype=float),
        "algorithm": topography_display_algorithm("analystm.topography_display.sample_topography_linecut"),
        "parameters": {"scan_size_nm": float(scan_size_nm), "p1_nm": [float(p1[0]), float(p1[1])], "p2_nm": [float(p2[0]), float(p2[1])]},
    }


def sample_fft_linecut(fft_display: Any, *, scan_size_nm: float, p1_q: Sequence[float], p2_q: Sequence[float]) -> dict[str, Any]:
    data = np.asarray(fft_display, dtype=float)
    if data.ndim != 2:
        raise ValueError("FFT linecut expects a 2D FFT display map")
    p1 = np.asarray(p1_q, dtype=float).ravel()
    p2 = np.asarray(p2_q, dtype=float).ravel()
    if p1.size < 2 or p2.size < 2:
        raise ValueError("FFT linecut endpoints must be qx,qy")
    nx = int(data.shape[0])
    k_max = (float(nx) / 2.0) * (2.0 * np.pi / float(scan_size_nm))

    def k2p(v: float) -> float:
        return (float(v) - (-k_max)) / (2.0 * k_max) * float(nx)

    x0, y0 = k2p(float(p1[0])), k2p(float(p1[1]))
    x1, y1 = k2p(float(p2[0])), k2p(float(p2[1]))
    n = max(2, int(np.hypot(x1 - x0, y1 - y0)))
    xs = np.linspace(x0, x1, n)
    ys = np.linspace(y0, y1, n)
    values = map_coordinates(data, np.vstack((ys, xs)), order=1)
    q_dist = np.linspace(0.0, float(np.hypot(float(p1[0]) - float(p2[0]), float(p1[1]) - float(p2[1]))), n)
    return {
        "distance_q": np.asarray(q_dist, dtype=float),
        "values": np.asarray(values, dtype=float),
        "algorithm": topography_display_algorithm("analystm.topography_display.sample_fft_linecut"),
        "parameters": {"scan_size_nm": float(scan_size_nm), "p1_q": [float(p1[0]), float(p1[1])], "p2_q": [float(p2[0]), float(p2[1])]},
    }


def lattice_constant_from_delta_q(delta_q: float, *, lattice: str = "square") -> float:
    dq = abs(float(delta_q))
    if dq < 1e-4:
        return float("nan")
    if str(lattice or "square").strip().lower().startswith("hex"):
        return float((8.0 * np.pi) / (np.sqrt(3.0) * dq))
    return float((4.0 * np.pi) / dq)
