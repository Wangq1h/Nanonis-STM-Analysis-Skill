#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = Path(os.environ.get("STM_SJTM_SKILL_CACHE", "~/.cache/stm-sjtm-data-processing")).expanduser()
HOST_CONFIG = Path(
    os.environ.get("STM_SJTM_SKILL_HOST_CONFIG", "~/.config/stm-sjtm-data-processing/host.json")
).expanduser()
RUNTIME_JSON = "runtime.json"
REEXEC_ENV = "STM_SJTM_AGENT_RUNTIME_REEXEC"


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if isinstance(data, dict):
        return data
    return {}


def runtime_json_path(cache_dir: Path = DEFAULT_CACHE_DIR) -> Path:
    return cache_dir.expanduser() / RUNTIME_JSON


def normalize_roots(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


def venv_python_from_path(venv_path: str) -> str:
    if not venv_path:
        return ""
    root = Path(venv_path).expanduser()
    if os.name == "nt":
        return str(root / "Scripts" / "python.exe")
    return str(root / "bin" / "python")


def runtime_python(runtime: dict[str, Any]) -> str:
    candidates = [
        str(runtime.get("python", "")),
        venv_python_from_path(str(runtime.get("venv_path", ""))),
    ]
    for item in candidates:
        if item and Path(item).expanduser().is_file():
            return str(Path(item).expanduser())
    return ""


def resolved_pysidam_roots(runtime: dict[str, Any], host: dict[str, Any]) -> list[str]:
    roots: list[str] = []
    roots.extend(normalize_roots(runtime.get("pysidam_root")))
    roots.extend(normalize_roots(host.get("pysidam_root")))
    roots.extend(normalize_roots(host.get("pysidam_roots")))
    env_root = os.environ.get("PYSIDAM_ROOT")
    if env_root:
        roots.append(env_root)

    out: list[str] = []
    seen: set[str] = set()
    for root in roots:
        text = str(Path(root).expanduser())
        if text not in seen:
            seen.add(text)
            out.append(text)
    return out


def add_pysidam_roots_to_path(roots: list[str]) -> None:
    for root in reversed(roots):
        path = Path(root).expanduser()
        if (path / "pysidam" / "core" / "nanonis_io.py").is_file():
            text = str(path)
            if text not in sys.path:
                sys.path.insert(0, text)


def _same_executable(a: str, b: str) -> bool:
    try:
        return Path(a).resolve() == Path(b).resolve()
    except Exception:
        return os.path.abspath(a) == os.path.abspath(b)


def ensure_runtime(reexec: bool = True) -> dict[str, Any]:
    """Load cached runtime metadata and re-exec inside it when possible."""
    runtime_path = runtime_json_path()
    runtime = read_json(runtime_path)
    host = read_json(HOST_CONFIG)
    python = runtime_python(runtime)
    roots = resolved_pysidam_roots(runtime, host)

    if reexec and python and not _same_executable(sys.executable, python) and not os.environ.get(REEXEC_ENV):
        env = dict(os.environ)
        env[REEXEC_ENV] = "1"
        env.setdefault("STM_SJTM_SKILL_ROOT", str(SKILL_ROOT))
        if roots:
            env.setdefault("PYSIDAM_ROOT", roots[0])
        os.execve(python, [python, *sys.argv], env)

    add_pysidam_roots_to_path(roots)
    return {
        "runtime_json": str(runtime_path),
        "host_config": str(HOST_CONFIG),
        "python": python,
        "current_python": sys.executable,
        "pysidam_roots": roots,
        "runtime_json_exists": runtime_path.is_file(),
        "host_config_exists": HOST_CONFIG.is_file(),
    }


def json_default(value: Any) -> Any:
    try:
        import numpy as np

        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
        if isinstance(value, np.ndarray):
            return value.tolist()
    except Exception:
        pass
    if isinstance(value, Path):
        return str(value)
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")


def finite_summary(array: Any) -> dict[str, Any]:
    import numpy as np

    arr = np.asarray(array)
    out: dict[str, Any] = {
        "shape": [int(x) for x in arr.shape],
        "dtype": str(arr.dtype),
    }
    if arr.size == 0:
        out.update({"finite_count": 0, "nan_count": 0})
        return out

    try:
        vals = np.asarray(arr, dtype=float)
    except Exception:
        out["numeric"] = False
        return out

    finite = np.isfinite(vals)
    out["numeric"] = True
    out["finite_count"] = int(np.count_nonzero(finite))
    out["nan_count"] = int(np.count_nonzero(~finite))
    if out["finite_count"]:
        good = vals[finite]
        out["min"] = float(np.nanmin(good))
        out["max"] = float(np.nanmax(good))
        out["mean"] = float(np.nanmean(good))
    return out


def signals_summary(signals: Any, max_channels: int = 80) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not isinstance(signals, dict):
        return out
    for idx, (name, raw) in enumerate(signals.items()):
        if idx >= max_channels:
            out["_truncated"] = True
            out["_channel_count"] = len(signals)
            break
        if isinstance(raw, dict):
            out[str(name)] = {str(k): finite_summary(v) for k, v in raw.items()}
        else:
            out[str(name)] = finite_summary(raw)
    return out


def header_summary(header: Any, include_values: bool = False) -> dict[str, Any]:
    if not isinstance(header, dict):
        return {"type": type(header).__name__, "key_count": 0}
    keys = [str(k) for k in header.keys()]
    out: dict[str, Any] = {
        "type": "dict",
        "key_count": len(keys),
        "keys": keys[:80],
        "privacy": "header values omitted by default",
    }
    if include_values:
        out["values"] = {str(k): str(v) for k, v in list(header.items())[:80]}
        out["privacy"] = "header values included by explicit request"
    return out


def best_channel_name(channels: list[str], requested: str, fallback_contains: list[str]) -> str:
    if not channels:
        return ""
    if requested in channels:
        return requested
    req = requested.strip().lower()
    for name in channels:
        low = str(name).lower()
        if low == req or low.startswith(req):
            return str(name)
    for token in fallback_contains:
        tok = token.lower()
        for name in channels:
            low = str(name).lower()
            if tok in low and "[bwd]" not in low:
                return str(name)
    for name in channels:
        if "[bwd]" not in str(name).lower():
            return str(name)
    return str(channels[0])


def backward_partner(channels: list[str], forward_name: str) -> str:
    base = forward_name.replace(" [bwd]", "")
    for name in channels:
        text = str(name)
        if "[bwd]" in text and text.replace(" [bwd]", "") == base:
            return text
    bare = base.split("(")[0].strip().lower()
    for name in channels:
        text = str(name)
        if "[bwd]" in text.lower() and bare and bare in text.lower():
            return text
    return ""
