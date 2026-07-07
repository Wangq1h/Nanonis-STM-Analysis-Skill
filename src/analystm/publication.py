from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np


EDITOR_MAX_IMAGE_PIXELS = 700_000
EDITOR_MAX_IMAGE_DIM = 1800
EDITOR_MAX_LINE_POINTS = 8000

PUBLICATION_SOURCE_MAPPING = (
    "publication_editor.ImagePayload, LinePayload, FigurePayload, AnnotationPayload, "
    "_regularize_image_extent, _image_shape_score, _axis_centers_from_extent, "
    "_thin_line_points, _downsample_image_for_editor, _degenerate_image_as_line, "
    "_payload_data_limits, _line_payload_limits, _filter_inset_images_from_payload, "
    "PublicationFigureWindow._nice_length, _suggest_scalebar_length, _apply_image_contrast"
)


def publication_algorithm(engine: str = "analystm.publication.payload_summary") -> dict[str, str]:
    return {
        "name": "AnalySTM publication payload backend",
        "engine": engine,
        "pysidam_source_mapping": PUBLICATION_SOURCE_MAPPING,
    }


@dataclass
class ImagePayload:
    data: np.ndarray
    extent: tuple | None = None
    cmap: str = "viridis"
    vmin: float | None = None
    vmax: float | None = None
    interpolation: str = "nearest"


@dataclass
class LinePayload:
    x: np.ndarray
    y: np.ndarray
    label: str
    style: dict = field(default_factory=dict)


@dataclass
class FigurePayload:
    title: str = ""
    xlabel: str = ""
    ylabel: str = ""
    xlim: tuple | None = None
    ylim: tuple | None = None
    images: list = field(default_factory=list)
    lines: list = field(default_factory=list)


@dataclass
class AnnotationPayload:
    text: str = ""
    visible: bool = False
    x: float = 5.0
    y: float = 95.0
    font_size: float = 10.0
    halign: str = "left"
    valign: str = "top"
    text_color: str = "#111827"
    text_background: bool = False
    text_bg_color: str = "#f3f4f6"
    text_bg_alpha: float = 0.70
    color: str = "#111827"
    arrow: bool = False
    arrow_color: str = "#111827"
    arrow_start_x: float = 50.0
    arrow_start_y: float = 50.0
    arrow_length: float = 15.0
    arrow_angle: float = 0.0
    arrow_width: float = 1.0
    shape: bool = False
    shape_color: str = "#00bcd4"
    shape_type: str = "circle"
    shape_x: float = 50.0
    shape_y: float = 50.0
    shape_width: float = 6.0
    shape_height: float = 6.0
    shape_angle: float = 0.0
    shape_linewidth: float = 1.8


def regularize_image_extent(data: Any, extent: Sequence[float] | None) -> tuple[float, float, float, float] | None:
    try:
        arr = np.asarray(data)
    except Exception:
        return tuple(extent) if extent is not None else None
    if arr.ndim < 2:
        return tuple(extent) if extent is not None else None
    rows = int(arr.shape[0])
    cols = int(arr.shape[1])
    if rows <= 0 or cols <= 0:
        return tuple(extent) if extent is not None else None
    try:
        x0, x1, y0, y1 = [float(v) for v in extent] if extent is not None else (0.0, float(cols), 0.0, float(rows))
    except Exception:
        x0, x1, y0, y1 = 0.0, float(cols), 0.0, float(rows)
    if not np.all(np.isfinite([x0, x1, y0, y1])):
        x0, x1, y0, y1 = 0.0, float(cols), 0.0, float(rows)
    width = abs(float(x1) - float(x0))
    height = abs(float(y1) - float(y0))
    eps = 1e-12
    if width <= eps:
        cx = 0.5 * (float(x0) + float(x1))
        fallback = float(height / max(rows, 1)) if height > eps else 1.0
        half = max(abs(fallback), 1.0) * 0.5
        x0, x1 = cx - half, cx + half
        width = abs(x1 - x0)
    if height <= eps:
        cy = 0.5 * (float(y0) + float(y1))
        fallback = float(width / max(cols, 1)) if width > eps else 1.0
        half = max(abs(fallback), 1.0) * 0.5
        y0, y1 = cy - half, cy + half
        height = abs(y1 - y0)
    if rows <= 1:
        cy = 0.5 * (float(y0) + float(y1))
        half = max(float(height), float(width / max(cols, 1)), 1.0) * 0.5
        y0, y1 = cy - half, cy + half
    if cols <= 1:
        cx = 0.5 * (float(x0) + float(x1))
        half = max(float(width), float(height / max(rows, 1)), 1.0) * 0.5
        x0, x1 = cx - half, cx + half
    return (float(x0), float(x1), float(y0), float(y1))


