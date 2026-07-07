import ctypes
import os
import re
from dataclasses import dataclass, field

import numpy as np

from .bias_utils import is_bias_like_channel_name, normalize_imported_bias_to_mv


class ImportedReadError(RuntimeError):
    def __init__(self, path, original_error):
        self.path = str(path)
        self.original_error = original_error
        super().__init__(f"Failed to read imported file {self.path}:\n{original_error}")


@dataclass
class ImportedDataObject:
    signals: dict
    header: dict = field(default_factory=dict)
    bias: object = None


@dataclass
class ImportedFile:
    obj: ImportedDataObject
    dtype: str
    channels: list = field(default_factory=list)
    scan_size_nm: float | None = None
    source_format: str = ""
    metadata: dict = field(default_factory=dict)


def read_text_with_encodings(path, encodings=None):
    if encodings is None:
        encodings = ["utf-8", "utf-8-sig", "gbk", "cp936", "gb2312", "big5", "latin1"]
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc, errors="strict") as f:
                return f.read(), enc
        except Exception:
            continue
    with open(path, "rb") as f:
        raw = f.read()
    return raw.decode("latin1", errors="replace"), "latin1"


def parse_numeric_table(text):
    lines = text.splitlines()
    parsed_rows = []
    header_buf = []
    col_count_hist = {}
    last_textual_parts = None
    first_numeric_cols = None

    for ln in lines:
        stripped = ln.strip()
        if not stripped or stripped.startswith(("#", "//", ";")):
            header_buf.append(ln)
            continue
        parts = stripped.replace(",", " ").split()
        floats = []
        ok = True
        for p in parts:
            try:
                floats.append(float(p))
            except Exception:
                ok = False
                break
        if ok and len(floats) >= 2:
            parsed_rows.append(floats)
            col_count_hist[len(floats)] = col_count_hist.get(len(floats), 0) + 1
            if first_numeric_cols is None:
                first_numeric_cols = len(floats)
        else:
            header_buf.append(ln)
            raw_parts = [p.strip() for p in re.split(r"\t+", stripped) if p.strip()]
            if len(raw_parts) >= 2 and any(re.search(r"[A-Za-z]", p) for p in raw_parts):
                last_textual_parts = raw_parts

    if not parsed_rows:
        raise ValueError("No numeric rows parsed from file.")
    best_cols = max(col_count_hist.items(), key=lambda kv: kv[1])[0]
    filtered = [row[:best_cols] for row in parsed_rows if len(row) >= best_cols]
    col_names = None
    if last_textual_parts is not None and len(last_textual_parts) >= int(best_cols):
        col_names = [str(x).strip() for x in last_textual_parts[: int(best_cols)]]
    elif first_numeric_cols is not None and first_numeric_cols == best_cols:
        col_names = [f"col{i}" for i in range(int(best_cols))]
    return np.asarray(filtered, dtype=float), ("\n".join(header_buf) if header_buf else None), col_names


def _dedupe_name(name, used_names, fallback):
    base = str(name or "").strip() or str(fallback)
    if base not in used_names:
        used_names.add(base)
        return base
    idx = 2
    while f"{base} ({idx})" in used_names:
        idx += 1
    out = f"{base} ({idx})"
    used_names.add(out)
    return out


def _column_name_fallback(path, col_idx):
    stem = os.path.splitext(os.path.basename(os.fspath(path)))[0].strip()
    if col_idx == 1 and stem:
        return stem
    return f"Signal {col_idx}"


