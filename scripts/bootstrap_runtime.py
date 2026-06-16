#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = SKILL_ROOT / "runtime"
DEFAULT_GROUPS = ("core", "nanonis", "ibw")
GROUP_REQUIREMENTS = {
    "core": RUNTIME_DIR / "requirements-core.txt",
    "nanonis": RUNTIME_DIR / "requirements-nanonis.txt",
    "ibw": RUNTIME_DIR / "requirements-ibw.txt",
    "ai": RUNTIME_DIR / "requirements-ai.txt",
    "ui": RUNTIME_DIR / "requirements-ui.txt",
}
GROUP_ALIASES = {
    "headless": DEFAULT_GROUPS,
    "all": ("core", "nanonis", "ibw", "ai", "ui"),
}
CONSTRAINTS_FILE = RUNTIME_DIR / "constraints.txt"
DEFAULT_CACHE_DIR = Path(os.environ.get("STM_SJTM_SKILL_CACHE", "~/.cache/stm-sjtm-data-processing")).expanduser()
RUNTIME_JSON = "runtime.json"


def die(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def assert_not_root() -> None:
    geteuid = getattr(os, "geteuid", None)
    if geteuid is not None and geteuid() == 0:
        die("Refusing to bootstrap as root. Re-run as a normal user.")


def assert_safe_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved == Path("/"):
        die("Refusing to use filesystem root as a runtime path.")

    forbidden = [
        Path("/usr"),
        Path("/bin"),
        Path("/sbin"),
        Path("/System"),
        Path("/Library"),
        Path("/Applications"),
        Path("/opt/homebrew"),
        Path("/opt/local"),
        Path("/opt/conda"),
    ]
    for item in forbidden:
        if resolved == item or is_relative_to(resolved, item):
            die(f"Refusing to write runtime environment under system path: {resolved}")

    home = Path.home().resolve()
    skill_root = SKILL_ROOT.resolve()
    if not (is_relative_to(resolved, home) or is_relative_to(resolved, skill_root)):
        die(f"Runtime path must be user-writable and under the home directory or skill root: {resolved}")
    return resolved


def parse_groups(raw: str) -> list[str]:
    requested: list[str] = []
    for part in raw.replace(";", ",").replace(" ", ",").split(","):
        key = part.strip().lower()
        if not key:
            continue
        if key in GROUP_ALIASES:
            requested.extend(GROUP_ALIASES[key])
        else:
            requested.append(key)

    unknown = [group for group in requested if group not in GROUP_REQUIREMENTS]
    if unknown:
        die("Unknown dependency group(s): " + ", ".join(sorted(set(unknown))))

    ordered: list[str] = []
    for group in requested:
        if group not in ordered:
            ordered.append(group)
    return ordered or list(DEFAULT_GROUPS)


def requirement_files(groups: list[str]) -> list[Path]:
    files = [GROUP_REQUIREMENTS[group] for group in groups]
    missing = [str(path.relative_to(SKILL_ROOT)) for path in files if not path.is_file()]
    if missing:
        die("Missing requirement files: " + ", ".join(missing))
    if not CONSTRAINTS_FILE.is_file():
        die("Missing constraints file: runtime/constraints.txt")
    return files


def lock_hash(groups: list[str], python_path: str, files: list[Path]) -> str:
    h = hashlib.sha256()
    h.update(("python=" + python_path).encode("utf-8"))
    h.update(("groups=" + ",".join(groups)).encode("utf-8"))
    for path in [CONSTRAINTS_FILE, *files]:
        h.update(str(path.relative_to(SKILL_ROOT)).encode("utf-8"))
        h.update(path.read_bytes())
    return h.hexdigest()[:12]


def safe_venv_path(cache_dir: Path, groups: list[str], python_path: str, files: list[Path]) -> Path:
    tag = f"py{sys.version_info.major}{sys.version_info.minor}-{platform.system().lower()}-{platform.machine().lower()}"
    group_name = "-".join(groups)
    return assert_safe_path(cache_dir / "venvs" / f"{tag}-{group_name}-{lock_hash(groups, python_path, files)}")


def venv_python(venv_path: Path) -> Path:
    if os.name == "nt":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def run_command(cmd: list[str], dry_run: bool) -> None:
    print("+ " + " ".join(cmd))
    if dry_run:
        return
    subprocess.check_call(cmd)


def ensure_venv(base_python: str, venv_path: Path, recreate: bool, dry_run: bool) -> Path:
    assert_safe_path(venv_path)
    pyvenv = venv_path / "pyvenv.cfg"
    if recreate and venv_path.exists():
        if not pyvenv.is_file():
            die(f"Refusing to recreate path that is not a Python venv: {venv_path}")
        if dry_run:
            print(f"Would remove existing venv: {venv_path}")
        else:
            shutil.rmtree(venv_path)

    if not pyvenv.is_file():
        run_command([base_python, "-m", "venv", str(venv_path)], dry_run)

    python = venv_python(venv_path)
    if not dry_run and not python.is_file():
        die(f"Venv Python was not created: {python}")
    return python


def install_requirements(
    python: Path,
    files: list[Path],
    wheelhouse: Path | None,
    no_network: bool,
    dry_run: bool,
) -> None:
    if no_network and wheelhouse is None:
        print("Skipping pip install because --no-network was set and no --wheelhouse was provided.")
        return

    base = [str(python), "-m", "pip", "install"]
    if not no_network:
        run_command([*base, "--upgrade", "pip", "setuptools", "wheel"], dry_run)

    cmd = [*base, "-c", str(CONSTRAINTS_FILE)]
    if wheelhouse is not None:
        wheelhouse = assert_safe_path(wheelhouse)
        cmd.extend(["--find-links", str(wheelhouse)])
    if no_network:
        cmd.append("--no-index")
    for path in files:
        cmd.extend(["-r", str(path)])
    run_command(cmd, dry_run)


def looks_like_pysidam_source(root: Path) -> bool:
    return (root / "pysidam" / "core" / "nanonis_io.py").is_file()


def candidate_pysidam_roots(explicit: list[str]) -> list[Path]:
    roots: list[Path] = []
    for item in explicit:
        if item:
            roots.append(Path(item).expanduser())
    env_root = os.environ.get("PYSIDAM_ROOT")
    if env_root:
        roots.append(Path(env_root).expanduser())
    for base in [Path.cwd(), SKILL_ROOT, SKILL_ROOT.parent]:
        roots.extend(
            [
                base,
                base / "pysidam",
                base / "pysidam-origin-main",
                base.parent / "pysidam",
                base.parent / "pysidam-origin-main",
            ]
        )

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


def find_pysidam_source(explicit: list[str]) -> Path | None:
    for root in candidate_pysidam_roots(explicit):
        if looks_like_pysidam_source(root):
            return root
    return None


def git_is_clean(repo: Path) -> bool:
    output = subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"], text=True)
    return output.strip() == ""


def ensure_pysidam_source(
    explicit: list[str],
    mode: str,
    git_url: str,
    git_ref: str,
    cache_dir: Path,
    no_network: bool,
    dry_run: bool,
) -> Path | None:
    existing = find_pysidam_source(explicit)
    if existing is not None:
        return existing

    if mode == "none":
        return None
    if no_network:
        print("PySIDAM source not found; skipping clone because --no-network was set.")
        return None

    target = assert_safe_path(cache_dir / "src" / "pysidam")
    if dry_run:
        print(f"Would clone or update PySIDAM source at: {target}")
        return target

    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        run_command(["git", "clone", git_url, str(target)], dry_run=False)
    elif not looks_like_pysidam_source(target):
        die(f"Managed PySIDAM cache exists but does not look like PySIDAM source: {target}")

    if (target / ".git").is_dir():
        if not git_is_clean(target):
            die(f"Managed PySIDAM cache is dirty; refusing to modify it: {target}")
        run_command(["git", "-C", str(target), "fetch", "origin", "--prune"], dry_run=False)
        run_command(["git", "-C", str(target), "checkout", "--detach", git_ref], dry_run=False)
    return target


def run_probe(python: Path, pysidam_root: Path | None, dry_run: bool) -> dict[str, Any]:
    cmd = [str(python), str(SKILL_ROOT / "scripts" / "probe_runtime.py"), "--json"]
    if pysidam_root is not None:
        cmd.extend(["--pysidam-root", str(pysidam_root)])
    print("+ " + " ".join(cmd))
    if dry_run:
        return {"dry_run": True, "command": cmd}
    output = subprocess.check_output(cmd, text=True)
    return json.loads(output)


def write_runtime_json(
    cache_dir: Path,
    venv_path: Path,
    python: Path,
    groups: list[str],
    req_files: list[Path],
    pysidam_root: Path | None,
    probe: dict[str, Any],
    dry_run: bool,
) -> Path:
    payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "skill_root": str(SKILL_ROOT),
        "cache_dir": str(cache_dir),
        "venv_path": str(venv_path),
        "python": str(python),
        "groups": groups,
        "requirements": [str(path.relative_to(SKILL_ROOT)) for path in req_files],
        "constraints": str(CONSTRAINTS_FILE.relative_to(SKILL_ROOT)),
        "pysidam_root": str(pysidam_root) if pysidam_root is not None else "",
        "probe": probe,
    }
    path = cache_dir / RUNTIME_JSON
    print(f"runtime.json: {path}")
    if not dry_run:
        cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an isolated STM/SJTM skill Python runtime.")
    parser.add_argument("--groups", default=",".join(DEFAULT_GROUPS), help="Comma-separated groups: core,nanonis,ibw,ai,ui,headless,all.")
    parser.add_argument("--python", default=sys.executable, help="Base Python used to create the venv.")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="User-writable cache directory.")
    parser.add_argument("--venv-path", default="", help="Explicit venv path. Must be user-writable and non-system.")
    parser.add_argument("--wheelhouse", default="", help="Optional local wheelhouse directory.")
    parser.add_argument("--no-network", action="store_true", help="Install only from --wheelhouse and do not clone PySIDAM.")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without changing files or installing packages.")
    parser.add_argument("--recreate", action="store_true", help="Remove and recreate the managed venv if it already exists.")
    parser.add_argument("--pysidam-root", action="append", default=[], help="Existing PySIDAM source checkout root.")
    parser.add_argument("--pysidam-mode", choices=["auto", "none"], default="auto", help="Use an existing PySIDAM source or clone one into cache.")
    parser.add_argument("--pysidam-git-url", default="https://github.com/Wangq1h/pysidam.git", help="PySIDAM git URL used by auto mode.")
    parser.add_argument("--pysidam-ref", default="origin/main", help="PySIDAM ref checked out in the managed cache.")
    args = parser.parse_args()

    assert_not_root()
    groups = parse_groups(args.groups)
    req_files = requirement_files(groups)
    cache_dir = assert_safe_path(Path(args.cache_dir))
    venv_path = assert_safe_path(Path(args.venv_path)) if args.venv_path else safe_venv_path(cache_dir, groups, args.python, req_files)
    wheelhouse = Path(args.wheelhouse).expanduser() if args.wheelhouse else None

    print("STM/SJTM runtime bootstrap")
    print("groups: " + ", ".join(groups))
    print(f"cache: {cache_dir}")
    print(f"venv: {venv_path}")

    python = ensure_venv(args.python, venv_path, recreate=args.recreate, dry_run=args.dry_run)
    install_requirements(python, req_files, wheelhouse=wheelhouse, no_network=args.no_network, dry_run=args.dry_run)
    pysidam_root = ensure_pysidam_source(
        args.pysidam_root,
        mode=args.pysidam_mode,
        git_url=args.pysidam_git_url,
        git_ref=args.pysidam_ref,
        cache_dir=cache_dir,
        no_network=args.no_network,
        dry_run=args.dry_run,
    )
    probe = run_probe(python, pysidam_root, dry_run=args.dry_run)
    write_runtime_json(cache_dir, venv_path, python, groups, req_files, pysidam_root, probe, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
