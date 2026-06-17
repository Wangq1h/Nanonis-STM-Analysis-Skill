#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sys


SKILL_NAME = "stm-sjtm-data-processing"
SOURCE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser() / "skills" / SKILL_NAME
EXCLUDE_NAMES = {".git", "__pycache__", ".DS_Store"}


def die(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def safe_target(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    home = Path.home().resolve()
    if resolved == home or resolved == Path("/"):
        die(f"Refusing unsafe install target: {resolved}")
    if not is_relative_to(resolved, home):
        die(f"Install target must be under the current user's home directory: {resolved}")
    if resolved.name != SKILL_NAME:
        die(f"Install target must end with {SKILL_NAME}: {resolved}")
    return resolved


def remove_installed_git(target: Path, dry_run: bool) -> None:
    git_dir = target / ".git"
    if not git_dir.exists():
        return
    if not git_dir.is_dir():
        die(f"Refusing to remove non-directory .git path: {git_dir}")
    if dry_run:
        print(f"Would remove installed Git metadata: {git_dir}")
        return
    shutil.rmtree(git_dir)
    print(f"Removed installed Git metadata: {git_dir}")


def should_exclude(path: Path) -> bool:
    return any(part in EXCLUDE_NAMES for part in path.parts)


def copy_tree(source: Path, target: Path, dry_run: bool) -> None:
    source = source.resolve()
    target = safe_target(target)
    if source == target:
        die("Source and target are the same path.")
    if dry_run:
        print(f"Would sync {source} -> {target}")
        return

    target.mkdir(parents=True, exist_ok=True)
    remove_installed_git(target, dry_run=False)

    seen: set[Path] = set()
    for src in source.rglob("*"):
        rel = src.relative_to(source)
        if should_exclude(rel):
            continue
        dst = target / rel
        seen.add(dst)
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    for dst in sorted(target.rglob("*"), reverse=True):
        rel = dst.relative_to(target)
        if should_exclude(rel):
            continue
        if dst not in seen and dst != target:
            if dst.is_dir():
                try:
                    dst.rmdir()
                except OSError:
                    pass
            else:
                dst.unlink()
    print(f"Synced installed skill without Git metadata: {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync this skill into the local Codex skills directory (~/.codex/skills).")
    parser.add_argument("--source", default=str(SOURCE_ROOT), help="Source skill repository root.")
    parser.add_argument("--target", default=str(DEFAULT_TARGET), help="Installed skill target directory.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned sync without modifying files.")
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    target = Path(args.target).expanduser()
    if not (source / "SKILL.md").is_file():
        die(f"Source does not look like a skill root: {source}")
    if args.dry_run:
        remove_installed_git(safe_target(target), dry_run=True)
    copy_tree(source, target, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