def _read_text_file(path):
    text, encoding = read_text_with_encodings(path)
    table, text_header, col_names = parse_numeric_table(text)
    if table.ndim != 2 or table.shape[1] < 2:
        raise ValueError("Text import requires at least two numeric columns.")
    ext = os.path.splitext(os.fspath(path))[1].lower().lstrip(".") or "txt"

    x_idx = 0
    if col_names:
        for idx, name in enumerate(col_names):
            if is_bias_like_channel_name(name):
                x_idx = idx
                break

    used_names = set()
    signals = {"Bias calc (V)": np.asarray(table[:, x_idx], dtype=float)}
    used_names.add("Bias calc (V)")
    for idx in range(table.shape[1]):
        if idx == x_idx:
            continue
        raw_name = col_names[idx] if col_names and idx < len(col_names) else None
        channel_name = _dedupe_name(raw_name, used_names, _column_name_fallback(path, idx))
        signals[channel_name] = np.asarray(table[:, idx], dtype=float)

    header = {
        "source_format": ext,
        "import_role": "spectrum_1d",
        "import_semantics": "generic_1d_spectrum",
        "encoding": encoding,
        "text_header": text_header or "",
        "column_names": list(col_names or []),
        "row_count": int(table.shape[0]),
        "column_count": int(table.shape[1]),
    }
    obj = ImportedDataObject(signals=signals, header=header)
    return ImportedFile(
        obj=obj,
        dtype="dat",
        channels=list(signals.keys()),
        source_format=ext,
        metadata={
            "encoding": encoding,
            "column_names": list(col_names or []),
            "import_role": "spectrum_1d",
            "import_semantics": "generic_1d_spectrum",
        },
    )


_IBW_MAX_DIMS = 4
_IBW_WAVE_HEADER_BYTES = 320
_IBW_WAVE_NAME5 = 31
_IBW_TYPE_TO_DTYPE = {
    2: np.dtype("<f4"),
    3: np.dtype("<c8"),
    4: np.dtype("<f8"),
    5: np.dtype("<c16"),
    8: np.dtype("<i1"),
    0x10: np.dtype("<i2"),
    0x20: np.dtype("<i4"),
    0x48: np.dtype("<u1"),
    0x50: np.dtype("<u2"),
    0x60: np.dtype("<u4"),
    0x80: np.dtype("<i8"),
    0xC0: np.dtype("<u8"),
}


class _IBWBinHeader5(ctypes.Structure):
    _pack_ = 2
    _fields_ = [
        ("version", ctypes.c_int16),
        ("checksum", ctypes.c_int16),
        ("wfmSize", ctypes.c_int32),
        ("formulaSize", ctypes.c_int32),
        ("noteSize", ctypes.c_int32),
        ("dataEUnitsSize", ctypes.c_int32),
        ("dimEUnitsSize", ctypes.c_int32 * _IBW_MAX_DIMS),
        ("dimLabelsSize", ctypes.c_int32 * _IBW_MAX_DIMS),
        ("sIndicesSize", ctypes.c_int32),
        ("longWaveNameSize", ctypes.c_int16),
        ("optionsSize1", ctypes.c_int16),
        ("optionsSize2", ctypes.c_int32),
    ]


class _IBWWaveHeader5(ctypes.Structure):
    _pack_ = 2
    _fields_ = [
        ("next", ctypes.c_byte * 4),
        ("creationDate", ctypes.c_uint32),
        ("modDate", ctypes.c_uint32),
        ("npnts", ctypes.c_int32),
        ("type", ctypes.c_int16),
        ("dLock", ctypes.c_int16),
        ("whpad1", ctypes.c_char * 3),
        ("waveNameEncoding", ctypes.c_byte),
        ("waveUnitsEncoding", ctypes.c_byte),
        ("waveNoteEncoding", ctypes.c_byte),
        ("whVersion", ctypes.c_int16),
        ("bname", ctypes.c_char * (_IBW_WAVE_NAME5 + 1)),
        ("whpad2", ctypes.c_int32),
        ("dFolder", ctypes.c_byte * 4),
        ("nDim", ctypes.c_int32 * _IBW_MAX_DIMS),
        ("sfA", ctypes.c_double * _IBW_MAX_DIMS),
        ("sfB", ctypes.c_double * _IBW_MAX_DIMS),
        ("dataUnits", ctypes.c_char * 4),
        ("dimUnits", (ctypes.c_char * 4) * _IBW_MAX_DIMS),
        ("fsValid", ctypes.c_int16),
        ("whpad3", ctypes.c_int16),
        ("botFullScale", ctypes.c_double),
        ("topFullScale", ctypes.c_double),
        ("dataEUnits", ctypes.c_byte * 4),
        ("dimEUnits", (ctypes.c_byte * 4) * _IBW_MAX_DIMS),
        ("dimLabels", (ctypes.c_byte * 4) * _IBW_MAX_DIMS),
        ("waveNoteH", ctypes.c_byte * 4),
        ("platform", ctypes.c_char),
        ("spare", ctypes.c_char),
        ("waveDimLabelEncoding", ctypes.c_byte),
        ("textWaveContentEncoding", ctypes.c_byte),
        ("whUnused", ctypes.c_int32 * 13),
        ("vRefNum", ctypes.c_int32),
        ("dirID", ctypes.c_int32),
        ("private", ctypes.c_byte * 28),
    ]


