from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import numpy as np


EXPORT_SOURCE_MAPPING = "core.export.write_nanonis_spec_dat and write_nanonis_grid_3ds"


_NANONIS_SPEC_HEADER_DEFAULTS = (
    ("Experiment", "bias spectroscopy"),
    ("Saved Date", ""),
    ("User", ""),
    ("Date", ""),
    ("X (m)", ""),
    ("Y (m)", ""),
    ("Z (m)", ""),
    ("Z offset (m)", ""),
    ("Settling time (s)", ""),
    ("Integration time (s)", ""),
    ("Z-Ctrl hold", ""),
    ("Final Z (m)", ""),
    ("Start time", ""),
    ("Filter type", ""),
    ("Order", ""),
    ("Cutoff frq", ""),
)


def export_algorithm(engine: str) -> dict[str, str]:
    return {"name": "AnalySTM Nanonis export backend", "engine": engine, "pysidam_source_mapping": EXPORT_SOURCE_MAPPING}


def nanonis_timestamp(dt_obj: Any = None) -> str:
    dt_obj = dt_obj if dt_obj is not None else datetime.now()
    return dt_obj.strftime("%d.%m.%Y %H:%M:%S")


def sanitize_nanonis_header_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\r", " ").replace("\n", " ")


def build_nanonis_spec_header(
    header: dict[str, Any] | None = None,
    experiment: str | None = None,
    saved_date: str | None = None,
    extra_comments: Sequence[Any] | None = None,
) -> dict[str, str]:
    source = header if isinstance(header, dict) else {}
    out: dict[str, str] = {}

    for key, default in _NANONIS_SPEC_HEADER_DEFAULTS:
        if key == "Experiment":
            value = experiment if experiment is not None else source.get(key, default)
        elif key == "Saved Date":
            value = saved_date if saved_date is not None else source.get(key, nanonis_timestamp())
        else:
            value = source.get(key, default)
        out[key] = sanitize_nanonis_header_value(value)

    existing_comment_keys: set[str] = set()
    for key, value in source.items():
        key_text = str(key)
        if key_text in out:
            continue
        if key_text.startswith("Comment"):
            existing_comment_keys.add(key_text)
            continue
        out[key_text] = sanitize_nanonis_header_value(value)

    for key, value in source.items():
        key_text = str(key)
        if key_text.startswith("Comment"):
            out[key_text] = sanitize_nanonis_header_value(value)

    existing_comment_indices: set[int] = set()
    for key_text in existing_comment_keys.union({k for k in out if str(k).startswith("Comment")}):
        match = re.fullmatch(r"Comment(\d+)", str(key_text))
        if match:
            existing_comment_indices.add(int(match.group(1)))

    next_comment_idx = 1
    for comment in extra_comments or []:
        text = sanitize_nanonis_header_value(comment).strip()
        if not text:
            continue
        while next_comment_idx in existing_comment_indices:
            next_comment_idx += 1
        out[f"Comment{next_comment_idx:02d}"] = text
        existing_comment_indices.add(next_comment_idx)
        next_comment_idx += 1

    return out


def format_nanonis_data_value(value: Any, precision: int = 7) -> str:
    try:
        val = float(value)
    except Exception:
        return sanitize_nanonis_header_value(value)
    if np.isnan(val):
        return "nan"
    if np.isposinf(val):
        return "inf"
    if np.isneginf(val):
        return "-inf"
    text = f"{val:.{int(max(0, precision))}E}"
    return re.sub(r"E([+-])0*(\d+)$", r"E\1\2", text)


