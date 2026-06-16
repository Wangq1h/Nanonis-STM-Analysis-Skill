#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = Path(os.environ.get("STM_SJTM_SKILL_CACHE", "~/.cache/stm-sjtm-data-processing")).expanduser()
HOST_CONFIG = Path(
    os.environ.get("STM_SJTM_SKILL_HOST_CONFIG", "~/.config/stm-sjtm-data-processing/host.json")
).expanduser()
RUNTIME_JSON = "runtime.json"


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception as exc:
        return {"_error": f"{type(exc).__name__}: {exc}"}


def runtime_json_path(cache_dir: Path) -> Path:
    return cache_dir.expanduser() / RUNTIME_JSON


def venv_python_from_path(venv_path: str) -> str:
    if not venv_path:
        return ""
    root = Path(venv_path).expanduser()
    if os.name == "nt":
        return str(root / "Scripts" / "python.exe")
    return str(root / "bin" / "python")


def first_existing_python(runtime: dict[str, Any]) -> str:
    candidates = [
        str(runtime.get("python", "")),
        venv_python_from_path(str(runtime.get("venv_path", ""))),
    ]
    for item in candidates:
        if item and Path(item).expanduser().is_file():
            return str(Path(item).expanduser())
    return ""


def normalize_roots(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


def resolve_pysidam_roots(runtime: dict[str, Any], host: dict[str, Any]) -> list[str]:
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
        key = str(Path(root).expanduser())
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def build_probe_command(python: str, roots: list[str]) -> list[str]:
    cmd = [python, str(SKILL_ROOT / "scripts" / "probe_runtime.py")]
    for root in roots:
        cmd.extend(["--pysidam-root", root])
    return cmd


def shell_join(cmd: list[str]) -> str:
    return " ".join(shlex.quote(item) for item in cmd)


def build_bootstrap_command(host: dict[str, Any], cache_dir: Path) -> list[str]:
    base_python = str(host.get("base_python") or sys.executable)
    groups = str(host.get("default_groups") or "headless")
    cmd = [
        base_python,
        str(SKILL_ROOT / "scripts" / "bootstrap_runtime.py"),
        "--groups",
        groups,
        "--cache-dir",
        str(cache_dir),
    ]
    for root in normalize_roots(host.get("pysidam_root")) + normalize_roots(host.get("pysidam_roots")):
        cmd.extend(["--pysidam-root", root])
    return cmd


def runtime_status(cache_dir: Path, host_config: Path) -> dict[str, Any]:
    runtime_path = runtime_json_path(cache_dir)
    runtime = read_json(runtime_path)
    host = read_json(host_config)
    python = first_existing_python(runtime)
    pysidam_roots = resolve_pysidam_roots(runtime, host)
    bootstrap_cmd = build_bootstrap_command(host, cache_dir)

    status = {
        "cache_dir": str(cache_dir.expanduser()),
        "runtime_json": str(runtime_path.expanduser()),
        "host_config": str(host_config.expanduser()),
        "runtime_json_exists": runtime_path.expanduser().is_file(),
        "host_config_exists": host_config.expanduser().is_file(),
        "runtime_json_error": runtime.get("_error", ""),
        "host_config_error": host.get("_error", ""),
        "python": python,
        "python_exists": bool(python),
        "pysidam_roots": pysidam_roots,
        "probe_command": build_probe_command(python, pysidam_roots) if python else [],
        "bootstrap_command": bootstrap_cmd,
    }
    status["ready"] = bool(status["python_exists"] and not status["runtime_json_error"])
    return status


def print_summary(status: dict[str, Any]) -> None:
    print("STM/SJTM runtime resolver")
    print(f"runtime.json: {status['runtime_json']}")
    print(f"host.json: {status['host_config']}")
    if status["ready"]:
        print(f"python: {status['python']}")
        if status["pysidam_roots"]:
            print("pysidam_root: " + ", ".join(status["pysidam_roots"]))
        print("probe:")
        print("  " + shell_join(status["probe_command"]))
    else:
        print("runtime: not ready")
        if status["runtime_json_error"]:
            print(f"runtime.json error: {status['runtime_json_error']}")
        print("bootstrap:")
        print("  " + shell_join(status["bootstrap_command"]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve the persistent STM/SJTM skill runtime.")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="Runtime cache directory.")
    parser.add_argument("--host-config", default=str(HOST_CONFIG), help="Host-specific config JSON.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable runtime status.")
    parser.add_argument("--probe", action="store_true", help="Run probe_runtime.py with the cached runtime Python.")
    parser.add_argument("--print-python", action="store_true", help="Print the cached runtime Python path.")
    parser.add_argument("--print-pysidam-root", action="store_true", help="Print resolved PySIDAM source roots.")
    parser.add_argument("--bootstrap-command", action="store_true", help="Print a safe bootstrap command.")
    parser.add_argument("--require-ready", action="store_true", help="Exit nonzero unless a cached runtime exists.")
    args = parser.parse_args()

    status = runtime_status(Path(args.cache_dir), Path(args.host_config))

    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    elif args.print_python:
        if status["python"]:
            print(status["python"])
    elif args.print_pysidam_root:
        for root in status["pysidam_roots"]:
            print(root)
    elif args.bootstrap_command:
        print(shell_join(status["bootstrap_command"]))
    elif args.probe:
        if not status["ready"]:
            print_summary(status)
            return 2
        subprocess.check_call(status["probe_command"])
    else:
        print_summary(status)

    if args.require_ready and not status["ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