def _decode_c_text(raw, prefer_utf8=False):
    blob = bytes(raw).split(b"\x00", 1)[0]
    if not blob:
        return ""
    encodings = ["utf-8", "latin1"] if prefer_utf8 else ["latin1", "utf-8"]
    for enc in encodings:
        try:
            return blob.decode(enc).strip()
        except Exception:
            continue
    return blob.decode("latin1", errors="replace").strip()


def _decode_blob_text(blob, prefer_utf8=False):
    if not blob:
        return ""
    encodings = ["utf-8", "latin1"] if prefer_utf8 else ["latin1", "utf-8"]
    for enc in encodings:
        try:
            return blob.decode(enc).strip()
        except Exception:
            continue
    return blob.decode("latin1", errors="replace").strip()


def _infer_length_unit_factor_to_nm(unit):
    text = str(unit or "").strip().lower()
    if not text:
        return None
    aliases = {
        "m": 1e9,
        "meter": 1e9,
        "meters": 1e9,
        "nm": 1.0,
        "um": 1e3,
        "µm": 1e3,
        "μm": 1e3,
        "pm": 1e-3,
        "a": 0.1,
        "å": 0.1,
        "angstrom": 0.1,
        "angstroms": 0.1,
    }
    return aliases.get(text)


def _infer_bias_unit_factor_to_mv(unit):
    text = str(unit or "").strip().lower()
    aliases = {
        "v": 1e3,
        "volt": 1e3,
        "volts": 1e3,
        "mv": 1.0,
        "millivolt": 1.0,
        "millivolts": 1.0,
        "uv": 1e-3,
        "µv": 1e-3,
        "μv": 1e-3,
        "microvolt": 1e-3,
        "microvolts": 1e-3,
    }
    return aliases.get(text)


def _normalize_ibw_bias_axis_to_mv(values, unit=None):
    arr = np.asarray(values, dtype=float).ravel()
    factor = _infer_bias_unit_factor_to_mv(unit)
    if factor is not None:
        return np.asarray(arr * float(factor), dtype=float)
    return np.asarray(normalize_imported_bias_to_mv(arr), dtype=float)


def _ibw_has_explicit_spectral_metadata(wave_name, note):
    text = f"{wave_name} {note}".lower()
    keywords = (
        "didv",
        "di/dv",
        "d idv",
        "spectrum",
        "spectra",
        "spectroscopy",
        "sweep",
        "bias",
        "energy",
    )
    return any(token in text for token in keywords)


def _ibw_text_looks_fft(wave_name, note):
    text = f"{wave_name} {note}".lower()
    return any(token in text for token in ("fft", "sft", "fourier", "k-space", "reciprocal"))


def _ibw_axis_span_native(axis):
    try:
        values = np.asarray(axis.get("values"), dtype=float).ravel()
    except Exception:
        values = np.asarray([], dtype=float)
    if values.size >= 2:
        span = float(values[-1] - values[0])
        if np.isfinite(span) and span != 0:
            return abs(span)
    try:
        delta = float(axis.get("delta", 0.0))
        size = int(axis.get("size", 0))
    except Exception:
        return None
    span = abs(delta) * max(size - 1, 1)
    if np.isfinite(span) and span > 0:
        return float(span)
    return None


def _ibw_axis_span_nm(axis):
    factor = _infer_length_unit_factor_to_nm(axis.get("unit"))
    if factor is None:
        return None
    span_native = _ibw_axis_span_native(axis)
    if span_native is None:
        return None
    return float(span_native) * float(factor)