def write_nanonis_spec_dat(
    path: str | Path,
    columns: Sequence[tuple[str, Any]],
    header: dict[str, Any] | None = None,
    extra_comments: Sequence[Any] | None = None,
    experiment: str | None = None,
    saved_date: str | None = None,
    precision: int = 7,
) -> Path:
    if not columns:
        raise ValueError("No columns were provided for .dat export.")

    normalized_columns: list[tuple[str, np.ndarray]] = []
    data_len = None
    for name, data in columns:
        arr = np.asarray(data, dtype=float).ravel()
        if arr.size == 0:
            raise ValueError(f"Column '{name}' is empty.")
        if data_len is None:
            data_len = int(arr.size)
        elif int(arr.size) != data_len:
            raise ValueError("All exported columns must have the same length.")
        normalized_columns.append((sanitize_nanonis_header_value(name), arr))

    header_map = build_nanonis_spec_header(
        header=header,
        experiment=experiment,
        saved_date=saved_date,
        extra_comments=extra_comments,
    )

    lines = [f"{key}\t{value}\t" for key, value in header_map.items()]
    lines.extend(["", "[DATA]", "\t".join(name for name, _ in normalized_columns)])

    for row in zip(*(arr for _, arr in normalized_columns)):
        lines.append("\t".join(format_nanonis_data_value(value, precision=precision) for value in row))

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("\r\n".join(lines) + "\r\n")
    return out_path


def _grid_header_list(value: Any, default_items: Sequence[Any]) -> list[str]:
    if isinstance(value, str):
        items = [part.strip() for part in value.split(";") if str(part).strip()]
        if items:
            return items
    elif isinstance(value, (list, tuple, np.ndarray)):
        items = [str(part).strip() for part in np.asarray(value, dtype=object).ravel() if str(part).strip()]
        if items:
            return items
    return [str(part).strip() for part in default_items if str(part).strip()]


def _grid_header_scalar(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, (list, tuple, np.ndarray)):
        arr = np.asarray(value, dtype=object).ravel()
        if arr.size <= 0:
            return default
        value = arr[0]
    try:
        numeric = float(value)
    except Exception:
        return sanitize_nanonis_header_value(value)
    if not np.isfinite(numeric):
        return default
    return format_nanonis_data_value(numeric, precision=9)


def _grid_header_list_text(values: Sequence[Any]) -> str:
    return ";".join(sanitize_nanonis_header_value(value).strip() for value in values if str(value).strip())


def _grid_header_extra_text(value: Any) -> str | None:
    if value is None or isinstance(value, dict):
        return None
    if isinstance(value, (list, tuple, np.ndarray)):
        arr = np.asarray(value, dtype=object).ravel()
        if arr.size <= 0:
            return None
        return _grid_header_list_text(arr.tolist())
    text = sanitize_nanonis_header_value(value).strip()
    return text or None


def _header_float_value(header: dict[str, Any] | None, keys: Sequence[str], default: float = 0.0) -> float:
    source = header if isinstance(header, dict) else {}
    for key in keys:
        value = source.get(key)
        if value is None:
            continue
        try:
            numeric = float(np.asarray(value).ravel()[0])
        except Exception:
            continue
        if np.isfinite(numeric):
            return float(numeric)
    return float(default)


