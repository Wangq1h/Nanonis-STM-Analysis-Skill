from __future__ import annotations

from typing import Any

import numpy as np


def domain_wall_policy(
    regions: list[dict[str, Any]] | None = None,
    allow_agent_proposal: bool = False,
) -> dict[str, Any]:
    """Describe the required DW-region decision path before analysis."""
    if regions:
        return {
            "mode": "user_preapproved_regions",
            "message": "Use the human-specified Domain Wall regions first and record them in provenance.",
        }
    if allow_agent_proposal:
        return {
            "mode": "agent_proposal_allowed",
            "message": "Create an agent-proposed DW mask package, then keep the broad DW and refined on-DW masks separate.",
        }
    return {
        "mode": "ask_user_for_dw_regions",
        "message": "Ask the human to mark Domain Wall regions or explicitly allow an agent proposal before DW analysis.",
    }


def coordinate_grid_yx(
    shape_yx: tuple[int, int],
    scan_size_nm_xy: tuple[float, float],
) -> tuple[np.ndarray, np.ndarray]:
    """Return pixel-center coordinates as x_nm_yx, y_nm_yx arrays."""
    ny, nx = map(int, shape_yx)
    sx_nm, sy_nm = map(float, scan_size_nm_xy)
    if ny <= 0 or nx <= 0:
        raise ValueError("shape_yx must contain positive dimensions")
    if sx_nm <= 0 or sy_nm <= 0:
        raise ValueError("scan_size_nm_xy must contain positive scan sizes")
    x = (np.arange(nx, dtype=float) + 0.5) * sx_nm / nx
    y = (np.arange(ny, dtype=float) + 0.5) * sy_nm / ny
    x_grid, y_grid = np.meshgrid(x, y)
    return x_grid, y_grid


def build_domain_wall_masks(
    shape_yx: tuple[int, int],
    scan_size_nm_xy: tuple[float, float],
    regions: list[dict[str, Any]],
    near_width_nm: float = 0.0,
    edge_exclude_nm: float = 0.0,
    refine_map_yx: Any | None = None,
    refine_percentile: float | None = None,
    refine_mode: str = "above",
) -> dict[str, Any]:
    """Build reusable broad/on/near/away masks from human DW regions."""
    x_grid, y_grid = coordinate_grid_yx(shape_yx, scan_size_nm_xy)
    broad = np.zeros(tuple(map(int, shape_yx)), dtype=bool)
    for region in regions:
        broad |= region_mask(region, x_grid, y_grid)

    valid = _edge_valid_mask(x_grid, y_grid, scan_size_nm_xy, edge_exclude_nm)
    broad_valid = broad & valid
    on_dw = _refine_on_dw_mask(
        broad_valid,
        refine_map_yx=refine_map_yx,
        refine_percentile=refine_percentile,
        refine_mode=refine_mode,
    )
    near = _near_mask_from_broad(broad_valid, scan_size_nm_xy, near_width_nm) & valid
    away = valid & ~broad_valid & ~near

    return {
        "schema_version": 1,
        "x_nm_yx": x_grid,
        "y_nm_yx": y_grid,
        "broad_dw_mask": broad_valid,
        "on_dw_mask": on_dw,
        "near_dw_mask": near,
        "away_mask": away,
        "analysis_mask": valid,
        "counts": {
            "broad_dw": int(np.count_nonzero(broad_valid)),
            "on_dw": int(np.count_nonzero(on_dw)),
            "near_dw": int(np.count_nonzero(near)),
            "away": int(np.count_nonzero(away)),
            "analysis": int(np.count_nonzero(valid)),
        },
        "metadata": {
            "shape_yx": [int(shape_yx[0]), int(shape_yx[1])],
            "scan_size_nm_xy": [float(scan_size_nm_xy[0]), float(scan_size_nm_xy[1])],
            "pixel_size_nm_xy": [float(scan_size_nm_xy[0]) / int(shape_yx[1]), float(scan_size_nm_xy[1]) / int(shape_yx[0])],
            "near_width_nm": float(near_width_nm),
            "edge_exclude_nm": float(edge_exclude_nm),
            "regions": [dict(region) for region in regions],
            "refinement": {
                "enabled": refine_map_yx is not None and refine_percentile is not None,
                "percentile": float(refine_percentile) if refine_percentile is not None else None,
                "mode": str(refine_mode),
                "policy": "away_mask excludes the full broad DW strip even when on_dw_mask is refined.",
            },
        },
    }