def _score_ibw_bias_axis(axis, wave_name="", note=""):
    try:
        values = np.asarray(axis.get("values"), dtype=float).ravel()
    except Exception:
        values = np.asarray([], dtype=float)
    if values.size <= 1:
        return -1e9
    finite = values[np.isfinite(values)]
    if finite.size != values.size or finite.size <= 1:
        return -1e9

    score = 0.0
    unit = str(axis.get("unit") or "").strip().lower()
    if _infer_bias_unit_factor_to_mv(unit) is not None:
        score += 20.0
    if _infer_length_unit_factor_to_nm(unit) is not None:
        score -= 8.0

    diffs = np.diff(finite)
    monotonic = bool(np.all(diffs >= 0) or np.all(diffs <= 0))
    if monotonic:
        score += 4.0
    if np.nanmin(finite) <= 0.0 <= np.nanmax(finite):
        score += 5.0

    span = float(np.nanmax(finite) - np.nanmin(finite))
    max_abs = float(np.nanmax(np.abs(finite)))
    if np.isfinite(max_abs):
        if max_abs <= 5.0:
            score += 4.0
        elif max_abs <= 5000.0:
            score += 2.0
        elif max_abs >= 1e6:
            score -= 4.0
    if np.isfinite(span) and span > 0:
        center = abs(float(np.nanmean(finite))) / max(span, 1e-12)
        score += max(0.0, 2.0 - 3.0 * center)

    text = f"{wave_name} {note}".lower()
    if any(token in text for token in ("bias", "sweep", "energy", "spec", "didv")):
        score += 1.0
    return score


def _guess_ibw_bias_axis_index(axes, wave_name="", note=""):
    if not axes:
        return None
    best_idx = None
    best_score = None
    for idx, axis in enumerate(axes):
        score = _score_ibw_bias_axis(axis, wave_name=wave_name, note=note)
        if best_score is None or score > best_score:
            best_idx = idx
            best_score = score
    if best_score is None or best_score < 4.0:
        return None
    best_axis = axes[int(best_idx)]
    unit = str(best_axis.get("unit") or "").strip().lower()
    try:
        values = np.asarray(best_axis.get("values"), dtype=float).ravel()
    except Exception:
        values = np.asarray([], dtype=float)
    crosses_zero = bool(values.size > 1 and np.nanmin(values) <= 0.0 <= np.nanmax(values))
    has_bias_unit = _infer_bias_unit_factor_to_mv(unit) is not None
    has_explicit_meta = _ibw_has_explicit_spectral_metadata(wave_name, note)
    if not (has_bias_unit or crosses_zero or has_explicit_meta):
        return None
    return int(best_idx)


def _ibw_axis_metadata(axes):
    out = []
    for axis in axes:
        out.append(
            {
                "size": int(axis.get("size", 0)),
                "start": float(axis.get("start", 0.0)),
                "delta": float(axis.get("delta", 0.0)),
                "unit": str(axis.get("unit", "")),
                "values": np.asarray(axis.get("values", []), dtype=float),
            }
        )
    return out


def _ibw_looks_like_fft(wave_name, note, axes):
    text = f"{wave_name} {note}".lower()
    if any(token in text for token in ("fft", "sft", "fourier", "magnitude squared", "power spectrum")):
        return True
    try:
        if len(axes) >= 2:
            starts = [float(axes[i]["start"]) for i in range(2)]
            deltas = [abs(float(axes[i]["delta"])) for i in range(2)]
            sizes = [int(axes[i]["size"]) for i in range(2)]
            spans = [deltas[i] * max(sizes[i] - 1, 1) for i in range(2)]
            if all(np.isfinite(starts + deltas + spans)) and all(0.0 < v <= 2.0 for v in spans):
                if any(v < 0.0 for v in starts) and all(v < 0.1 for v in deltas):
                    return True
    except Exception:
        pass
    return False


