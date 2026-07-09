#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = SKILL_ROOT / "src"

if SRC_ROOT.is_dir():
    sys.path.insert(0, str(SRC_ROOT))

DEFAULT_MODULES = [
    ("analystm", "public_backend"),
    ("numpy", "core"),
    ("scipy", "core"),
    ("skimage", "core"),
    ("matplotlib", "core"),
    ("openpyxl", "core"),
    ("nanonispy", "native_io"),
    ("igorwriter", "ibw_export"),
]

LEGACY_PYSIDAM_MODULES = [
    ("pysidam", "legacy_pysidam"),
]

AI_MODULES = [
    ("Atom_Identificator_core", "ai_atom_detection"),
]

MODULES = DEFAULT_MODULES


def import_status(module_name: str) -> dict[str, Any]:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        return {
            "module": module_name,
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    return {
        "module": module_name,
        "ok": True,
        "file": str(getattr(module, "__file__", "")),
        "version": str(getattr(module, "__version__", "")),
    }


def candidate_roots(explicit: list[str]) -> list[Path]:
    roots: list[Path] = []
    for item in explicit:
        if item:
            roots.append(Path(item).expanduser())
    env_root = os.environ.get("PYSIDAM_ROOT")
    if env_root:
        roots.append(Path(env_root).expanduser())
    cwd = Path.cwd().resolve()
    for base in [cwd, *cwd.parents]:
        roots.append(base)
        roots.append(base / "pysidam")
        roots.append(base / "pysidam-origin-main")
    out: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            resolved = root.resolve()
        except Exception:
            resolved = root
        key = str(resolved)
        if key not in seen:
            seen.add(key)
            out.append(resolved)
    return out


def looks_like_pysidam_source(root: Path) -> bool:
    return (root / "pysidam" / "core" / "nanonis_io.py").is_file()


def git_info(root: Path) -> dict[str, Any]:
    def run_git(args: list[str]) -> str:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()

    info: dict[str, Any] = {}
    try:
        info["head"] = run_git(["rev-parse", "HEAD"])
        info["branch"] = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        info["status_short"] = run_git(["status", "--short"])
        try:
            info["origin_main"] = run_git(["rev-parse", "origin/main"])
        except Exception:
            info["origin_main"] = ""
    except Exception as exc:
        info["error"] = f"{type(exc).__name__}: {exc}"
    return info


def find_and_load_pysidam(explicit_roots: list[str]) -> dict[str, Any]:
    initial = import_status("pysidam")
    if initial["ok"]:
        return {
            "loaded": True,
            "method": "import",
            "root": "",
            "import": initial,
            "git": {},
        }

    for root in candidate_roots(explicit_roots):
        if not looks_like_pysidam_source(root):
            continue
        sys.path.insert(0, str(root))
        retry = import_status("pysidam")
        if retry["ok"]:
            return {
                "loaded": True,
                "method": "source",
                "root": str(root),
                "import": retry,
                "git": git_info(root),
            }
        try:
            sys.path.remove(str(root))
        except ValueError:
            pass

    return {
        "loaded": False,
        "method": "unavailable",
        "root": "",
        "import": initial,
        "git": {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe STM/SJTM skill runtime dependencies.")
    parser.add_argument(
        "--include-legacy-pysidam",
        action="store_true",
        help="Also probe the explicit legacy PySIDAM bridge runtime.",
    )
    parser.add_argument(
        "--include-ai",
        action="store_true",
        help="Also probe the not-yet-default external AI atom detector integration.",
    )
    parser.add_argument("--pysidam-root", action="append", default=[], help="Path to a legacy PySIDAM source checkout root.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    include_legacy = bool(args.include_legacy_pysidam or args.pysidam_root)
    pysidam_info: dict[str, Any] | None = find_and_load_pysidam(args.pysidam_root) if include_legacy else None

    module_results = []
    modules = list(DEFAULT_MODULES)
    if include_legacy:
        modules.extend(LEGACY_PYSIDAM_MODULES)
    if args.include_ai:
        modules.extend(AI_MODULES)

    for module_name, tier in modules:
        if module_name == "pysidam":
            status = dict(pysidam_info["import"]) if pysidam_info else import_status("pysidam")
        else:
            status = import_status(module_name)
        status["tier"] = tier
        module_results.append(status)

    def ok(module_name: str) -> bool:
        return bool(next(item for item in module_results if item["module"] == module_name)["ok"])

    result = {
        "modules": module_results,
        "capabilities": {
            "analystm_public_backend": ok("analystm"),
            "raw_nanonis_io": ok("nanonispy"),
            "ibw_export": ok("igorwriter"),
            "ai_atom_detection": "planned",
        },
    }
    if include_legacy:
        result["legacy_pysidam"] = pysidam_info
        result["capabilities"]["legacy_pysidam_bridge"] = bool(pysidam_info and pysidam_info["loaded"])
    if args.include_ai:
        result["capabilities"]["ai_atom_detection"] = ok("Atom_Identificator_core")

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print("STM/SJTM AnalySTM runtime probe")
    if include_legacy and pysidam_info is not None:
        print(f"legacy pysidam loaded: {pysidam_info['loaded']} ({pysidam_info['method']})")
        if pysidam_info.get("root"):
            print(f"legacy pysidam root: {pysidam_info['root']}")
        if pysidam_info.get("git"):
            git = pysidam_info["git"]
            if git.get("head"):
                print(f"legacy pysidam git head: {git.get('head')}")
            if git.get("origin_main"):
                print(f"legacy pysidam origin/main: {git.get('origin_main')}")
            if git.get("status_short"):
                print("legacy pysidam status: dirty")

    for item in module_results:
        state = "OK" if item["ok"] else "MISSING"
        detail = item.get("version") or item.get("file") or item.get("error", "")
        print(f"{item['module']} [{item['tier']}]: {state} {detail}".rstrip())

    print("AI atom detection: planned integration; not required by the default runtime")
    print("capabilities:")
    for key, value in result["capabilities"].items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