def image_shape_score(data: Any, extent: Sequence[float] | None = None) -> float:
    try:
        shape = tuple(np.asarray(data).shape[:2])
    except Exception:
        return -1.0
    if len(shape) < 2:
        return -1.0
    rows, cols = int(shape[0]), int(shape[1])
    if rows <= 0 or cols <= 0:
        return -1.0
    min_dim = min(rows, cols)
    max_dim = max(rows, cols)
    score = float(rows * cols)
    if min_dim <= 2 and max_dim >= 16:
        score -= 1e12
    if max_dim / max(min_dim, 1) > 30:
        score -= 1e9
    if extent is not None:
        try:
            x0, x1, y0, y1 = [float(v) for v in extent]
            ew = abs(x1 - x0)
            eh = abs(y1 - y0)
            if ew > 0 and eh > 0:
                aspect = max(ew / eh, eh / ew)
                if aspect > 30:
                    score -= 1e9
        except Exception:
            pass
    return float(score)


def axis_centers_from_extent(start: float, end: float, count: int) -> np.ndarray:
    count = int(count)
    if count <= 0:
        return np.array([], dtype=float)
    try:
        start = float(start)
        end = float(end)
    except Exception:
        start, end = 0.0, float(count)
    if not np.isfinite(start) or not np.isfinite(end) or start == end:
        start, end = 0.0, float(count)
    step = (end - start) / float(count)
    return start + (np.arange(count, dtype=float) + 0.5) * step


def thin_line_points(x: Any, y: Any, max_points: int = EDITOR_MAX_LINE_POINTS) -> tuple[np.ndarray, np.ndarray]:
    try:
        xx = np.asarray(x, dtype=float).ravel()
        yy = np.asarray(y, dtype=float).ravel()
    except Exception:
        return np.asarray(x), np.asarray(y)
    n = min(int(xx.size), int(yy.size))
    if n <= 0:
        return xx[:0], yy[:0]
    xx = xx[:n]
    yy = yy[:n]
    try:
        max_points = int(max_points)
    except Exception:
        max_points = EDITOR_MAX_LINE_POINTS
    if max_points <= 0 or n <= max_points:
        return xx, yy
    idx = np.linspace(0, n - 1, max_points, dtype=int)
    return xx[idx], yy[idx]


def downsample_image_for_editor(data: Any) -> np.ndarray:
    try:
        arr = np.asarray(data)
    except Exception:
        return data
    if arr.ndim != 2:
        return arr
    rows, cols = arr.shape
    if rows <= 0 or cols <= 0:
        return arr
    total = int(rows) * int(cols)
    if total <= EDITOR_MAX_IMAGE_PIXELS and rows <= EDITOR_MAX_IMAGE_DIM and cols <= EDITOR_MAX_IMAGE_DIM:
        return arr
    scale = max(
        np.sqrt(float(total) / float(EDITOR_MAX_IMAGE_PIXELS)),
        float(rows) / float(EDITOR_MAX_IMAGE_DIM),
        float(cols) / float(EDITOR_MAX_IMAGE_DIM),
        1.0,
    )
    step = max(1, int(np.ceil(scale)))
    return np.ascontiguousarray(arr[::step, ::step])