def region_mask(region: dict[str, Any], x_grid: np.ndarray, y_grid: np.ndarray) -> np.ndarray:
    """Return a boolean mask for one structured DW region."""
    kind = str(region.get("type", "")).lower()
    if kind == "x_band":
        return (x_grid >= float(region["x_min_nm"])) & (x_grid <= float(region["x_max_nm"]))
    if kind == "y_band":
        return (y_grid >= float(region["y_min_nm"])) & (y_grid <= float(region["y_max_nm"]))
    if kind == "rectangle":
        return (
            (x_grid >= float(region["x_min_nm"]))
            & (x_grid <= float(region["x_max_nm"]))
            & (y_grid >= float(region["y_min_nm"]))
            & (y_grid <= float(region["y_max_nm"]))
        )
    if kind == "circle":
        cx, cy = region["center_nm"]
        radius = float(region["radius_nm"])
        return (x_grid - float(cx)) ** 2 + (y_grid - float(cy)) ** 2 <= radius * radius
    if kind == "polygon":
        return _polygon_mask(x_grid, y_grid, region["vertices_nm"])
    if kind == "line_strip":
        return _line_strip_mask(x_grid, y_grid, region)
    raise ValueError(f"Unsupported Domain Wall region type: {kind!r}")


def region_stats(map_yx: Any, masks: dict[str, Any], denominator_floor: float = 1e-12) -> dict[str, Any]:
    """Summarize a 2D map in DW, near-DW, and away regions."""
    data = np.asarray(map_yx, dtype=float)
    if data.ndim != 2:
        raise ValueError(f"map_yx must be 2D, got shape {data.shape}")
    out: dict[str, Any] = {"schema_version": 1, "regions": {}, "ratios": {}}
    for label, key in (("on_dw", "on_dw_mask"), ("near_dw", "near_dw_mask"), ("away", "away_mask")):
        mask = np.asarray(masks[key], dtype=bool)
        if mask.shape != data.shape:
            raise ValueError(f"{key} shape {mask.shape} does not match map shape {data.shape}")
        out["regions"][label] = _masked_summary(data, mask)

    dw = out["regions"]["on_dw"]
    away = out["regions"]["away"]
    if dw["n"] and away["n"]:
        away_mean = float(away["mean"])
        away_median = float(away["median"])
        out["ratios"]["on_dw_over_away_mean"] = (
            float(dw["mean"]) / away_mean if abs(away_mean) > denominator_floor else None
        )
        out["ratios"]["on_dw_over_away_median"] = (
            float(dw["median"]) / away_median if abs(away_median) > denominator_floor else None
        )
    else:
        out["ratios"]["on_dw_over_away_mean"] = None
        out["ratios"]["on_dw_over_away_median"] = None
    return out


def _edge_valid_mask(
    x_grid: np.ndarray,
    y_grid: np.ndarray,
    scan_size_nm_xy: tuple[float, float],
    edge_exclude_nm: float,
) -> np.ndarray:
    edge = float(edge_exclude_nm)
    if edge <= 0:
        return np.ones(x_grid.shape, dtype=bool)
    sx_nm, sy_nm = map(float, scan_size_nm_xy)
    return (x_grid >= edge) & (x_grid <= sx_nm - edge) & (y_grid >= edge) & (y_grid <= sy_nm - edge)


