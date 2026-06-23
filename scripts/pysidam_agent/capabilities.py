#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


try:
    from .common import SKILL_ROOT
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from pysidam_agent.common import SKILL_ROOT


INDEX = SKILL_ROOT / "references" / "pysidam-capability-index.json"


def load_index() -> dict:
    return json.loads(INDEX.read_text(encoding="utf-8"))


def iter_capabilities(index: dict):
    for domain in index.get("domains", []):
        domain_name = domain.get("domain", "")
        for capability in domain.get("capabilities", []):
            item = dict(capability)
            item["domain"] = domain_name
            yield item


def matches_query(item: dict, query: str) -> bool:
    if not query:
        return True
    needle = str(query).strip().lower()
    haystack_parts = []
    for key in ("name", "domain", "module", "api", "status", "bridge", "notes", "contract"):
        value = item.get(key, "")
        if value:
            haystack_parts.append(str(value))
    for key in ("formats", "models", "requires"):
        value = item.get(key, [])
        if isinstance(value, list):
            haystack_parts.extend(str(part) for part in value)
    return needle in " ".join(haystack_parts).lower()


def main() -> int:
    parser = argparse.ArgumentParser(description="Query the PySIDAM capability index.")
    parser.add_argument("--domain", default="", help="Filter by domain id.")
    parser.add_argument("--status", default="", help="Filter by capability status.")
    parser.add_argument("--query", default="", help="Keyword search over capability names, modules, APIs, notes, bridges, formats, and requirements.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table.")
    args = parser.parse_args()

    index = load_index()
    rows = []
    for item in iter_capabilities(index):
        if args.domain and item.get("domain") != args.domain:
            continue
        if args.status and item.get("status") != args.status:
            continue
        if args.query and not matches_query(item, args.query):
            continue
        rows.append(item)

    if args.json:
        print(json.dumps({"index": INDEX.name, "count": len(rows), "capabilities": rows}, ensure_ascii=False, indent=2))
        return 0

    print(f"PySIDAM capability index: {index.get('pysidam_commit', '')}")
    for item in rows:
        module = item.get("module", "")
        api = item.get("api", "")
        bridge = item.get("bridge", "")
        suffix = f" -> {bridge}" if bridge else ""
        print(f"{item.get('domain', '')}\t{item.get('status', '')}\t{module}:{api}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