def degenerate_image_as_line(data: Any, extent: Sequence[float] | None, idx: int = 0) -> tuple[LinePayload | None, str | None]:
    try:
        arr = np.asarray(data, dtype=float)
    except Exception:
        return None, None
    if arr.ndim != 2:
        return None, None
    rows, cols = arr.shape
    if rows <= 0 or cols <= 0 or (rows > 1 and cols > 1) or (rows == 1 and cols == 1):
        return None, None
    try:
        x0, x1, y0, y1 = [float(v) for v in extent] if extent is not None else (0.0, float(cols), 0.0, float(rows))
    except Exception:
        x0, x1, y0, y1 = 0.0, float(cols), 0.0, float(rows)
    if rows == 1:
        x = axis_centers_from_extent(x0, x1, cols)
        y = arr[0, :]
        axis_hint = "x"
    else:
        x = axis_centers_from_extent(y0, y1, rows)
        y = arr[:, 0]
        axis_hint = "y"
    finite = np.isfinite(x) & np.isfinite(y)
    if np.count_nonzero(finite) < 2:
        return None, None
    x, y = thin_line_points(x[finite], y[finite])
    return (
        LinePayload(
            x=x,
            y=y,
            label=f"Image profile {int(idx) + 1}",
            style={"color": "#1565c0", "linewidth": 1.8, "linestyle": "-", "marker": "", "markerfill": "solid", "markersize": 4.5, "alpha": 1.0, "visible": True},
        ),
        axis_hint,
    )


def _limits_with_pad(values: Sequence[float]) -> tuple[float, float] | None:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 2:
        return None
    lo = float(np.nanmin(arr))
    hi = float(np.nanmax(arr))
    if not np.isfinite(lo) or not np.isfinite(hi) or lo == hi:
        return None
    pad = 0.02 * abs(hi - lo)
    return lo - pad, hi + pad


def payload_data_limits(payload: FigurePayload | None) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
    if payload is None:
        return None, None
    x_vals: list[float] = []
    y_vals: list[float] = []
    for image in getattr(payload, "images", []) or []:
        extent = getattr(image, "extent", None)
        if extent is not None and len(extent) == 4:
            try:
                x0, x1, y0, y1 = [float(v) for v in extent]
                if np.all(np.isfinite([x0, x1])) and x0 != x1:
                    x_vals.extend([x0, x1])
                if np.all(np.isfinite([y0, y1])) and y0 != y1:
                    y_vals.extend([y0, y1])
            except Exception:
                pass
        else:
            try:
                arr = np.asarray(image.data)
                if arr.ndim >= 2:
                    y_vals.extend([0.0, float(arr.shape[0])])
                    x_vals.extend([0.0, float(arr.shape[1])])
            except Exception:
                pass
    for line in getattr(payload, "lines", []) or []:
        try:
            x = np.asarray(line.x, dtype=float).ravel()
            y = np.asarray(line.y, dtype=float).ravel()
            mask = np.isfinite(x) & np.isfinite(y)
            if np.count_nonzero(mask) >= 2:
                x_vals.extend([float(np.nanmin(x[mask])), float(np.nanmax(x[mask]))])
                y_vals.extend([float(np.nanmin(y[mask])), float(np.nanmax(y[mask]))])
        except Exception:
            pass
    return _limits_with_pad(x_vals), _limits_with_pad(y_vals)


def line_payload_limits(lines: Sequence[LinePayload]) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
    x_vals: list[float] = []
    y_vals: list[float] = []
    for line in lines or []:
        try:
            x = np.asarray(line.x, dtype=float).ravel()
            y = np.asarray(line.y, dtype=float).ravel()
        except Exception:
            continue
        mask = np.isfinite(x) & np.isfinite(y)
        if np.count_nonzero(mask) < 2:
            continue
        x_vals.extend([float(np.nanmin(x[mask])), float(np.nanmax(x[mask]))])
        y_vals.extend([float(np.nanmin(y[mask])), float(np.nanmax(y[mask]))])

    def _limits(values: Sequence[float]) -> tuple[float, float] | None:
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size < 2:
            return None
        lo = float(np.nanmin(arr))
        hi = float(np.nanmax(arr))
        if not np.isfinite(lo) or not np.isfinite(hi) or hi == lo:
            return None
        return lo, hi

    return _limits(x_vals), _limits(y_vals)