def _read_ibw_file(path):
    with open(path, "rb") as f:
        raw = f.read()
    header_size = ctypes.sizeof(_IBWBinHeader5) + ctypes.sizeof(_IBWWaveHeader5)
    if len(raw) < header_size:
        raise ValueError("File is too small to be a valid IBW file.")

    bin_header = _IBWBinHeader5.from_buffer_copy(raw[: ctypes.sizeof(_IBWBinHeader5)])
    wave_header = _IBWWaveHeader5.from_buffer_copy(
        raw[ctypes.sizeof(_IBWBinHeader5) : header_size]
    )
    if int(bin_header.version) not in (5, 7):
        raise ValueError(f"Unsupported IBW version: {bin_header.version}")
    dtype = _IBW_TYPE_TO_DTYPE.get(int(wave_header.type))
    if dtype is None:
        raise ValueError(f"Unsupported IBW numeric type code: {wave_header.type}")

    dims = [int(v) for v in wave_header.nDim if int(v) > 0]
    if not dims:
        dims = [int(wave_header.npnts)]
    if np.prod(dims, dtype=np.int64) != int(wave_header.npnts):
        raise ValueError("IBW shape metadata does not match point count.")

    data_bytes = int(bin_header.wfmSize) - _IBW_WAVE_HEADER_BYTES
    if data_bytes <= 0:
        raise ValueError("IBW file contains no wave data.")
    data_offset = header_size
    data_end = data_offset + data_bytes
    if data_end > len(raw):
        raise ValueError("IBW data section is truncated.")

    flat = np.frombuffer(raw[data_offset:data_end], dtype=dtype, count=int(wave_header.npnts))
    array = np.asarray(flat.reshape(tuple(dims), order="F"))

    formula_end = data_end + int(bin_header.formulaSize)
    note_end = formula_end + int(bin_header.noteSize)
    if note_end > len(raw):
        note_end = len(raw)
    note = _decode_blob_text(
        raw[formula_end:note_end],
        prefer_utf8=bool(int(wave_header.waveNoteEncoding)),
    )
    wave_name = _decode_c_text(
        wave_header.bname,
        prefer_utf8=bool(int(wave_header.waveNameEncoding)),
    ) or os.path.splitext(os.path.basename(os.fspath(path)))[0]
    data_units = _decode_c_text(
        wave_header.dataUnits,
        prefer_utf8=bool(int(wave_header.waveUnitsEncoding)),
    )
    dim_units = [
        _decode_c_text(
            wave_header.dimUnits[idx],
            prefer_utf8=bool(int(wave_header.waveUnitsEncoding)),
        )
        for idx in range(len(dims))
    ]
    axes = []
    for idx, size in enumerate(dims):
        delta = float(wave_header.sfA[idx])
        start = float(wave_header.sfB[idx])
        axis = start + delta * np.arange(int(size), dtype=float)
        axes.append(
            {
                "size": int(size),
                "start": start,
                "delta": delta,
                "unit": dim_units[idx] if idx < len(dim_units) else "",
                "values": axis,
            }
        )

    header = {
        "source_format": "ibw",
        "ibw_version": int(bin_header.version),
        "ibw_wave_name": wave_name,
        "ibw_note": note,
        "ibw_shape": tuple(int(v) for v in dims),
        "ibw_type_code": int(wave_header.type),
        "ibw_data_units": data_units,
        "ibw_dim_units": dim_units,
        "ibw_axes": _ibw_axis_metadata(axes),
    }

    if array.ndim == 1:
        header.update({
            "import_role": "spectrum_1d",
            "import_semantics": "generic_1d_spectrum",
        })
        signals = {
            "Bias calc (V)": np.asarray(axes[0]["values"], dtype=float),
            wave_name: np.asarray(array, dtype=float).ravel(),
        }
        obj = ImportedDataObject(signals=signals, header=header)
        return ImportedFile(
            obj=obj,
            dtype="dat",
            channels=list(signals.keys()),
            source_format="ibw",
            metadata={
                "shape": tuple(dims),
                "wave_name": wave_name,
                "note": note,
                "import_role": "spectrum_1d",
                "import_semantics": "generic_1d_spectrum",
            },
        )

    if array.ndim == 2:
        is_fft = _ibw_looks_like_fft(wave_name, note, axes)
        bias_idx = _guess_ibw_bias_axis_index(axes, wave_name=wave_name, note=note)
        spectral_like = (not is_fft) and (bias_idx is not None)
        if spectral_like:
            if bias_idx is None:
                bias_idx = 1 if len(axes) > 1 else 0
            spatial_idx = 1 - int(bias_idx)
            bias_axis_mv = _normalize_ibw_bias_axis_to_mv(
                axes[int(bias_idx)]["values"],
                axes[int(bias_idx)].get("unit"),
            )
            scan_size_nm = _ibw_axis_span_nm(axes[int(spatial_idx)])
            if scan_size_nm is None:
                scan_size_nm = float(max(int(axes[int(spatial_idx)]["size"]) - 1, 1))
            header.update(
                {
                    "import_role": "generic_linecut_map_2d",
                    "import_semantics": "unknown_linecut_map",
                    "ibw_is_fft": False,
                    "ibw_promotable_spectral": True,
                    "ibw_bias_axis_index": int(bias_idx),
                    "ibw_spatial_axis_indices": [int(spatial_idx)],
                    "ibw_bias_already_mv": True,
                    "size_xy": [float(scan_size_nm) * 1e-9, 1e-9],
                    "scan_range": [float(scan_size_nm) * 1e-9, 1e-9],
                }
            )
            signals = {wave_name: np.asarray(array, dtype=float)}
            obj = ImportedDataObject(signals=signals, header=header, bias=bias_axis_mv)
            return ImportedFile(
                obj=obj,
                dtype="sxm",
                channels=list(signals.keys()),
                scan_size_nm=float(scan_size_nm),
                source_format="ibw",
                metadata={
                    "shape": tuple(dims),
                    "wave_name": wave_name,
                    "note": note,
                    "import_role": "generic_linecut_map_2d",
                    "import_semantics": "unknown_linecut_map",
                    "ibw_is_fft": False,
                    "ibw_promotable_spectral": True,
                    "ibw_bias_axis_index": int(bias_idx),
                    "ibw_spatial_axis_indices": [int(spatial_idx)],
                },
            )
        import_role = "generic_fft_map_2d" if is_fft else "generic_map_2d"
        import_semantics = "unknown_2d_fft_map" if is_fft else "unknown_2d_map"
        header.update({
            "import_role": import_role,
            "import_semantics": import_semantics,
            "ibw_is_fft": bool(is_fft),
        })
        signals = {wave_name: np.asarray(array, dtype=float)}
        scan_size_nm = None
        factors = [_infer_length_unit_factor_to_nm(ax.get("unit")) for ax in axes[:2]]
        if all(f is not None for f in factors):
            size_x_nm = abs(float(axes[0]["delta"])) * max(int(axes[0]["size"]) - 1, 1) * float(factors[0])
            size_y_nm = abs(float(axes[1]["delta"])) * max(int(axes[1]["size"]) - 1, 1) * float(factors[1])
            scan_size_nm = float(max(size_x_nm, size_y_nm))
            header["scan_range"] = [size_x_nm * 1e-9, size_y_nm * 1e-9]
            header["size_xy"] = [size_x_nm * 1e-9, size_y_nm * 1e-9]
        obj = ImportedDataObject(signals=signals, header=header)
        return ImportedFile(
            obj=obj,
            dtype="sxm",
            channels=list(signals.keys()),
            scan_size_nm=scan_size_nm,
            source_format="ibw",
            metadata={
                "shape": tuple(dims),
                "wave_name": wave_name,
                "note": note,
                "import_role": import_role,
                "import_semantics": import_semantics,
                "ibw_is_fft": bool(is_fft),
            },
        )

    if array.ndim == 3 and not _ibw_text_looks_fft(wave_name, note):
        bias_idx = _guess_ibw_bias_axis_index(axes, wave_name=wave_name, note=note)
        if bias_idx is None and _ibw_has_explicit_spectral_metadata(wave_name, note):
            bias_idx = int(array.ndim - 1)
        if bias_idx is None:
            header.update({
                "import_role": "generic_nd_wave",
                "import_semantics": "unknown_nd_wave",
                "ibw_is_fft": False,
            })
            signals = {wave_name: np.asarray(array)}
            obj = ImportedDataObject(signals=signals, header=header)
            return ImportedFile(
                obj=obj,
                dtype="ibw",
                channels=list(signals.keys()),
                source_format="ibw",
                metadata={
                    "shape": tuple(dims),
                    "wave_name": wave_name,
                    "note": note,
                    "import_role": "generic_nd_wave",
                    "import_semantics": "unknown_nd_wave",
                    "ibw_is_fft": False,
                },
            )
        spatial_indices = [idx for idx in range(array.ndim) if idx != int(bias_idx)]
        bias_axis_mv = _normalize_ibw_bias_axis_to_mv(
            axes[int(bias_idx)]["values"],
            axes[int(bias_idx)].get("unit"),
        )
        spans_nm = []
        size_xy = []
        for idx in spatial_indices[:2]:
            span_nm = _ibw_axis_span_nm(axes[idx])
            if span_nm is None:
                span_nm = float(max(int(axes[idx]["size"]) - 1, 1))
            spans_nm.append(float(span_nm))
            size_xy.append(float(span_nm) * 1e-9)
        scan_size_nm = float(max(spans_nm)) if spans_nm else float(max(int(v) - 1 for v in dims[:2]))
        if len(size_xy) == 1:
            size_xy = [size_xy[0], size_xy[0]]
        header.update(
            {
                "import_role": "generic_spectral_cube_3d",
                "import_semantics": "unknown_spectral_cube",
                "ibw_is_fft": False,
                "ibw_promotable_spectral": True,
                "ibw_bias_axis_index": int(bias_idx),
                "ibw_spatial_axis_indices": [int(v) for v in spatial_indices[:2]],
                "ibw_bias_already_mv": True,
                "size_xy": list(size_xy[:2]) if size_xy else [scan_size_nm * 1e-9, scan_size_nm * 1e-9],
                "scan_range": list(size_xy[:2]) if size_xy else [scan_size_nm * 1e-9, scan_size_nm * 1e-9],
            }
        )
        signals = {wave_name: np.asarray(array, dtype=float)}
        obj = ImportedDataObject(signals=signals, header=header, bias=bias_axis_mv)
        return ImportedFile(
            obj=obj,
            dtype="ibw",
            channels=list(signals.keys()),
            scan_size_nm=scan_size_nm,
            source_format="ibw",
            metadata={
                "shape": tuple(dims),
                "wave_name": wave_name,
                "note": note,
                "import_role": "generic_spectral_cube_3d",
                "import_semantics": "unknown_spectral_cube",
                "ibw_is_fft": False,
                "ibw_promotable_spectral": True,
                "ibw_bias_axis_index": int(bias_idx),
                "ibw_spatial_axis_indices": [int(v) for v in spatial_indices[:2]],
            },
        )

    header.update({
        "import_role": "generic_nd_wave",
        "import_semantics": "unknown_nd_wave",
        "ibw_is_fft": bool(_ibw_text_looks_fft(wave_name, note)),
    })
    signals = {wave_name: np.asarray(array)}
    obj = ImportedDataObject(signals=signals, header=header)
    return ImportedFile(
        obj=obj,
        dtype="ibw",
        channels=list(signals.keys()),
        source_format="ibw",
        metadata={
            "shape": tuple(dims),
            "wave_name": wave_name,
            "note": note,
            "import_role": "generic_nd_wave",
            "import_semantics": "unknown_nd_wave",
            "ibw_is_fft": bool(_ibw_text_looks_fft(wave_name, note)),
        },
    )


