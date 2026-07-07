from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np


def scale_recommendation(
    shape_yx: tuple[int, int],
    scan_size_nm_xy: tuple[float, float],
    resize_ratio: float | None = None,
    expected_spacing_nm: float | None = None,
    target_inference_pixel_nm: float = 0.026,
) -> dict[str, Any]:
    """Summarize native/inference pixel scale for AtomDetector tuning."""
    ny, nx = map(int, shape_yx)
    sx_nm, sy_nm = map(float, scan_size_nm_xy)
    if ny <= 0 or nx <= 0:
        raise ValueError("shape_yx must contain positive dimensions")
    if sx_nm <= 0 or sy_nm <= 0:
        raise ValueError("scan_size_nm_xy must contain positive values")
    native_x = sx_nm / nx
    native_y = sy_nm / ny
    if resize_ratio is None:
        ratio_x = native_x / float(target_inference_pixel_nm)
        ratio_y = native_y / float(target_inference_pixel_nm)
        resize_ratio = float(np.clip(np.mean([ratio_x, ratio_y]), 1.25, 1.75))
    ratio = float(resize_ratio)
    if ratio <= 0:
        raise ValueError("resize_ratio must be positive")
    inference_x = native_x / ratio
    inference_y = native_y / ratio
    inference_mean = float(np.mean([inference_x, inference_y]))
    if 0.022 <= inference_mean <= 0.031:
        status = "preferred"
    elif 0.018 <= inference_mean <= 0.038:
        status = "acceptable"
    else:
        status = "retune"

    out: dict[str, Any] = {
        "native_pixel_nm_xy": [float(native_x), float(native_y)],
        "resize_ratio": ratio,
        "inference_pixel_nm_xy": [float(inference_x), float(inference_y)],
        "target_inference_pixel_nm": float(target_inference_pixel_nm),
        "scale_status": status,
        "recommended_resize_ratio": ratio if status == "preferred" else float(np.clip(native_x / target_inference_pixel_nm, 1.25, 1.75)),
    }
    if expected_spacing_nm is not None:
        spacing = float(expected_spacing_nm)
        out["expected_spacing_nm"] = spacing
        out["expected_spacing_in_native_px"] = float(spacing / np.mean([native_x, native_y]))
        out["expected_spacing_in_inference_px"] = float(spacing / inference_mean)
    return out