def _build_synthetic_grid_params(
    nx: int,
    ny: int,
    bias_v: Any,
    header: dict[str, Any] | None = None,
    topo_map: Any = None,
) -> tuple[np.ndarray, list[str], list[str], int]:
    source = header if isinstance(header, dict) else {}
    default_fixed = ["Sweep Start", "Sweep End"]
    default_exp = [
        "X (m)",
        "Y (m)",
        "Z (m)",
        "Z offset (m)",
        "Settling time (s)",
        "Integration time (s)",
        "Z-Ctrl hold",
        "Final Z (m)",
    ]
    fixed_parameters = _grid_header_list(source.get("fixed_parameters"), default_fixed)
    if len(fixed_parameters) < 2:
        fixed_parameters = list(default_fixed)
    experimental_parameters = _grid_header_list(source.get("experimental_parameters"), default_exp)
    try:
        header_num_parameters = int(source.get("num_parameters", 0) or 0)
    except Exception:
        header_num_parameters = 0
    num_parameters = int(max(2, len(fixed_parameters) + len(experimental_parameters), header_num_parameters))
    param_names = list(fixed_parameters) + list(experimental_parameters)
    while len(param_names) < num_parameters:
        param_names.append(f"Extra Param {len(param_names) + 1}")

    size_xy = source.get("size_xy")
    if isinstance(size_xy, (list, tuple, np.ndarray)) and len(size_xy) >= 2:
        sx_m = float(np.asarray(size_xy, dtype=float).ravel()[0])
        sy_m = float(np.asarray(size_xy, dtype=float).ravel()[1])
    else:
        scan_size_nm = _header_float_value(source, ("scan_size_nm",), default=100.0)
        sx_m = sy_m = float(scan_size_nm) * 1e-9
    pos_xy = source.get("pos_xy")
    if isinstance(pos_xy, (list, tuple, np.ndarray)) and len(pos_xy) >= 2:
        px_m = float(np.asarray(pos_xy, dtype=float).ravel()[0])
        py_m = float(np.asarray(pos_xy, dtype=float).ravel()[1])
    else:
        px_m = py_m = 0.0

    x_axis = np.linspace(px_m - 0.5 * sx_m, px_m + 0.5 * sx_m, int(nx), dtype=float) if nx > 1 else np.asarray([px_m], dtype=float)
    y_axis = np.linspace(py_m - 0.5 * sy_m, py_m + 0.5 * sy_m, int(ny), dtype=float) if ny > 1 else np.asarray([py_m], dtype=float)

    topo_internal = None
    if topo_map is not None:
        try:
            topo_arr = np.asarray(topo_map, dtype=float)
        except Exception:
            topo_arr = None
        if topo_arr is not None and topo_arr.shape == (int(nx), int(ny)):
            topo_internal = topo_arr
    if topo_internal is None:
        topo_internal = np.zeros((int(nx), int(ny)), dtype=float)

    params = np.zeros((int(ny), int(nx), int(num_parameters)), dtype=">f4")
    bias_arr = np.asarray(bias_v, dtype=float).ravel()
    sweep_start = float(bias_arr[0]) if bias_arr.size else 0.0
    sweep_end = float(bias_arr[-1]) if bias_arr.size else 0.0
    params[:, :, 0] = sweep_start
    params[:, :, 1] = sweep_end

    x_grid = np.broadcast_to(x_axis.reshape(1, int(nx)), (int(ny), int(nx)))
    y_grid = np.broadcast_to(y_axis.reshape(int(ny), 1), (int(ny), int(nx)))
    topo_grid = np.transpose(np.asarray(topo_internal, dtype=float), (1, 0))
    z_offset = _header_float_value(source, ("z_offset_m", "Z offset (m)"), default=0.0)
    settling = _header_float_value(source, ("measure_delay", "Delay before measuring (s)", "Settling time (s)"), default=0.0)
    integration = _header_float_value(source, ("Integration time (s)",), default=0.0)
    z_hold = _header_float_value(source, ("Z-Ctrl hold",), default=0.0)

    for idx, name in enumerate(param_names[2:], start=2):
        norm = "".join(ch.lower() for ch in str(name) if ch.isalnum())
        if norm in {"xm", "x"}:
            params[:, :, idx] = x_grid
        elif norm in {"ym", "y"}:
            params[:, :, idx] = y_grid
        elif norm in {"zm", "z"}:
            params[:, :, idx] = topo_grid
        elif norm in {"zoffsetm", "zoffset"}:
            params[:, :, idx] = float(z_offset)
        elif norm in {"settlingtimes", "delaybeforemeasurings"}:
            params[:, :, idx] = float(settling)
        elif norm in {"integrationtimes"}:
            params[:, :, idx] = float(integration)
        elif norm in {"zctrlhold"}:
            params[:, :, idx] = float(z_hold)
        elif norm in {"finalzm", "finalz"}:
            params[:, :, idx] = topo_grid

    return params, fixed_parameters, experimental_parameters, int(num_parameters)


