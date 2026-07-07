from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from scipy import ndimage

from .dataset_utils import extract_sxm_scan_dir, normalize_sxm_direction_map


MAP_CROP_SOURCE_MAPPING = (
    "usefultools_map_crop.UsefulToolsMapCropWindow._compute_sampling_geometry, "
    "_sample_display_patch, _build_generated_header, _crop_sxm_signals, _crop_3ds_signals"
)


def map_crop_algorithm(engine: str = "analystm.map_crop.compute_square_crop_geometry") -> dict[str, str]:
    return {
        "name": "AnalySTM map crop backend",
        "engine": engine,
        "pysidam_source_mapping": MAP_CROP_SOURCE_MAPPING,
    }


def source_size_xy_nm(header: dict[str, Any] | None = None, scan_size_nm: float | Sequence[float] = 100.0) -> tuple[float, float]:
    arr = np.asarray(scan_size_nm, dtype=float).ravel()
    if arr.size >= 2:
        sx = float(arr[0])
        sy = float(arr[1])
    elif arr.size == 1:
        sx = sy = float(arr[0])
    else:
        sx = sy = 100.0
    if not np.isfinite(sx) or sx <= 0:
        sx = 100.0
    if not np.isfinite(sy) or sy <= 0:
        sy = sx
    if not isinstance(header, dict):
        return float(sx), float(sy)

    for key in ("size_xy", "scan_range"):
        try:
            vals = header.get(key)
            if isinstance(vals, (list, tuple, np.ndarray)) and len(vals) >= 2:
                x_nm = float(vals[0]) * 1e9
                y_nm = float(vals[1]) * 1e9
                if np.isfinite(x_nm) and x_nm > 0:
                    sx = x_nm
                if np.isfinite(y_nm) and y_nm > 0:
                    sy = y_nm
                break
        except Exception:
            pass
    return float(sx), float(sy)


def canonical_direction(key: Any) -> str:
    text = str(key or "").strip().lower()
    return "backward" if text.startswith("back") else "forward"


def undo_sxm_display_orientation(data: Any, direction: str = "forward", header: dict[str, Any] | None = None) -> np.ndarray:
    arr = np.asarray(data, dtype=float)
    if str(direction).lower() == "backward":
        arr = np.fliplr(arr)
    if extract_sxm_scan_dir(header, default="down") == "up":
        arr = np.flipud(arr)
    return np.ascontiguousarray(arr, dtype=float)


def extract_sxm_display_map(packet: Any, header: dict[str, Any] | None = None) -> np.ndarray | None:
    if isinstance(packet, dict):
        raw = None
        direction = "forward"
        for preferred in ("forward", "backward"):
            for key, value in packet.items():
                if canonical_direction(key) == preferred:
                    raw = value
                    direction = preferred
                    break
            if raw is not None:
                break
        if raw is None and packet:
            first_key = next(iter(packet.keys()))
            raw = packet[first_key]
            direction = canonical_direction(first_key)
    else:
        raw = packet
        direction = "forward"
    if raw is None:
        return None
    display = normalize_sxm_direction_map(raw, direction=direction, header=header)
    try:
        arr = np.asarray(display, dtype=float)
    except Exception:
        return None
    if arr.ndim != 2:
        return None
    return np.ascontiguousarray(arr, dtype=float)


def compute_square_crop_geometry(
    *,
    preview_shape_yx: Sequence[int],
    center_xy_px: Sequence[float],
    side_px: float,
    angle_deg: float = 0.0,
    source_size_nm_xy: Sequence[float] | float = 100.0,
) -> dict[str, Any]:
    full_h = int(preview_shape_yx[0])
    full_w = int(preview_shape_yx[1])
    if full_h <= 0 or full_w <= 0:
        raise ValueError("preview shape must be positive")
    center = np.asarray(center_xy_px, dtype=float).ravel()
    if center.size < 2:
        raise ValueError("center_xy_px must contain x,y")
    center_x = float(center[0])
    center_y = float(center[1])
    side = max(1.0, float(side_px))
    span_x = side
    span_y = side
    out_w = max(1, int(round(span_x)))
    out_h = max(1, int(round(span_y)))

    u = ((np.arange(out_w, dtype=float) + 0.5) / float(out_w) - 0.5) * float(span_x)
    v = ((np.arange(out_h, dtype=float) + 0.5) / float(out_h) - 0.5) * float(span_y)
    uu, vv = np.meshgrid(u, v)

    theta = np.deg2rad(float(angle_deg))
    cos_t = float(np.cos(theta))
    sin_t = float(np.sin(theta))
    xx = center_x + uu * cos_t - vv * sin_t
    yy = center_y + uu * sin_t + vv * cos_t

    src_size = np.asarray(source_size_nm_xy, dtype=float).ravel()
    if src_size.size >= 2:
        src_x_nm = float(src_size[0])
        src_y_nm = float(src_size[1])
    elif src_size.size == 1:
        src_x_nm = src_y_nm = float(src_size[0])
    else:
        src_x_nm = src_y_nm = 100.0
    crop_x_nm = src_x_nm * float(span_x) / max(float(full_w), 1.0)
    crop_y_nm = src_y_nm * float(span_y) / max(float(full_h), 1.0)

    return {
        "rows": np.asarray(yy - 0.5, dtype=float),
        "cols": np.asarray(xx - 0.5, dtype=float),
        "out_shape": (int(out_h), int(out_w)),
        "crop_size_nm": (float(crop_x_nm), float(crop_y_nm)),
        "outer_size_px": (float(side), float(side)),
        "inner_size_px": (float(span_x), float(span_y)),
        "mode_label": "Square",
        "source_angle_deg": float(angle_deg),
        "output_angle_deg": float(angle_deg),
        "algorithm": map_crop_algorithm(),
    }