def filter_inset_images_from_payload(payload: FigurePayload | None) -> FigurePayload | None:
    if payload is None or not payload.images or not payload.lines:
        return payload
    line_xlim, line_ylim = line_payload_limits(payload.lines)
    if line_xlim is None or line_ylim is None:
        line_xlim = payload.xlim
        line_ylim = payload.ylim
    try:
        xspan = abs(float(line_xlim[1]) - float(line_xlim[0])) if line_xlim is not None else 0.0
        yspan = abs(float(line_ylim[1]) - float(line_ylim[0])) if line_ylim is not None else 0.0
    except Exception:
        return payload
    if xspan <= 0 or yspan <= 0:
        return payload
    kept = []
    for image in payload.images:
        extent = getattr(image, "extent", None)
        if extent is None or len(extent) != 4:
            kept.append(image)
            continue
        try:
            x0, x1, y0, y1 = [float(v) for v in extent]
        except Exception:
            kept.append(image)
            continue
        img_w = abs(x1 - x0)
        img_h = abs(y1 - y0)
        if not np.isfinite(img_w) or not np.isfinite(img_h) or img_w <= 0 or img_h <= 0:
            kept.append(image)
            continue
        width_ratio = img_w / xspan
        height_ratio = img_h / yspan
        area_ratio = width_ratio * height_ratio
        if area_ratio >= 0.45 or width_ratio >= 0.82 or height_ratio >= 0.82:
            kept.append(image)
    payload.images[:] = kept
    return payload


def nice_length(value: float) -> float:
    try:
        value = abs(float(value))
    except Exception:
        return 1.0
    if (not np.isfinite(value)) or value <= 0:
        return 1.0
    exponent = np.floor(np.log10(value))
    fraction = value / (10.0**exponent)
    if fraction < 1.5:
        nice = 1.0
    elif fraction < 3.5:
        nice = 2.0
    elif fraction < 7.5:
        nice = 5.0
    else:
        nice = 10.0
    return float(nice * (10.0**exponent))


def suggest_scalebar_length(image: ImagePayload | None) -> float:
    if image is None:
        return 10.0
    width = None
    try:
        if image.extent is not None and len(image.extent) == 4:
            width = abs(float(image.extent[1]) - float(image.extent[0]))
    except Exception:
        width = None
    if width is None or (not np.isfinite(width)) or width <= 0:
        try:
            data = np.asarray(image.data)
            if data.ndim >= 2:
                width = float(data.shape[1])
        except Exception:
            width = None
    if width is None or (not np.isfinite(width)) or width <= 0:
        return 10.0
    return nice_length(width * 0.2)


def axis_unit_hint(label: str) -> str:
    text = str(label or "").strip()
    if "(" in text and ")" in text:
        try:
            return text.rsplit("(", 1)[1].split(")", 1)[0].strip()
        except Exception:
            return ""
    return ""


def default_scalebar_label(length: float, xlabel: str = "") -> str:
    unit = axis_unit_hint(xlabel)
    return f"{float(length):.6g} {unit}".strip()


def apply_image_contrast(data: Any, *, mode: str = "full", source_vmin: float | None = None, source_vmax: float | None = None) -> tuple[float, float] | None:
    try:
        arr = np.asarray(data, dtype=float)
    except Exception:
        return None
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return None
    mode_key = str(mode or "").strip().lower()
    if mode_key == "source":
        vmin = source_vmin if source_vmin is not None else float(np.nanmin(finite))
        vmax = source_vmax if source_vmax is not None else float(np.nanmax(finite))
    elif mode_key == "robust":
        vmin = float(np.nanpercentile(finite, 1.0))
        vmax = float(np.nanpercentile(finite, 99.0))
    elif mode_key == "symmetric":
        vmax_abs = float(np.nanmax(np.abs(finite)))
        vmin, vmax = -vmax_abs, vmax_abs
    else:
        vmin = float(np.nanmin(finite))
        vmax = float(np.nanmax(finite))
    if not (np.isfinite(vmin) and np.isfinite(vmax)):
        return None
    if vmin == vmax:
        vmax = vmin + 1e-9
    return float(vmin), float(vmax)


def payload_summary(payload: FigurePayload) -> dict[str, Any]:
    xlim, ylim = payload_data_limits(payload)
    return {
        "image_count": int(len(payload.images)),
        "line_count": int(len(payload.lines)),
        "xlim": list(xlim) if xlim is not None else [],
        "ylim": list(ylim) if ylim is not None else [],
        "algorithm": publication_algorithm(),
    }