def _near_mask_from_broad(
    broad_mask: np.ndarray,
    scan_size_nm_xy: tuple[float, float],
    near_width_nm: float,
) -> np.ndarray:
    width = float(near_width_nm)
    if width <= 0 or not np.any(broad_mask):
        return np.zeros(broad_mask.shape, dtype=bool)
    ny, nx = broad_mask.shape
    sx_nm, sy_nm = map(float, scan_size_nm_xy)
    try:
        from scipy.ndimage import distance_transform_edt

        dist = distance_transform_edt(~broad_mask, sampling=(sy_nm / ny, sx_nm / nx))
        return (~broad_mask) & (dist <= width)
    except Exception:
        y_idx, x_idx = np.nonzero(broad_mask)
        yy, xx = np.mgrid[0:ny, 0:nx]
        dx_nm = (xx[..., None] - x_idx) * sx_nm / nx
        dy_nm = (yy[..., None] - y_idx) * sy_nm / ny
        dist = np.sqrt(np.min(dx_nm * dx_nm + dy_nm * dy_nm, axis=2))
        return (~broad_mask) & (dist <= width)


def _refine_on_dw_mask(
    broad_mask: np.ndarray,
    refine_map_yx: Any | None,
    refine_percentile: float | None,
    refine_mode: str,
) -> np.ndarray:
    if refine_map_yx is None or refine_percentile is None:
        return np.array(broad_mask, copy=True)
    data = np.asarray(refine_map_yx, dtype=float)
    if data.shape != broad_mask.shape:
        raise ValueError(f"refine_map_yx shape {data.shape} does not match mask shape {broad_mask.shape}")
    vals = data[broad_mask & np.isfinite(data)]
    if vals.size == 0:
        return np.zeros(broad_mask.shape, dtype=bool)
    threshold = float(np.nanpercentile(vals, float(refine_percentile)))
    mode = str(refine_mode).lower()
    if mode == "above":
        return broad_mask & np.isfinite(data) & (data >= threshold)
    if mode == "below":
        return broad_mask & np.isfinite(data) & (data <= threshold)
    raise ValueError("refine_mode must be 'above' or 'below'")


def _line_strip_mask(x_grid: np.ndarray, y_grid: np.ndarray, region: dict[str, Any]) -> np.ndarray:
    px, py = region["point_nm"]
    width = float(region["width_nm"])
    if width <= 0:
        raise ValueError("line_strip width_nm must be positive")
    if "normal_nm" in region:
        nx, ny = region["normal_nm"]
    elif "normal_xy" in region:
        nx, ny = region["normal_xy"]
    else:
        raise ValueError("line_strip requires normal_nm or normal_xy")
    normal = np.asarray([float(nx), float(ny)], dtype=float)
    norm = float(np.linalg.norm(normal))
    if not np.isfinite(norm) or norm <= 0:
        raise ValueError("line_strip normal must be non-zero")
    normal = normal / norm
    dx = x_grid - float(px)
    dy = y_grid - float(py)
    distance = np.abs(dx * normal[0] + dy * normal[1])
    mask = distance <= 0.5 * width
    if "length_nm" in region:
        tangent = np.asarray([-normal[1], normal[0]], dtype=float)
        along = np.abs(dx * tangent[0] + dy * tangent[1])
        mask &= along <= 0.5 * float(region["length_nm"])
    return mask


def _polygon_mask(x_grid: np.ndarray, y_grid: np.ndarray, vertices: Any) -> np.ndarray:
    pts = [(float(px), float(py)) for px, py in vertices]
    if len(pts) < 3:
        raise ValueError("polygon requires at least three vertices")
    flat_x = x_grid.ravel()
    flat_y = y_grid.ravel()
    inside = np.zeros(flat_x.shape, dtype=bool)
    j = len(pts) - 1
    for i, (xi, yi) in enumerate(pts):
        xj, yj = pts[j]
        crosses = ((yi > flat_y) != (yj > flat_y)) & (
            flat_x < (xj - xi) * (flat_y - yi) / ((yj - yi) or 1e-12) + xi
        )
        inside ^= crosses
        j = i
    return inside.reshape(x_grid.shape)


def _masked_summary(data: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    vals = np.asarray(data[mask], dtype=float)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return {"n": 0, "mean": None, "median": None, "std": None, "min": None, "max": None}
    return {
        "n": int(vals.size),
        "mean": float(np.nanmean(vals)),
        "median": float(np.nanmedian(vals)),
        "std": float(np.nanstd(vals)),
        "min": float(np.nanmin(vals)),
        "max": float(np.nanmax(vals)),
    }