def read_imported_file(path):
    path = os.fspath(path)
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in {".txt", ".csv", ".tsv"}:
            return _read_text_file(path)
        if ext == ".ibw":
            return _read_ibw_file(path)
        raise ValueError(f"Unsupported imported file type: {path}")
    except Exception as exc:
        raise ImportedReadError(path, exc) from exc


def imported_file_to_numeric_table(imported_file):
    if imported_file is None or getattr(imported_file, "dtype", None) != "dat":
        raise ValueError("Imported file is not a 1D spectroscopy-like dataset.")
    obj = getattr(imported_file, "obj", None)
    signals = getattr(obj, "signals", None)
    if not isinstance(signals, dict):
        raise ValueError("Imported file does not contain usable signal data.")
    x = np.asarray(signals.get("Bias calc (V)"), dtype=float).ravel()
    if x.size < 2:
        raise ValueError("Imported file is missing a usable bias axis.")
    y_keys = [key for key in signals.keys() if key != "Bias calc (V)"]
    if not y_keys:
        raise ValueError("Imported file does not contain any signal channels.")
    y = np.asarray(signals[y_keys[0]], dtype=float).ravel()
    n = min(x.size, y.size)
    if n < 2:
        raise ValueError("Imported file contains fewer than 2 points.")
    header = getattr(obj, "header", {}) or {}
    header_text = header.get("text_header") or header.get("ibw_note") or ""
    cols = ["Bias calc (V)", y_keys[0]]
    return np.column_stack((x[:n], y[:n])), header_text, "binary" if imported_file.source_format == "ibw" else header.get("encoding", "-"), cols


__all__ = [
    "ImportedDataObject",
    "ImportedFile",
    "ImportedReadError",
    "imported_file_to_numeric_table",
    "parse_numeric_table",
    "read_imported_file",
    "read_text_with_encodings",
]
