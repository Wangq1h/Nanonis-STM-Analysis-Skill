from __future__ import annotations

import time
from typing import Any, Sequence
import math

import numpy as np
from scipy import ndimage

from .fft_windowing import apply_fft_dc_mask, canonical_fft_window_name, fft_window_1d, fft_window_2d
from .phase_lockin import unwrap_phase_2d, wrap_pi


QPI_SYMMETRY_SOURCE_MAPPING = "qpi_symmetry.symmetrize_qpi and _rotate_image_xy"
PR_QPI_SOURCE_MAPPING = "qpi_pr_pqi._compute_pr_qpi_volume"
QPI_FFT_SOURCE_MAPPING = "qpi_display._compute_fft_base_volume, _prepare_fft_block, and _postprocess_fft_volume"
QPI_REAL_PHASE_SOURCE_MAPPING = "qpi_real_phase.lockin_phase and PRLibWindow.run_prlib p_LL formula"
QPI_1D_SOURCE_MAPPING = (
    "qpi_1D_QPI._extract_linecut_pixels, _build_fft_dc_gaussian_notch_1d_discrete, "
    "_apply_fft_q0_mask, and QPI1DWindow.recompute_linecut_and_fft"
)


def qpi_algorithm(engine: str, *, source_mapping: str) -> dict[str, str]:
    return {
        "name": "AnalySTM QPI backend",
        "engine": engine,
        "pysidam_source_mapping": source_mapping,
    }


def _signed_scale(data: Any, scale_mode: str) -> np.ndarray:
    arr = np.asarray(data, dtype=np.float32)
    mode = str(scale_mode).strip().lower()
    if "sqrt" in mode:
        return (np.sign(arr) * np.sqrt(np.abs(arr))).astype(np.float32, copy=False)
    if "log" in mode:
        return (np.sign(arr) * np.log10(np.abs(arr) + 1e-12)).astype(np.float32, copy=False)
    return arr.astype(np.float32, copy=False)


def qpi1d_fft_display_scale(data: Any, mode: str) -> np.ndarray:
    arr = np.asarray(data, dtype=np.float32)
    text = str(mode).strip().lower()
    if "sqrt" in text:
        return np.sqrt(np.clip(arr, 0.0, None)).astype(np.float32, copy=False)
    if "log" in text:
        return np.log10(np.clip(arr, 0.0, None) + 1e-12).astype(np.float32, copy=False)
    return arr.astype(np.float32, copy=False)


def safe_axis_step(axis: Any) -> float:
    try:
        arr = np.asarray(axis, dtype=float).ravel()
    except Exception:
        return 1.0
    if arr.size < 2:
        return 1.0
    step = float(arr[1] - arr[0])
    if not np.isfinite(step) or step == 0:
        return 1.0
    return step