def sample_display_patch(display_arr: Any, geometry: dict[str, Any]) -> np.ndarray | None:
    if display_arr is None or geometry is None:
        return None
    arr = np.asarray(display_arr, dtype=float)
    if arr.ndim != 2:
        return None
    rows = np.asarray(geometry["rows"], dtype=float)
    cols = np.asarray(geometry["cols"], dtype=float)
    try:
        patch = ndimage.map_coordinates(arr, [rows, cols], order=1, mode="nearest")
    except Exception:
        return None
    return np.ascontiguousarray(patch, dtype=float)


def safe_percentile_levels(data: Any, low: float = 1.0, high: float = 99.0) -> tuple[float, float] | None:
    if data is None:
        return None
    try:
        arr = np.asarray(data, dtype=float)
    except Exception:
        return None
    finite = arr[np.isfinite(arr)]
    if finite.size <= 0:
        return None
    try:
        lo = float(np.nanpercentile(finite, float(low)))
        hi = float(np.nanpercentile(finite, float(high)))
    except Exception:
        lo = float(np.nanmin(finite))
        hi = float(np.nanmax(finite))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo = float(np.nanmin(finite))
        hi = float(np.nanmax(finite))
    if not np.isfinite(lo) or not np.isfinite(hi):
        return None
    if hi <= lo:
        pad = max(1e-12, abs(lo) * 0.01, 1.0)
        lo -= pad
        hi += pad
    return lo, hi


def build_generated_header(
    header: dict[str, Any] | None,
    geometry: dict[str, Any],
    *,
    dtype: str,
    bias_len: int | None = None,
    source_file: str | None = None,
    source_channel: str | None = None,
) -> dict[str, Any]:
    out = dict(header or {})
    crop_x_nm, crop_y_nm = geometry["crop_size_nm"]
    out_h, out_w = geometry["out_shape"]
    out["size_xy"] = [float(crop_x_nm) * 1e-9, float(crop_y_nm) * 1e-9]
    out["scan_range"] = [float(crop_x_nm) * 1e-9, float(crop_y_nm) * 1e-9]
    out["crop_mode"] = geometry["mode_label"]
    out["crop_source_file"] = source_file
    out["crop_source_channel"] = source_channel
    out["crop_outer_size_px"] = [float(geometry["outer_size_px"][0]), float(geometry["outer_size_px"][1])]
    out["crop_output_size_px"] = [int(out_w), int(out_h)]
    out["crop_output_angle_deg"] = float(geometry["output_angle_deg"])
    if str(dtype).lower() == "3ds":
        grid_w = int(out_w)
        grid_h = int(out_h)
        for key in ("dim_px", "grid_dim", "dim_pixels", "grid_dim_px", "grid_size", "pixels", "grid_pixels"):
            if key in out:
                out[key] = [grid_w, grid_h]
        for key in ("nx", "x_pixels", "grid_nx"):
            if key in out:
                out[key] = grid_w
        for key in ("ny", "y_pixels", "grid_ny"):
            if key in out:
                out[key] = grid_h
        if bias_len is not None:
            out["num_sweep_signal"] = int(bias_len)
    return out


def crop_sxm_signals(signals: dict[str, Any], geometry: dict[str, Any], header: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for chan, packet in (signals or {}).items():
        if isinstance(packet, dict):
            cropped_packet: dict[str, np.ndarray] = {}
            for raw_dir_key, raw_arr in packet.items():
                direction = canonical_direction(raw_dir_key)
                display_arr = extract_sxm_display_map({direction: raw_arr}, header=header)
                patch = sample_display_patch(display_arr, geometry)
                if patch is None:
                    continue
                cropped_packet[raw_dir_key] = undo_sxm_display_orientation(patch, direction, header=header)
            if cropped_packet:
                out[str(chan)] = cropped_packet
        else:
            display_arr = extract_sxm_display_map(packet, header=header)
            patch = sample_display_patch(display_arr, geometry)
            if patch is None:
                continue
            out[str(chan)] = undo_sxm_display_orientation(patch, "forward", header=header)
    return out


def crop_3ds_signals(signals: dict[str, Any], geometry: dict[str, Any]) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for chan, value in (signals or {}).items():
        cube = np.asarray(value, dtype=float)
        if cube.ndim == 2:
            cube = cube[:, :, np.newaxis]
        if cube.ndim != 3:
            continue
        layers: list[np.ndarray] = []
        for idx in range(cube.shape[2]):
            display_arr = np.asarray(cube[:, :, idx], dtype=float).T
            patch = sample_display_patch(display_arr, geometry)
            if patch is None:
                break
            layers.append(np.asarray(patch, dtype=float).T)
        if not layers:
            continue
        out[str(chan)] = np.ascontiguousarray(np.stack(layers, axis=2), dtype=float)
    return out
