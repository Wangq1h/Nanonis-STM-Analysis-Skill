import importlib
import os
from dataclasses import dataclass, field

import numpy as np


_NAP_MODULE = None
_NAP_IMPORT_ERROR = None
_NAP_IMPORT_ATTEMPTED = False


class NanonisUnavailableError(RuntimeError):
    pass


class NanonisReadError(RuntimeError):
    def __init__(self, path, original_error):
        self.path = str(path)
        self.original_error = original_error
        super().__init__(f"Failed to read {self.path} with nanonispy:\n{original_error}")


@dataclass
class NanonisFile:
    obj: object
    dtype: str
    channels: list = field(default_factory=list)


def ensure_numpy_nanonis_compatibility():
    aliases = {
        "bool": bool,
        "complex": complex,
        "float": float,
        "int": int,
        "object": object,
        "str": str,
    }
    namespace = np.__dict__
    for name, value in aliases.items():
        if name not in namespace:
            setattr(np, name, value)


def import_nanonispy(required=False):
    global _NAP_MODULE, _NAP_IMPORT_ERROR, _NAP_IMPORT_ATTEMPTED
    if _NAP_MODULE is not None:
        return _NAP_MODULE
    if _NAP_IMPORT_ATTEMPTED:
        if required:
            raise NanonisUnavailableError(f"nanonispy is unavailable: {_NAP_IMPORT_ERROR}")
        return None

    _NAP_IMPORT_ATTEMPTED = True
    ensure_numpy_nanonis_compatibility()
    try:
        _NAP_MODULE = importlib.import_module("nanonispy")
        _NAP_IMPORT_ERROR = None
    except Exception as exc:
        _NAP_MODULE = None
        _NAP_IMPORT_ERROR = exc
        if required:
            raise NanonisUnavailableError(f"nanonispy is unavailable: {exc}") from exc
    return _NAP_MODULE


def nanonis_available():
    return import_nanonispy(required=False) is not None


def extract_nanonis_channels(obj):
    try:
        signals = getattr(obj, "signals", None)
        if isinstance(signals, dict):
            return list(signals.keys())
    except Exception:
        pass
    return []


def _prepare_grid_object(obj):
    try:
        if not (hasattr(obj, "signals") and isinstance(obj.signals, dict)):
            return obj
        if "topo" not in obj.signals:
            topo_key = None
            for cand in ("Topography", "Topography (m)", "Z", "Z (m)", "Height", "Height (m)"):
                if cand in obj.signals:
                    topo_key = cand
                    break
            if topo_key is not None:
                topo_arr = np.asarray(obj.signals[topo_key])
                try:
                    topo_arr = topo_arr.squeeze()
                except Exception:
                    pass
                obj.signals["topo"] = topo_arr
        if "sweep_signal" not in obj.signals and "Bias (V)" in obj.signals:
            obj.signals["sweep_signal"] = obj.signals["Bias (V)"]
    except Exception:
        pass
    return obj


def read_nanonis_file(path):
    path = os.fspath(path)
    ext = os.path.splitext(path)[1].lower()
    nap = import_nanonispy(required=True)

    try:
        if ext == ".3ds":
            obj = _prepare_grid_object(nap.read.Grid(path))
            dtype = "3ds"
        elif ext == ".sxm":
            obj = nap.read.Scan(path)
            dtype = "sxm"
        elif ext == ".dat":
            obj = nap.read.Spec(path)
            dtype = "dat"
        else:
            raise ValueError(f"Unsupported Nanonis file type: {path}")
    except Exception as exc:
        raise NanonisReadError(path, exc) from exc

    return NanonisFile(obj=obj, dtype=dtype, channels=extract_nanonis_channels(obj))


__all__ = [
    "NanonisFile",
    "NanonisReadError",
    "NanonisUnavailableError",
    "ensure_numpy_nanonis_compatibility",
    "extract_nanonis_channels",
    "import_nanonispy",
    "nanonis_available",
    "read_nanonis_file",
]
