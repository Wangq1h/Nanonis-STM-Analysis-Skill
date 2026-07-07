from __future__ import annotations

from typing import Any, Sequence

import numpy as np


PATH_VIZ_SOURCE_MAPPING = (
    "usefultools_path_viz.SurfaceSurveyPathVizWindow._pending_segments, "
    "_all_points_for_view, confirm_pending_steps, _autoscale_fit, _autoscale_origin, "
    "export_table_excel, _redistribute_overflow"
)


def path_viz_algorithm(engine: str = "analystm.path_viz.build_path_from_batches") -> dict[str, str]:
    return {
        "name": "AnalySTM surface survey path backend",
        "engine": engine,
        "pysidam_source_mapping": PATH_VIZ_SOURCE_MAPPING,
    }


def move_delta(direction: str, steps: int | float) -> tuple[float, float, str]:
    count = int(steps)
    if count <= 0:
        raise ValueError("Steps XY must be > 0.")
    dx = dy = 0
    text = str(direction)
    if text == "+Y":
        dy = count
    elif text == "-Y":
        dy = -count
    elif text == "-X":
        dx = -count
    elif text == "+X":
        dx = count
    else:
        raise ValueError(f"unknown path direction: {direction}")
    return float(dx), float(dy), f"{text} {count}"


def pending_segments(points: Sequence[Sequence[float]], pending_moves: Sequence[dict[str, Any]]) -> list[tuple[tuple[float, float], tuple[float, float], str]]:
    if not points:
        raise ValueError("path requires at least one point")
    x, y = float(points[-1][0]), float(points[-1][1])
    segments: list[tuple[tuple[float, float], tuple[float, float], str]] = []
    for move in pending_moves:
        nx = x + float(move["dx"])
        ny = y + float(move["dy"])
        segments.append(((x, y), (nx, ny), str(move.get("label", ""))))
        x, y = nx, ny
    return segments


def all_points_for_view(points: Sequence[Sequence[float]], pending_moves: Sequence[dict[str, Any]] | None = None) -> list[tuple[float, float]]:
    pts = [(float(p[0]), float(p[1])) for p in points]
    for _p0, p1, _label in pending_segments(pts, pending_moves or []):
        pts.append(p1)
    return pts


def confirm_pending_steps(
    points: Sequence[Sequence[float]],
    steps: Sequence[dict[str, Any]],
    pending_moves_in: Sequence[dict[str, Any]],
    *,
    z_steps: int,
    mark: str = "None",
) -> tuple[list[tuple[float, float]], list[dict[str, Any]]]:
    z = int(z_steps)
    if z <= 0:
        raise ValueError("Steps +Z must be > 0.")
    segments = pending_segments(points, pending_moves_in)
    if not segments:
        return [(float(p[0]), float(p[1])) for p in points], [dict(s) for s in steps]
    x0, y0 = segments[0][0]
    x1, y1 = segments[-1][1]
    move_label = " -> ".join(str(mv.get("label", "")) for mv in pending_moves_in if mv.get("label"))
    out_points = [(float(p[0]), float(p[1])) for p in points]
    for _p0, p1, _label in segments:
        out_points.append(p1)
    out_steps = [dict(s) for s in steps]
    out_steps.append(
        {
            "z": int(z),
            "p0": (float(x0), float(y0)),
            "p1": (float(x1), float(y1)),
            "segments": [(p0, p1) for p0, p1, _label in segments],
            "n_points_added": len(segments),
            "move": move_label,
            "mark": str(mark or "None"),
        }
    )
    return out_points, out_steps


def build_path_from_batches(batches: Sequence[dict[str, Any]], *, start: Sequence[float] = (0.0, 0.0)) -> dict[str, Any]:
    points: list[tuple[float, float]] = [(float(start[0]), float(start[1]))]
    steps_log: list[dict[str, Any]] = []
    for batch in batches:
        moves = []
        for item in batch.get("moves", []):
            direction, count = item[0], item[1]
            dx, dy, label = move_delta(direction, count)
            moves.append({"dx": dx, "dy": dy, "label": label})
        points, steps_log = confirm_pending_steps(points, steps_log, moves, z_steps=int(batch.get("z", 0)), mark=str(batch.get("mark", "None")))
    return {
        "points": points,
        "steps": steps_log,
        "algorithm": path_viz_algorithm(),
        "summary": {"point_count": int(len(points)), "step_count": int(len(steps_log))},
    }


def autoscale_bounds(points: Sequence[Sequence[float]], *, mode: str = "fit") -> dict[str, tuple[float, float]]:
    pts = [(float(p[0]), float(p[1])) for p in points]
    if not pts:
        pts = [(0.0, 0.0)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if str(mode or "fit").strip().lower() == "origin":
        max_extent = max(max(abs(min(xs)), abs(max(xs))), max(abs(min(ys)), abs(max(ys))), 1.0)
        half = max_extent * 1.2
        return {"xlim": (-float(half), float(half)), "ylim": (-float(half), float(half))}
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if min_x == max_x:
        min_x -= 1.0
        max_x += 1.0
    if min_y == max_y:
        min_y -= 1.0
        max_y += 1.0
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0
    span = max(max_x - min_x, max_y - min_y) * 1.2
    half = span / 2.0
    return {"xlim": (float(cx - half), float(cx + half)), "ylim": (float(cy - half), float(cy + half))}


def path_log_rows(steps: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, step in enumerate(steps):
        x1, y1 = step.get("p1", (0.0, 0.0))
        rows.append(
            {
                "#": str(idx),
                "Move": str(step.get("move", "")),
                "+Z": str(int(step.get("z", 0))),
                "End (x,y)": f"({float(x1):.2f}, {float(y1):.2f})",
                "Arrived": str(step.get("arrived", "")),
                "Current": str(step.get("current", "")),
                "Mark": str(step.get("mark", "None")),
            }
        )
    return rows


def redistribute_overflow(widths: Sequence[int], overflow: int, excluded_col: int) -> list[int]:
    out = [int(w) for w in widths]
    targets = [i for i in range(len(out)) if i != int(excluded_col)]
    if not targets or int(overflow) <= 0:
        return out
    base = sum(max(1, out[i]) for i in targets)
    distributed = 0
    for i in targets[:-1]:
        add = int(round(int(overflow) * (max(1, out[i]) / float(base))))
        out[i] += add
        distributed += add
    out[targets[-1]] += max(0, int(overflow) - distributed)
    return out
