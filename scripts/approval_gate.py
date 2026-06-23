#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pysidam_agent_core.approval import (
    ApprovalValidationError,
    load_json,
    render_review_html,
    validate_decision,
    validate_proposal,
    validate_report_links_decision,
)


def cmd_validate_proposal(args: argparse.Namespace) -> int:
    validate_proposal(load_json(args.proposal))
    print(f"PASS: valid approval proposal: {args.proposal}")
    return 0


def cmd_validate_decision(args: argparse.Namespace) -> int:
    validate_decision(load_json(args.decision))
    print(f"PASS: valid approval decision: {args.decision}")
    return 0


def cmd_validate_report(args: argparse.Namespace) -> int:
    report = load_json(args.report)
    validate_report_links_decision(report, expected_decision_path=args.decision_path)
    print(f"PASS: report links approved decision: {args.report}")
    return 0


def cmd_render_html(args: argparse.Namespace) -> int:
    proposal = load_json(args.proposal)
    template_text = None
    if args.template:
        template_text = Path(args.template).expanduser().read_text(encoding="utf-8")
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_review_html(proposal, template_text=template_text), encoding="utf-8")
    print(f"PASS: wrote approval review HTML: {output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and render STM/SJTM approval gate artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate-proposal", help="Validate approval_proposal.json")
    p.add_argument("--proposal", required=True, help="Path to approval_proposal.json")
    p.set_defaults(func=cmd_validate_proposal)

    p = sub.add_parser("validate-decision", help="Validate approval_decision.json")
    p.add_argument("--decision", required=True, help="Path to approval_decision.json")
    p.set_defaults(func=cmd_validate_decision)

    p = sub.add_parser("validate-report", help="Validate that a report links an approval decision")
    p.add_argument("--report", required=True, help="Path to analysis report.json")
    p.add_argument("--decision-path", default=None, help="Expected approval.decision_path value")
    p.set_defaults(func=cmd_validate_report)

    p = sub.add_parser("render-html", help="Render a static approval review page")
    p.add_argument("--proposal", required=True, help="Path to approval_proposal.json")
    p.add_argument("--output", required=True, help="Path to output HTML")
    p.add_argument("--template", default=str(ROOT / "assets" / "approval-gate-template.html"))
    p.set_defaults(func=cmd_render_html)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ApprovalValidationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