def _pairwise_nearest(coords: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if coords.shape[0] < 2:
        return np.array([], dtype=float), np.empty((0, 2), dtype=float)
    try:
        from scipy.spatial import cKDTree

        tree = cKDTree(coords)
        distances, indices = tree.query(coords, k=min(8, coords.shape[0]))
        nn = np.asarray(distances[:, 1], dtype=float)
        shell_vectors = []
        for row_idx, row in enumerate(indices):
            for neighbor_idx in row[1:]:
                vec = coords[int(neighbor_idx)] - coords[row_idx]
                shell_vectors.append(vec)
        return nn, np.asarray(shell_vectors, dtype=float)
    except Exception:
        diffs = coords[:, None, :] - coords[None, :, :]
        dist = np.sqrt(np.sum(diffs * diffs, axis=2))
        np.fill_diagonal(dist, np.inf)
        nn = np.min(dist, axis=1)
        nearest = np.argsort(dist, axis=1)[:, : min(7, max(1, coords.shape[0] - 1))]
        shell_vectors = []
        for row_idx, row in enumerate(nearest):
            for neighbor_idx in row:
                shell_vectors.append(coords[int(neighbor_idx)] - coords[row_idx])
        return nn, np.asarray(shell_vectors, dtype=float)


def lattice_qc(
    coords_nm: Any,
    expected_spacing_nm: float | None = None,
    bounds_nm_xy: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Check whether detected atom sites resemble an orderly square lattice."""
    coords = np.asarray(coords_nm, dtype=float)
    if coords.ndim != 2 or coords.shape[1] != 2:
        raise ValueError("coords_nm must be an N x 2 array of x_nm,y_nm")
    coords = coords[np.all(np.isfinite(coords), axis=1)]
    n = int(coords.shape[0])
    if n < 4:
        return {
            "n_atoms": n,
            "passes": False,
            "recommend_reparameterize": True,
            "recommendation": "Too few atoms; adjust AtomDetector parameters or input map.",
        }

    nn, shell_vectors = _pairwise_nearest(coords)
    finite_nn = nn[np.isfinite(nn)]
    spacing = float(expected_spacing_nm) if expected_spacing_nm else float(np.nanmedian(finite_nn))
    duplicate_fraction = float(np.mean(finite_nn < 0.65 * spacing)) if finite_nn.size else 1.0
    vacancy_fraction = float(np.mean(finite_nn > 1.45 * spacing)) if finite_nn.size else 1.0
    p10 = float(np.nanpercentile(finite_nn, 10)) if finite_nn.size else None
    p90 = float(np.nanpercentile(finite_nn, 90)) if finite_nn.size else None
    spread_ratio = float(p90 / p10) if p10 and p10 > 0 and p90 else None

    vecs = np.asarray(shell_vectors, dtype=float)
    if vecs.size:
        lengths = np.sqrt(np.sum(vecs * vecs, axis=1))
        shell = vecs[(lengths >= 0.75 * spacing) & (lengths <= 1.35 * spacing)]
    else:
        shell = np.empty((0, 2), dtype=float)
    if shell.shape[0]:
        theta = np.arctan2(shell[:, 1], shell[:, 0])
        fourfold_order = float(np.abs(np.mean(np.exp(4j * theta))))
    else:
        fourfold_order = 0.0

    neighbor_count_ok_fraction = _neighbor_count_ok_fraction(coords, spacing, bounds_nm_xy=bounds_nm_xy)
    passes = (
        duplicate_fraction <= 0.02
        and vacancy_fraction <= 0.05
        and (spread_ratio is not None and spread_ratio <= 1.45)
        and fourfold_order >= 0.70
        and neighbor_count_ok_fraction >= 0.70
    )
    reasons: list[str] = []
    if duplicate_fraction > 0.02:
        reasons.append("duplicate-like close detections")
    if vacancy_fraction > 0.05:
        reasons.append("vacancy-like large nearest-neighbor gaps")
    if spread_ratio is None or spread_ratio > 1.45:
        reasons.append("broad nearest-neighbor spacing distribution")
    if fourfold_order < 0.70:
        reasons.append("weak square-lattice fourfold order")
    if neighbor_count_ok_fraction < 0.70:
        reasons.append("too few atoms have square-lattice neighbor counts")
    recommendation = (
        "Lattice QC passed; keep the current AI parameters."
        if passes
        else "Lattice QC failed; adjust resize_ratio, min_dist, and prob_threshold, then rerun AI detection."
    )
    return {
        "n_atoms": n,
        "expected_spacing_nm": spacing,
        "nearest_neighbor_nm_median": float(np.nanmedian(finite_nn)) if finite_nn.size else None,
        "nearest_neighbor_nm_p10": p10,
        "nearest_neighbor_nm_p90": p90,
        "nearest_neighbor_spread_p90_over_p10": spread_ratio,
        "duplicate_like_fraction": duplicate_fraction,
        "vacancy_like_fraction": vacancy_fraction,
        "fourfold_order": fourfold_order,
        "neighbor_count_ok_fraction": neighbor_count_ok_fraction,
        "passes": bool(passes),
        "recommend_reparameterize": not bool(passes),
        "failed_reasons": reasons,
        "recommendation": recommendation,
    }


def _neighbor_count_ok_fraction(
    coords: np.ndarray,
    spacing: float,
    bounds_nm_xy: tuple[float, float] | None = None,
) -> float:
    if coords.shape[0] < 4:
        return 0.0
    try:
        from scipy.spatial import cKDTree

        tree = cKDTree(coords)
        neighbor_lists = tree.query_ball_point(coords, r=1.35 * spacing)
        counts = np.array([len(items) - 1 for items in neighbor_lists], dtype=int)
    except Exception:
        diffs = coords[:, None, :] - coords[None, :, :]
        dist = np.sqrt(np.sum(diffs * diffs, axis=2))
        counts = np.sum((dist > 0) & (dist <= 1.35 * spacing), axis=1)
    if bounds_nm_xy is None:
        x_min, y_min = np.min(coords, axis=0)
        x_max, y_max = np.max(coords, axis=0)
    else:
        x_min, y_min = 0.0, 0.0
        x_max, y_max = map(float, bounds_nm_xy)
    margin = 1.6 * spacing
    interior = (
        (coords[:, 0] > x_min + margin)
        & (coords[:, 0] < x_max - margin)
        & (coords[:, 1] > y_min + margin)
        & (coords[:, 1] < y_max - margin)
    )
    if not np.any(interior):
        interior = np.ones(coords.shape[0], dtype=bool)
    ok = (counts[interior] >= 3) & (counts[interior] <= 5)
    return float(np.mean(ok)) if ok.size else 0.0


def apply_wipe_regions(
    atom_rows: Iterable[dict[str, Any]],
    regions: list[dict[str, Any]],
    class_key: str = "class",
    output_key: str = "analysis_class",
    wipe_prefix: str = "excluded",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply human-specified wipe regions without changing remaining AI labels."""
    out: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for row in atom_rows:
        new_row = dict(row)
        x = _row_float(new_row, "x_nm")
        y = _row_float(new_row, "y_nm")
        matched = None
        for region in regions:
            if _region_contains(region, x, y):
                matched = str(region.get("label") or region.get("type") or "user")
                break
        if matched:
            label = f"{wipe_prefix}_{_safe_label(matched)}"
            new_row[output_key] = label
            new_row["excluded_reason"] = matched
            counts[matched] = counts.get(matched, 0) + 1
        else:
            new_row[output_key] = new_row.get(class_key, "")
            new_row["excluded_reason"] = ""
        out.append(new_row)
    return out, {
        "total_atoms": len(out),
        "wiped_count": int(sum(counts.values())),
        "wiped_by_region": counts,
        "output_key": output_key,
    }


def _row_float(row: dict[str, Any], key: str) -> float:
    if key not in row:
        raise KeyError(f"atom row is missing {key}")
    return float(row[key])


def _safe_label(text: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(text)).strip("_") or "user"


def _region_contains(region: dict[str, Any], x: float, y: float) -> bool:
    kind = str(region.get("type", "")).lower()
    if kind == "x_band":
        return float(region["x_min_nm"]) <= x <= float(region["x_max_nm"])
    if kind == "y_band":
        return float(region["y_min_nm"]) <= y <= float(region["y_max_nm"])
    if kind == "rectangle":
        return (
            float(region["x_min_nm"]) <= x <= float(region["x_max_nm"])
            and float(region["y_min_nm"]) <= y <= float(region["y_max_nm"])
        )
    if kind == "circle":
        cx, cy = region["center_nm"]
        radius = float(region["radius_nm"])
        return (x - float(cx)) ** 2 + (y - float(cy)) ** 2 <= radius * radius
    if kind == "polygon":
        return _point_in_polygon(x, y, region["vertices_nm"])
    raise ValueError(f"Unsupported wipe region type: {kind!r}")


def _point_in_polygon(x: float, y: float, vertices: Any) -> bool:
    pts = [(float(px), float(py)) for px, py in vertices]
    inside = False
    j = len(pts) - 1
    for i, (xi, yi) in enumerate(pts):
        xj, yj = pts[j]
        intersects = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi)
        if intersects:
            inside = not inside
        j = i
    return inside