def write_nanonis_grid_3ds(
    path: str | Path,
    signals: dict[str, Any],
    header: dict[str, Any] | None = None,
    bias_mV: Any = None,
    scan_size_nm: float | None = None,
    topo_map: Any = None,
) -> Path:
    if not isinstance(signals, dict) or not signals:
        raise ValueError("No signal channels were provided for .3ds export.")

    spectral_channels: list[tuple[str, np.ndarray]] = []
    nx = ny = n_bias = None
    for name, data in signals.items():
        arr = np.asarray(data, dtype=float)
        if arr.ndim != 3 or int(arr.shape[2]) <= 1:
            continue
        if nx is None:
            nx, ny, n_bias = int(arr.shape[0]), int(arr.shape[1]), int(arr.shape[2])
        elif arr.shape != (nx, ny, n_bias):
            raise ValueError("All spectral .3ds channels must share the same (x, y, bias) shape.")
        spectral_channels.append((sanitize_nanonis_header_value(name), np.ascontiguousarray(arr, dtype=float)))
    if not spectral_channels or nx is None or ny is None or n_bias is None:
        raise ValueError("No valid spectral 3D channels were found for .3ds export.")

    header_map = dict(header or {}) if isinstance(header, dict) else {}
    if scan_size_nm is not None and "size_xy" not in header_map:
        try:
            scan_m = float(np.asarray(scan_size_nm).ravel()[0]) * 1e-9
            if np.isfinite(scan_m) and scan_m > 0:
                header_map["size_xy"] = [scan_m, scan_m]
                header_map["scan_size_nm"] = float(np.asarray(scan_size_nm).ravel()[0])
        except Exception:
            pass

    try:
        bias_arr_mV = np.asarray(bias_mV, dtype=float).ravel() if bias_mV is not None else None
    except Exception:
        bias_arr_mV = None
    if bias_arr_mV is None or bias_arr_mV.size <= 0:
        bias_arr_v = np.linspace(-0.5, 0.5, int(n_bias), dtype=float) * 1e-3
    elif bias_arr_mV.size == int(n_bias):
        bias_arr_v = np.asarray(bias_arr_mV, dtype=float) / 1e3
    elif bias_arr_mV.size >= 2:
        bias_arr_v = np.linspace(float(bias_arr_mV[0]), float(bias_arr_mV[-1]), int(n_bias), dtype=float) / 1e3
    else:
        bias_arr_v = np.full(int(n_bias), float(bias_arr_mV[0]) / 1e3, dtype=float)

    topo_internal = np.nanmean(np.asarray(spectral_channels[0][1], dtype=float), axis=2) if topo_map is None else topo_map
    params_raw, fixed_parameters, experimental_parameters, num_parameters = _build_synthetic_grid_params(
        nx=nx,
        ny=ny,
        bias_v=bias_arr_v,
        header=header_map,
        topo_map=topo_internal,
    )

    channel_names = [name for name, _arr in spectral_channels]
    num_channels = int(len(channel_names))
    experiment_size = int(n_bias * num_channels * 4)
    pos_xy_vals = header_map.get("pos_xy")
    if isinstance(pos_xy_vals, (list, tuple, np.ndarray)) and len(pos_xy_vals) >= 2:
        pos_x, pos_y = pos_xy_vals[0], pos_xy_vals[1]
    else:
        pos_x, pos_y = 0.0, 0.0
    size_xy_vals = header_map.get("size_xy")
    if isinstance(size_xy_vals, (list, tuple, np.ndarray)) and len(size_xy_vals) >= 2:
        size_x, size_y = size_xy_vals[0], size_xy_vals[1]
    else:
        fallback_scan_m = float(scan_size_nm or 100.0) * 1e-9
        size_x, size_y = fallback_scan_m, fallback_scan_m
    header_lines = [
        f"Grid dim={int(nx)} x {int(ny)}",
        (
            "Grid settings="
            f"{_grid_header_scalar(pos_x, '0')};"
            f"{_grid_header_scalar(pos_y, '0')};"
            f"{_grid_header_scalar(size_x, '0')};"
            f"{_grid_header_scalar(size_y, '0')};"
            f"{_grid_header_scalar(header_map.get('angle', 0.0), '0')}"
        ),
        f"Sweep Signal={sanitize_nanonis_header_value(header_map.get('sweep_signal', 'Bias (V)'))}",
        f"Fixed parameters={_grid_header_list_text(fixed_parameters)}",
        f"Experiment parameters={_grid_header_list_text(experimental_parameters)}",
        f"# Parameters (4 byte)={int(num_parameters)}",
        f"Experiment size (bytes)={int(experiment_size)}",
        f"Points={int(n_bias)}",
        f"Channels={_grid_header_list_text(channel_names)}",
        f"Delay before measuring (s)={_grid_header_scalar(header_map.get('measure_delay', 0.0), '0')}",
        f"Experiment={sanitize_nanonis_header_value(header_map.get('experiment_name', header_map.get('Experiment', 'Grid Spectroscopy')))}",
        f"Start time={sanitize_nanonis_header_value(header_map.get('start_time', nanonis_timestamp()))}",
        f"End time={sanitize_nanonis_header_value(header_map.get('end_time', nanonis_timestamp()))}",
        f"User={sanitize_nanonis_header_value(header_map.get('user', header_map.get('User', '')))}",
        f"Comment={sanitize_nanonis_header_value(header_map.get('comment', header_map.get('Comment', '')))}",
    ]

    reserved_keys = {
        "dim_px",
        "grid_dim",
        "pos_xy",
        "size_xy",
        "angle",
        "sweep_signal",
        "fixed_parameters",
        "experimental_parameters",
        "num_parameters",
        "experiment_size",
        "num_sweep_signal",
        "channels",
        "num_channels",
        "measure_delay",
        "experiment_name",
        "start_time",
        "end_time",
        "user",
        "comment",
        "Experiment",
        "Start time",
        "End time",
        "User",
        "Comment",
        "Delay before measuring (s)",
        "Filetype",
    }
    filetype_text = _grid_header_extra_text(header_map.get("Filetype"))
    if filetype_text:
        header_lines.append(f"Filetype={filetype_text}")
    for key, value in header_map.items():
        key_text = str(key).strip()
        if not key_text or key_text in reserved_keys:
            continue
        value_text = _grid_header_extra_text(value)
        if value_text is None:
            continue
        header_lines.append(f"{key_text}={value_text}")
    header_lines.append(":HEADER_END:")
    header_blob = ("\r\n".join(header_lines) + "\r\n").encode("utf-8")

    per_pixel = int(num_parameters + n_bias * num_channels)
    raw = np.empty((int(ny), int(nx), per_pixel), dtype=">f4")
    raw[:, :, : int(num_parameters)] = params_raw
    for chan_idx, (_name, cube_internal) in enumerate(spectral_channels):
        start = int(num_parameters + chan_idx * n_bias)
        stop = int(start + n_bias)
        raw[:, :, start:stop] = np.transpose(np.asarray(cube_internal, dtype=float), (1, 0, 2)).astype(">f4", copy=False)

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as handle:
        handle.write(header_blob)
        raw.tofile(handle)
    return out_path


def write_ibw_wave(path: str | Path, data: Any, name: str | None = None) -> Path:
    try:
        from igorwriter import IgorWave
    except Exception as exc:
        raise RuntimeError("igorwriter is required for IBW export") from exc
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wave_name = name or out_path.stem
    wave = IgorWave(np.asarray(data), name=str(wave_name))
    wave.save(str(out_path))
    return out_path


__all__ = [
    "EXPORT_SOURCE_MAPPING",
    "build_nanonis_spec_header",
    "export_algorithm",
    "format_nanonis_data_value",
    "nanonis_timestamp",
    "sanitize_nanonis_header_value",
    "write_ibw_wave",
    "write_nanonis_grid_3ds",
    "write_nanonis_spec_dat",
]