def build_fft_q0_gaussian_notch_1d_discrete(length: int, sigma_px: float = 1.5, center: float | None = None) -> np.ndarray | None:
    n = int(length)
    if n <= 0:
        return None
    try:
        sigma = float(sigma_px)
    except Exception:
        sigma = 0.0
    if not np.isfinite(sigma) or sigma <= 0.0:
        return np.ones(n, dtype=float)

    c = float(n // 2) if center is None else float(center)
    xx = np.arange(n, dtype=float) - c
    denom = math.sqrt(2.0) * max(sigma, 1e-18)
    scale = math.sqrt(math.pi / 2.0) * sigma
    erf_vec = np.vectorize(math.erf, otypes=[float])
    avg_gaussian = scale * (erf_vec((xx + 0.5) / denom) - erf_vec((xx - 0.5) / denom))
    avg_gaussian = np.clip(avg_gaussian, 0.0, 1.0)
    return np.asarray(1.0 - avg_gaussian, dtype=float)


def apply_fft_q0_mask_1d(data: Any, radius_px: float = 1.5, copy: bool = True) -> np.ndarray:
    arr = np.array(data, copy=bool(copy))
    if arr.ndim < 1:
        return arr
    try:
        sigma = float(radius_px)
    except Exception:
        sigma = 0.0
    if not np.isfinite(sigma) or sigma <= 0.0:
        return arr
    notch = build_fft_q0_gaussian_notch_1d_discrete(int(arr.shape[0]), sigma_px=sigma)
    if notch is None:
        return arr
    notch = np.asarray(notch, dtype=arr.dtype)
    if arr.ndim == 1:
        return np.asarray(arr * notch, dtype=arr.dtype)
    shape = (int(arr.shape[0]),) + (1,) * (arr.ndim - 1)
    return np.asarray(arr * notch.reshape(shape), dtype=arr.dtype)


def remove_qpi1d_linear_baseline_1d(x_axis: Any, y: Any) -> np.ndarray:
    yy = np.asarray(y, dtype=float).ravel()
    if yy.size == 0:
        return yy
    x = np.asarray(x_axis, dtype=float).ravel()
    n = min(x.size, yy.size)
    if n < 4:
        return yy[:n]
    x = x[:n]
    y0 = yy[:n]
    out = y0.copy()
    finite = np.isfinite(x) & np.isfinite(y0)
    if np.sum(finite) < 4:
        return out
    x_f = x[finite]
    y_f = y0[finite]
    m = x_f.size
    n_edge = max(3, int(np.ceil(0.12 * m)))
    n_edge = min(n_edge, max(3, m // 2))
    idx = np.r_[0:n_edge, m - n_edge:m]
    try:
        k, b = np.polyfit(x_f[idx], y_f[idx], 1)
        out[finite] = y0[finite] - (k * x_f + b)
        return out
    except Exception:
        return out


def remove_qpi1d_linear_baseline_cube(bias_axis: Any, cube: Any) -> np.ndarray:
    arr = np.asarray(cube, dtype=float)
    if arr.ndim != 3 or arr.size == 0:
        return np.asarray(arr, dtype=np.float32)
    bias = np.asarray(bias_axis, dtype=float).ravel()
    nz = min(arr.shape[2], bias.size)
    if nz < 4:
        return np.asarray(arr[:, :, :nz], dtype=np.float32)
    out = np.asarray(arr[:, :, :nz], dtype=float).copy()
    flat = out.reshape(-1, nz)
    for i in range(flat.shape[0]):
        flat[i, :] = remove_qpi1d_linear_baseline_1d(bias[:nz], flat[i, :])
    return np.asarray(out, dtype=np.float32)


def _qpi1d_cube_xyb(cube: Any, cube_order: str = "xyb") -> np.ndarray:
    arr = np.asarray(cube, dtype=float)
    if arr.ndim != 3:
        raise ValueError("1D-QPI expects a 3D cube")
    order = str(cube_order or "xyb").strip().lower()
    if order in {"xyb", "xybias", "x,y,bias"}:
        return np.ascontiguousarray(arr, dtype=np.float32)
    if order in {"yxb", "yxbias", "y,x,bias"}:
        return np.ascontiguousarray(np.transpose(arr, (1, 0, 2)), dtype=np.float32)
    raise ValueError("cube_order must be 'xyb' or 'yxb'")


def _qpi1d_default_endpoints(size_x_nm: float, size_y_nm: float, dx_nm: float) -> tuple[float, float, float, float]:
    y_mid = float(size_y_nm) * 0.5 if np.isfinite(size_y_nm) and size_y_nm > 0 else 0.5
    x0 = float(size_x_nm) * 0.2 if np.isfinite(size_x_nm) and size_x_nm > 0 else 0.0
    x1 = float(size_x_nm) * 0.8 if np.isfinite(size_x_nm) and size_x_nm > 0 else max(1.0, float(dx_nm))
    return x0, y_mid, x1, y_mid


def extract_qpi_1d_linecut(
    cube_xyb: Any,
    *,
    scan_size_nm: float | Sequence[float],
    p1_nm: Sequence[float] | None = None,
    p2_nm: Sequence[float] | None = None,
) -> dict[str, np.ndarray]:
    grid_cube = np.asarray(cube_xyb, dtype=np.float32)
    if grid_cube.ndim != 3:
        raise ValueError("extract_qpi_1d_linecut expects a 3D cube in (x, y, bias) order")
    nx, ny, _ = grid_cube.shape
    sizes = np.asarray(scan_size_nm, dtype=float).ravel()
    size_x_nm = float(sizes[0]) if sizes.size else 100.0
    size_y_nm = float(sizes[1]) if sizes.size > 1 else size_x_nm
    dx_nm = size_x_nm / max(nx - 1, 1) if nx > 1 else 1.0
    dy_nm = size_y_nm / max(ny - 1, 1) if ny > 1 else 1.0

    if nx > 1 and ny == 1:
        line = np.asarray(grid_cube[:, 0, :], dtype=np.float32)
        xs_nm = np.linspace(0.0, size_x_nm, nx, dtype=float) if nx > 1 else np.array([0.0], dtype=float)
        ys_nm = np.full(nx, 0.5 * size_y_nm, dtype=float)
        dist_nm = np.asarray(xs_nm, dtype=float)
        return {"line": line, "distance_nm": dist_nm, "x_nm": xs_nm, "y_nm": ys_nm}
    if ny > 1 and nx == 1:
        line = np.asarray(grid_cube[0, :, :], dtype=np.float32)
        ys_nm = np.linspace(0.0, size_y_nm, ny, dtype=float) if ny > 1 else np.array([0.0], dtype=float)
        xs_nm = np.full(ny, 0.5 * size_x_nm, dtype=float)
        dist_nm = np.asarray(ys_nm, dtype=float)
        return {"line": line, "distance_nm": dist_nm, "x_nm": xs_nm, "y_nm": ys_nm}

    if p1_nm is None or p2_nm is None:
        x0_nm, y0_nm, x1_nm, y1_nm = _qpi1d_default_endpoints(size_x_nm, size_y_nm, dx_nm)
    else:
        x0_nm, y0_nm = float(p1_nm[0]), float(p1_nm[1])
        x1_nm, y1_nm = float(p2_nm[0]), float(p2_nm[1])

    if size_x_nm > 0:
        x0_nm = float(np.clip(x0_nm, 0.0, size_x_nm))
        x1_nm = float(np.clip(x1_nm, 0.0, size_x_nm))
    if size_y_nm > 0:
        y0_nm = float(np.clip(y0_nm, 0.0, size_y_nm))
        y1_nm = float(np.clip(y1_nm, 0.0, size_y_nm))
    line_len_nm = float(np.hypot(x1_nm - x0_nm, y1_nm - y0_nm))
    if not np.isfinite(line_len_nm) or line_len_nm <= 0:
        x0_nm, y0_nm, x1_nm, y1_nm = _qpi1d_default_endpoints(size_x_nm, size_y_nm, dx_nm)
        line_len_nm = float(np.hypot(x1_nm - x0_nm, y1_nm - y0_nm))
    if not np.isfinite(line_len_nm) or line_len_nm <= 0:
        raise ValueError("invalid 1D-QPI linecut endpoints")

    x0_px = x0_nm / size_x_nm * max(nx - 1, 1) if size_x_nm > 0 else 0.0
    x1_px = x1_nm / size_x_nm * max(nx - 1, 1) if size_x_nm > 0 else float(max(nx - 1, 0))
    y0_px = y0_nm / size_y_nm * max(ny - 1, 1) if size_y_nm > 0 else 0.0
    y1_px = y1_nm / size_y_nm * max(ny - 1, 1) if size_y_nm > 0 else float(max(ny - 1, 0))

    n = max(2, int(np.hypot(x1_px - x0_px, y1_px - y0_px)) + 1)
    xs_px = np.linspace(x0_px, x1_px, n, dtype=float)
    ys_px = np.linspace(y0_px, y1_px, n, dtype=float)
    dist_nm = np.sqrt(((xs_px - x0_px) * dx_nm) ** 2 + ((ys_px - y0_px) * dy_nm) ** 2)

    ix = np.clip(np.round(xs_px).astype(int), 0, nx - 1)
    iy = np.clip(np.round(ys_px).astype(int), 0, ny - 1)
    kept_ix: list[int] = []
    kept_iy: list[int] = []
    kept_dist: list[float] = []
    last = None
    for px, py, dist in zip(ix, iy, dist_nm):
        key = (int(px), int(py))
        if key == last:
            continue
        kept_ix.append(key[0])
        kept_iy.append(key[1])
        kept_dist.append(float(dist))
        last = key
    if len(kept_ix) < 2:
        raise ValueError("1D-QPI linecut has fewer than two unique pixels")

    ix_arr = np.asarray(kept_ix, dtype=int)
    iy_arr = np.asarray(kept_iy, dtype=int)
    xs_nm = ix_arr.astype(float) * (size_x_nm / max(nx - 1, 1) if nx > 1 else 1.0)
    ys_nm = iy_arr.astype(float) * (size_y_nm / max(ny - 1, 1) if ny > 1 else 1.0)
    line = np.asarray(grid_cube[ix_arr, iy_arr, :], dtype=np.float32)
    return {"line": line, "distance_nm": np.asarray(kept_dist, dtype=float), "x_nm": xs_nm, "y_nm": ys_nm}


def compute_qpi_1d_fft(
    cube: Any,
    *,
    bias: Sequence[float] | None = None,
    scan_size_nm: float | Sequence[float] = 100.0,
    p1_nm: Sequence[float] | None = None,
    p2_nm: Sequence[float] | None = None,
    cube_order: str = "xyb",
    background_mode: str = "None",
    window_name: str = "none",
    mask_q0: bool = True,
    mask_radius_px: float = 1.5,
    scale_mode: str = "Sqrt",
    smooth_size: int = 0,
) -> dict[str, Any]:
    grid_cube = _qpi1d_cube_xyb(cube, cube_order=cube_order)
    b = np.asarray(bias, dtype=float).ravel() if bias is not None else np.arange(grid_cube.shape[2], dtype=float)
    nz = min(grid_cube.shape[2], b.size)
    if nz <= 0:
        raise ValueError("1D-QPI cube has no bias layers")
    grid_cube = np.asarray(grid_cube[:, :, :nz], dtype=np.float32)
    b = b[:nz]
    if str(background_mode) == "Linear Tilt":
        grid_cube = remove_qpi1d_linear_baseline_cube(b, grid_cube)

    sampled = extract_qpi_1d_linecut(grid_cube, scan_size_nm=scan_size_nm, p1_nm=p1_nm, p2_nm=p2_nm)
    line = np.asarray(sampled["line"], dtype=np.float32)
    dist_nm = np.asarray(sampled["distance_nm"], dtype=float)
    proc_fft = line
    dist_fft_nm = dist_nm.copy()
    if dist_nm.size > 2:
        uniform_dist = np.linspace(float(dist_nm[0]), float(dist_nm[-1]), dist_nm.size, dtype=float)
        if np.all(np.isfinite(uniform_dist)) and uniform_dist.size == proc_fft.shape[0]:
            proc_uniform = np.empty_like(proc_fft, dtype=np.float32)
            for i in range(proc_fft.shape[1]):
                proc_uniform[:, i] = np.interp(uniform_dist, dist_nm, proc_fft[:, i]).astype(np.float32, copy=False)
            proc_fft = proc_uniform
            dist_fft_nm = uniform_dist

    mean_val = np.nanmean(proc_fft, axis=0, keepdims=True)
    mean_val = np.where(np.isfinite(mean_val), mean_val, 0.0).astype(np.float32, copy=False)
    proc_fft = np.array(proc_fft, dtype=np.float32, copy=True)
    invalid = ~np.isfinite(proc_fft)
    if np.any(invalid):
        proc_fft[invalid] = np.broadcast_to(mean_val, proc_fft.shape)[invalid]

    win_name = canonical_fft_window_name(window_name)
    if win_name and win_name != "none":
        win = np.asarray(fft_window_1d(proc_fft.shape[0], win_name), dtype=np.float32)
        proc_fft = np.asarray(proc_fft * win[:, None], dtype=np.float32)

    fft_complex = np.fft.fftshift(np.fft.fft(proc_fft, axis=0), axes=0)
    fft_mag = np.abs(fft_complex).astype(np.float32, copy=False)
    if mask_q0:
        fft_mag = np.asarray(apply_fft_q0_mask_1d(fft_mag, radius_px=mask_radius_px, copy=True), dtype=np.float32)

    ds_nm = float(np.nanmedian(np.diff(dist_fft_nm))) if dist_fft_nm.size > 1 else 1.0
    if not np.isfinite(ds_nm) or ds_nm <= 0:
        ds_nm = 1.0
    q_axis = (np.fft.fftshift(np.fft.fftfreq(proc_fft.shape[0], d=ds_nm)) * (2.0 * np.pi)).astype(float)

    line_display = np.asarray(line, dtype=np.float32)
    fft_display_source = np.asarray(fft_mag, dtype=np.float32)
    if int(smooth_size or 0) > 1:
        smooth_n = max(1, int(smooth_size))
        line_display = np.asarray(ndimage.uniform_filter(line_display, size=smooth_n), dtype=np.float32)
        fft_display_source = np.asarray(ndimage.uniform_filter(fft_display_source, size=smooth_n), dtype=np.float32)
        if mask_q0:
            fft_display_source = np.asarray(apply_fft_q0_mask_1d(fft_display_source, radius_px=mask_radius_px, copy=True), dtype=np.float32)
    fft_display = qpi1d_fft_display_scale(fft_display_source, scale_mode)

    sizes = np.asarray(scan_size_nm, dtype=float).ravel()
    scan_pair = [float(sizes[0]) if sizes.size else 100.0, float(sizes[1]) if sizes.size > 1 else (float(sizes[0]) if sizes.size else 100.0)]
    return {
        "line_matrix_raw": line,
        "line_matrix_display": line_display,
        "line_distance_nm": dist_nm,
        "line_distance_fft_nm": dist_fft_nm,
        "line_x_nm": np.asarray(sampled["x_nm"], dtype=float),
        "line_y_nm": np.asarray(sampled["y_nm"], dtype=float),
        "fft_map_raw": fft_mag,
        "fft_map_display": fft_display,
        "q_axis": q_axis,
        "bias": b,
        "algorithm": qpi_algorithm("analystm.qpi.compute_qpi_1d_fft", source_mapping=QPI_1D_SOURCE_MAPPING),
        "parameters": {
            "scan_size_nm": scan_pair,
            "p1_nm": [float(p1_nm[0]), float(p1_nm[1])] if p1_nm is not None else [],
            "p2_nm": [float(p2_nm[0]), float(p2_nm[1])] if p2_nm is not None else [],
            "cube_order": str(cube_order),
            "background_mode": str(background_mode),
            "window_name": str(window_name),
            "mask_q0": bool(mask_q0),
            "mask_radius_px": float(mask_radius_px),
            "scale_mode": str(scale_mode),
            "smooth_size": int(smooth_size or 0),
        },
        "summary": {
            "n_line_pixels": int(line.shape[0]),
            "n_bias": int(line.shape[1]),
            "q_min_2pi_per_nm": float(np.nanmin(q_axis)) if q_axis.size else np.nan,
            "q_max_2pi_per_nm": float(np.nanmax(q_axis)) if q_axis.size else np.nan,
            "fft_finite_count": int(np.count_nonzero(np.isfinite(fft_mag))),
        },
    }


def qpi_fft_chunk_size(shape: Sequence[int]) -> int:
    try:
        nx, ny, nz = int(shape[0]), int(shape[1]), int(shape[2])
    except Exception:
        return 16
    plane_count = max(1, nx * ny)
    target_bytes = 64 * 1024 * 1024
    bytes_per_layer = max(1, plane_count * 8)
    chunk = max(2, int(target_bytes // bytes_per_layer))
    return int(max(2, min(24, chunk, max(1, nz))))


def prepare_fft_block(data: Any, window_name: str = "Hanning") -> np.ndarray:
    arr = np.asarray(data, dtype=np.float32)
    if arr.ndim < 2:
        return arr
    if arr.ndim == 2:
        mean_val = float(np.nanmean(arr))
        if not np.isfinite(mean_val):
            mean_val = 0.0
        out = np.nan_to_num(arr, nan=mean_val, posinf=mean_val, neginf=mean_val) - mean_val
    else:
        mean_val = np.nanmean(arr, axis=(0, 1), keepdims=True)
        mean_val = np.where(np.isfinite(mean_val), mean_val, 0.0).astype(np.float32, copy=False)
        out = np.array(arr, copy=True)
        invalid = ~np.isfinite(out)
        if np.any(invalid):
            out[invalid] = np.broadcast_to(mean_val, out.shape)[invalid]
        out = out - mean_val
    win_name = canonical_fft_window_name(window_name)
    if win_name and win_name != "none":
        win = np.asarray(fft_window_2d(out.shape[:2], win_name), dtype=np.float32)
        if out.ndim == 2:
            out = out * win
        else:
            out = out * win[:, :, None]
    return np.asarray(out, dtype=np.float32)


def postprocess_fft_volume(base_fft: Any, mask_dc: bool = False, mask_radius_px: float = 1.5, scale_mode: str = "Linear") -> np.ndarray | None:
    if base_fft is None:
        return None
    out = np.asarray(base_fft, dtype=np.float32)
    if mask_dc:
        out = np.asarray(apply_fft_dc_mask(out, radius_px=mask_radius_px, copy=True), dtype=np.float32)
    return _signed_scale(out, scale_mode)


def compute_fft_base_volume(
    cube: Any,
    window_name: str = "Hanning",
    cancel_check: Any = None,
    yield_sleep: float = 0.002,
) -> np.ndarray | None:
    data = np.asarray(cube, dtype=np.float32)

    def _cancelled() -> bool:
        try:
            return bool(cancel_check is not None and cancel_check())
        except Exception:
            return False

    if data.ndim < 3:
        if _cancelled():
            return None
        block = prepare_fft_block(data, window_name=window_name)
        return np.abs(np.fft.fftshift(np.fft.fft2(block, axes=(0, 1)), axes=(0, 1))).astype(np.float32, copy=False)

    nz = int(data.shape[2])
    chunk_size = qpi_fft_chunk_size(data.shape)
    out = np.empty(data.shape, dtype=np.float32)
    for start in range(0, nz, chunk_size):
        if _cancelled():
            return None
        stop = min(nz, start + chunk_size)
        block = prepare_fft_block(data[:, :, start:stop], window_name=window_name)
        fft_data = np.abs(np.fft.fftshift(np.fft.fft2(block, axes=(0, 1)), axes=(0, 1))).astype(np.float32, copy=False)
        out[:, :, start:stop] = fft_data
        if stop < nz and yield_sleep:
            time.sleep(float(yield_sleep))
    return out


def run_qpi_fft(
    cube: Any,
    *,
    window_name: str = "Hanning",
    mask_dc: bool = False,
    mask_radius_px: float = 1.5,
    scale_mode: str = "Linear",
) -> dict[str, Any]:
    base = compute_fft_base_volume(cube, window_name=window_name)
    display = postprocess_fft_volume(base, mask_dc=mask_dc, mask_radius_px=mask_radius_px, scale_mode=scale_mode)
    if base is None or display is None:
        raise RuntimeError("QPI FFT computation was cancelled")
    return {
        "fft_base": base,
        "fft_display": display,
        "algorithm": qpi_algorithm("analystm.qpi.compute_fft_base_volume", source_mapping=QPI_FFT_SOURCE_MAPPING),
        "parameters": {
            "window_name": str(window_name),
            "mask_dc": bool(mask_dc),
            "mask_radius_px": float(mask_radius_px),
            "scale_mode": str(scale_mode),
        },
        "summary": {
            "shape": [int(v) for v in np.asarray(base).shape],
            "finite_count": int(np.count_nonzero(np.isfinite(base))),
            "display_finite_count": int(np.count_nonzero(np.isfinite(display))),
        },
    }


def _as_stack(data: Any) -> tuple[np.ndarray, bool]:
    arr = np.asarray(data, dtype=float)
    was_2d = arr.ndim == 2
    if was_2d:
        arr = arr[:, :, None]
    if arr.ndim != 3:
        raise ValueError("QPI expects a 2D image or 3D energy stack.")
    return np.ascontiguousarray(arr, dtype=float), was_2d


def _rotate_image_xy(image: Any, angle_deg: float, center_xy: Sequence[float] | None = None, order: int = 1, cval: float = np.nan) -> np.ndarray:
    arr = np.asarray(image, dtype=float)
    h, w = arr.shape[:2]
    if center_xy is None:
        center_xy = ((w - 1) / 2.0, (h - 1) / 2.0)
    cx, cy = float(center_xy[0]), float(center_xy[1])
    theta = np.deg2rad(float(angle_deg))

    cos_t = float(np.cos(theta))
    sin_t = float(np.sin(theta))
    linear_xy = np.asarray([[cos_t, sin_t], [-sin_t, cos_t]], dtype=float)
    center = np.asarray([cx, cy], dtype=float)
    offset_xy = center - linear_xy @ center

    a, b = linear_xy[0]
    c, d = linear_xy[1]
    tx, ty = offset_xy
    rc_matrix = np.asarray([[d, c], [b, a]], dtype=float)
    rc_offset = np.asarray([ty, tx], dtype=float)
    return np.asarray(
        ndimage.affine_transform(
            arr,
            rc_matrix,
            offset=rc_offset,
            output_shape=arr.shape,
            order=int(order),
            mode="constant",
            cval=float(cval),
            prefilter=(int(order) > 1),
        ),
        dtype=float,
    )


def symmetrize_qpi(qpi: Any, order: int = 4, center: Sequence[float] | None = None, nan_policy: str = "ignore") -> np.ndarray:
    arr = np.asarray(qpi, dtype=float)
    try:
        n = int(order)
    except Exception:
        n = 1
    if n <= 1:
        return np.array(arr, copy=True)
    if n not in (2, 3, 4, 6):
        raise ValueError("Symmetry order must be one of 2, 3, 4, or 6.")

    if arr.ndim == 2:
        layers = [arr]
        was_2d = True
    elif arr.ndim == 3:
        layers = [arr[:, :, idx] for idx in range(arr.shape[2])]
        was_2d = False
    else:
        raise ValueError("QPI symmetry expects a 2D image or 3D stack.")

    out_layers: list[np.ndarray] = []
    ignore_nan = str(nan_policy or "ignore").strip().lower() == "ignore"
    for layer in layers:
        copies = []
        for i in range(n):
            copies.append(_rotate_image_xy(layer, 360.0 * i / float(n), center_xy=center, order=1, cval=np.nan))
        stack = np.stack(copies, axis=0)
        if ignore_nan:
            valid = np.isfinite(stack)
            count = np.sum(valid, axis=0)
            summed = np.nansum(stack, axis=0)
            avg = np.divide(summed, count, out=np.full_like(summed, np.nan, dtype=float), where=count > 0)
            avg = np.nan_to_num(avg, nan=0.0, posinf=0.0, neginf=0.0)
        else:
            avg = np.nanmean(np.nan_to_num(stack, nan=0.0, posinf=0.0, neginf=0.0), axis=0)
        out_layers.append(avg)

    if was_2d:
        return np.ascontiguousarray(out_layers[0], dtype=float)
    return np.ascontiguousarray(np.stack(out_layers, axis=2), dtype=float)


def run_qpi_symmetry(qpi: Any, order: int = 4, center: Sequence[float] | None = None, nan_policy: str = "ignore") -> dict[str, Any]:
    sym = symmetrize_qpi(qpi, order=order, center=center, nan_policy=nan_policy)
    return {
        "symmetrized_qpi": sym,
        "algorithm": qpi_algorithm("analystm.qpi.symmetrize_qpi", source_mapping=QPI_SYMMETRY_SOURCE_MAPPING),
        "parameters": {
            "order": int(order),
            "center_px": [float(center[0]), float(center[1])] if center is not None else [],
            "nan_policy": str(nan_policy or "ignore"),
        },
        "summary": {
            "shape": [int(v) for v in np.asarray(sym).shape],
            "finite_count": int(np.count_nonzero(np.isfinite(sym))),
        },
    }


def _normalize_bias_for_stack(bias: Sequence[float] | None, nz: int) -> np.ndarray:
    b = np.asarray(bias, dtype=float).ravel() if bias is not None else np.array([], dtype=float)
    if b.size != int(nz):
        if b.size >= 2:
            b = np.linspace(float(b[0]), float(b[-1]), int(nz), dtype=float)
        else:
            b = np.arange(int(nz), dtype=float)
    return b


def compute_pr_qpi_volume(
    grid_data: Any,
    bias: Sequence[float] | None,
    *,
    slider_min: int,
    slider_max: int,
    is_multi_impurity: bool = False,
    window_name: str = "Hanning",
    mask_dc: bool = True,
    mask_radius_px: float = 1.5,
    scale_mode: str = "Signed Sqrt",
) -> dict[str, Any]:
    data = np.asarray(grid_data, dtype=float)
    if data.ndim != 3:
        raise ValueError(f"expected 3D data, got ndim={data.ndim}")

    ny, nx, nz = data.shape
    s_min = int(np.clip(int(slider_min), 0, max(0, nz - 1)))
    s_max = int(np.clip(int(slider_max), s_min, max(0, nz - 1)))
    b = _normalize_bias_for_stack(bias, nz)

    fft_stack = np.zeros((ny, nx, nz), dtype=np.complex64)
    win_name = canonical_fft_window_name(window_name)
    w2d = np.asarray(fft_window_2d((ny, nx), win_name), dtype=float) if win_name and win_name != "none" else None

    for i in range(nz):
        layer = np.asarray(data[:, :, i], dtype=float)
        mean_val = float(np.nanmean(layer))
        if not np.isfinite(mean_val):
            mean_val = 0.0
        layer = np.nan_to_num(layer - mean_val, nan=0.0, posinf=0.0, neginf=0.0)
        if w2d is not None:
            layer = layer * w2d
        fft_stack[:, :, i] = np.fft.fftshift(np.fft.fft2(layer))

    pos_indices = np.arange(s_min, s_max + 1, dtype=int)
    if pos_indices.size <= 0:
        raise ValueError("invalid slider range: no positive-energy indices selected")
    neg_indices = np.abs(b[:, None] - (-b[pos_indices])[None, :]).argmin(axis=0).astype(int, copy=False)

    num_pos = int(pos_indices.size)
    nrows, ncols = fft_stack.shape[:2]
    pr_3d_pos = np.zeros((nrows, ncols, num_pos), dtype=np.float32)
    pr_3d_neg = np.zeros((nrows, ncols, num_pos), dtype=np.float32)

    for k, idx_pos in enumerate(pos_indices):
        idx_neg = int(neg_indices[k])
        g_pos = fft_stack[:, :, idx_pos]
        g_neg = fft_stack[:, :, idx_neg]

        res_pos = np.abs(g_pos).astype(np.float64, copy=False)
        if not is_multi_impurity:
            abs_neg = np.abs(g_neg)
            delta_theta = np.angle(g_neg) - np.angle(g_pos)
            res_neg = abs_neg * np.cos(delta_theta)
        else:
            denom_abs = np.abs(g_pos)
            max_den = float(np.max(denom_abs)) if denom_abs.size else 0.0
            if max_den <= 0.0:
                mask_zero = np.ones_like(denom_abs, dtype=bool)
                res_neg = np.zeros_like(denom_abs, dtype=float)
            else:
                mask_zero = denom_abs < (1e-12 * max_den)
                eps_rel = 1e-6
                eps_floor = max(1e-12 * max_den, np.finfo(float).eps * max_den)
                eps_map = np.maximum(eps_floor, eps_rel * denom_abs)
                phase = np.exp(1j * np.angle(g_pos + 1e-30))
                denom_safe = g_pos + phase * eps_map
                with np.errstate(divide="ignore", invalid="ignore"):
                    z_ratio = g_neg / denom_safe
                res_neg = np.real(z_ratio) * denom_abs
            res_neg[mask_zero] = 0.0

        for arr in (res_pos, res_neg):
            if mask_dc:
                arr[:] = np.asarray(apply_fft_dc_mask(arr, radius_px=mask_radius_px, copy=True), dtype=float)
            if "Sqrt" in str(scale_mode):
                arr[:] = np.sign(arr) * np.sqrt(np.abs(arr))
            elif "Log" in str(scale_mode):
                arr[:] = np.sign(arr) * np.log10(np.abs(arr) + 1e-12)

        pr_3d_pos[:, :, k] = res_pos.astype(np.float32, copy=False)
        pr_3d_neg[:, :, k] = res_neg.astype(np.float32, copy=False)

    return {
        "fft_stack": fft_stack,
        "pr_qpi_pos": pr_3d_pos,
        "pr_qpi_neg": pr_3d_neg,
        "bias": b,
        "positive_indices": pos_indices,
        "negative_indices": neg_indices,
        "positive_bias_mV": b[pos_indices],
        "negative_bias_mV": b[neg_indices],
        "algorithm": qpi_algorithm("analystm.qpi.compute_pr_qpi_volume", source_mapping=PR_QPI_SOURCE_MAPPING),
        "parameters": {
            "slider_min": int(s_min),
            "slider_max": int(s_max),
            "is_multi_impurity": bool(is_multi_impurity),
            "window_name": str(window_name),
            "mask_dc": bool(mask_dc),
            "mask_radius_px": float(mask_radius_px),
            "scale_mode": str(scale_mode),
        },
        "summary": {
            "shape_yx": [int(ny), int(nx)],
            "n_bias": int(nz),
            "n_positive_bias": int(num_pos),
            "positive_bias_min_mV": float(np.nanmin(b[pos_indices])) if pos_indices.size else np.nan,
            "positive_bias_max_mV": float(np.nanmax(b[pos_indices])) if pos_indices.size else np.nan,
        },
    }


def _fft2c(z: Any) -> np.ndarray:
    return np.fft.fftshift(np.fft.fft2(z))


def _ifft2c(z: Any) -> np.ndarray:
    return np.fft.ifft2(np.fft.ifftshift(z))


def _detrend_plane(image_2d: Any) -> np.ndarray:
    arr = np.asarray(image_2d, dtype=float)
    if arr.ndim != 2:
        return arr
    ny, nx = arr.shape
    yy, xx = np.mgrid[0:ny, 0:nx]
    a = np.c_[xx.ravel(), yy.ravel(), np.ones(nx * ny)]
    c, _, _, _ = np.linalg.lstsq(a, arr.ravel(), rcond=None)
    plane = c[0] * xx + c[1] * yy + c[2]
    return np.asarray(arr - plane, dtype=float)


def apply_real_phase_background_mode(image_2d: Any, mode: str) -> np.ndarray:
    data = np.array(np.asarray(image_2d, dtype=float), copy=True)
    if data.ndim != 2 or data.size == 0:
        return data

    mode = str(mode or "Raw").strip()
    ny, nx = data.shape
    if mode == "Sub Global Mean":
        data -= np.mean(data)
    elif mode == "Sub Line Mean (0-order)":
        data -= np.mean(data, axis=1, keepdims=True)
    elif mode == "Sub Line Mean (Row+Col)":
        data -= np.mean(data, axis=1, keepdims=True)
        data -= np.mean(data, axis=0, keepdims=True)
    elif mode == "Sub Line Linear (1-order)":
        x = np.arange(nx, dtype=float)
        for i in range(ny):
            coeff = np.polyfit(x, data[i], 1)
            data[i] -= np.polyval(coeff, x)
    elif mode == "Sub Plane (Global)":
        data = _detrend_plane(data)
    elif mode == "Sub Parabolic (Global)":
        xg, yg = np.meshgrid(np.arange(nx, dtype=float), np.arange(ny, dtype=float))
        xf = xg.ravel()
        yf = yg.ravel()
        a = np.c_[xf**2, yf**2, xf * yf, xf, yf, np.ones(xf.size)]
        coeff, _, _, _ = np.linalg.lstsq(a, data.ravel(), rcond=None)
        data -= coeff[0] * xg**2 + coeff[1] * yg**2 + coeff[2] * xg * yg + coeff[3] * xg + coeff[4] * yg + coeff[5]
    elif mode == "Differentiate (X-deriv)":
        data = np.gradient(data, axis=1)
    return np.asarray(data, dtype=float)


def real_phase_lockin(
    image: Any,
    q_px: Sequence[float],
    sigma_px: float = 3.0,
    return_unwrapped: bool = False,
    window: str = "none",
    fast_preview: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    layer = np.asarray(image, dtype=float)
    if layer.ndim != 2:
        raise ValueError("lockin_phase expects a 2D image")

    h, w = layer.shape
    baseline = float(np.nanmean(layer))
    if not np.isfinite(baseline):
        baseline = 0.0
    z = np.nan_to_num(layer, nan=baseline, posinf=baseline, neginf=baseline)
    win_name = canonical_fft_window_name(window)
    if win_name and win_name != "none":
        z = (z - baseline) * np.asarray(fft_window_2d((h, w), win_name), dtype=float)

    cy, cx = (h - 1) / 2.0, (w - 1) / 2.0
    py, px = float(q_px[0]), float(q_px[1])
    qy = 2.0 * np.pi * (py - cy) / float(h)
    qx = 2.0 * np.pi * (px - cx) / float(w)

    yy, xx = np.mgrid[0:h, 0:w]
    z_dem = z * np.exp(-1j * (qy * yy + qx * xx))

    pad_y, pad_x = max(1, h // 2), max(1, w // 2)
    z_pad = np.pad(z_dem, ((pad_y, pad_y), (pad_x, pad_x)), mode="wrap")
    f = _fft2c(z_pad)

    fh, fw = f.shape
    fcy, fcx = (fh - 1) / 2.0, (fw - 1) / 2.0
    yyf, xxf = np.mgrid[0:fh, 0:fw]
    r2 = (yyf - fcy) ** 2 + (xxf - fcx) ** 2
    sigma_eff = max(0.8, float(sigma_px) * 2.0)
    mask = np.exp(-r2 / (2.0 * sigma_eff**2))

    z_filt = _ifft2c(f * mask)
    z_out = z_filt[pad_y : pad_y + h, pad_x : pad_x + w]

    amp = np.abs(z_out)
    phi_wrapped = np.angle(z_out)
    if fast_preview:
        phi_unwrapped = phi_wrapped
    else:
        phi_unwrapped = unwrap_phase_2d(phi_wrapped)

    reconstructed = amp * np.cos(qy * yy + qx * xx + phi_unwrapped)

    if return_unwrapped:
        return amp, phi_wrapped, reconstructed
    return amp, phi_unwrapped, reconstructed


def compute_real_phase_pll(
    reference_image: Any,
    target_image: Any,
    *,
    q1_yx: Sequence[float],
    q2_yx: Sequence[float],
    sigma_px: float = 3.0,
    window: str = "none",
    detrend_target: bool = False,
) -> dict[str, Any]:
    ref_img = np.asarray(reference_image, dtype=float)
    tar_img = np.asarray(target_image, dtype=float)
    if ref_img.shape != tar_img.shape:
        raise ValueError("reference and target images must have matching shape")
    if ref_img.ndim != 2:
        raise ValueError("real phase p_LL expects 2D images")
    if detrend_target:
        tar_img = _detrend_plane(tar_img)

    amp_ref1, phi_ref1, _ = real_phase_lockin(ref_img, q1_yx, sigma_px=sigma_px, return_unwrapped=True, window=window)
    amp_ref2, phi_ref2, _ = real_phase_lockin(ref_img, q2_yx, sigma_px=sigma_px, return_unwrapped=True, window=window)
    amp_tar1, phi_tar1, _ = real_phase_lockin(tar_img, q1_yx, sigma_px=sigma_px, return_unwrapped=True, window=window)
    amp_tar2, phi_tar2, _ = real_phase_lockin(tar_img, q2_yx, sigma_px=sigma_px, return_unwrapped=True, window=window)

    delta1 = wrap_pi(phi_tar1 - phi_ref1)
    delta2 = wrap_pi(phi_tar2 - phi_ref2)
    pll = (np.abs(delta1) - np.abs(delta2)) / np.pi
    q1 = np.asarray(q1_yx, dtype=float)
    q2 = np.asarray(q2_yx, dtype=float)
    denom = float(np.linalg.norm(q1) * np.linalg.norm(q2))
    angle = np.nan
    if denom > 0:
        angle = float(np.degrees(np.arccos(np.clip(float(np.dot(q1, q2)) / denom, -1.0, 1.0))))
    finite = pll[np.isfinite(pll)]
    return {
        "pll": np.asarray(pll, dtype=float),
        "delta1": np.asarray(delta1, dtype=float),
        "delta2": np.asarray(delta2, dtype=float),
        "amp_ref1": np.asarray(amp_ref1, dtype=float),
        "amp_ref2": np.asarray(amp_ref2, dtype=float),
        "amp_tar1": np.asarray(amp_tar1, dtype=float),
        "amp_tar2": np.asarray(amp_tar2, dtype=float),
        "phi_ref1": np.asarray(phi_ref1, dtype=float),
        "phi_ref2": np.asarray(phi_ref2, dtype=float),
        "phi_tar1": np.asarray(phi_tar1, dtype=float),
        "phi_tar2": np.asarray(phi_tar2, dtype=float),
        "algorithm": qpi_algorithm("analystm.qpi.compute_real_phase_pll", source_mapping=QPI_REAL_PHASE_SOURCE_MAPPING),
        "parameters": {
            "q1_yx": [float(q1[0]), float(q1[1])],
            "q2_yx": [float(q2[0]), float(q2[1])],
            "sigma_px": float(sigma_px),
            "window": str(window),
            "detrend_target": bool(detrend_target),
            "q_angle_deg": angle,
        },
        "summary": {
            "finite_count": int(finite.size),
            "pll_min": float(np.min(finite)) if finite.size else np.nan,
            "pll_max": float(np.max(finite)) if finite.size else np.nan,
            "pll_mean": float(np.mean(finite)) if finite.size else np.nan,
        },
    }
