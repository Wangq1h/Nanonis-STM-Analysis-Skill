from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
GATE_TYPES = {"fit_window", "q_selection", "peak_count"}
PROPOSAL_STATUSES = {"pending_approval", "user_preapproved"}
DECISIONS = {"approved", "modified", "rejected", "user_preapproved"}
APPROVAL_OPTIONS = {"approve", "modify", "reject"}


class ApprovalValidationError(ValueError):
    """Raised when an approval gate artifact is invalid."""


def _require_dict(payload: Any, label: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ApprovalValidationError(f"{label} must be a JSON object")
    return payload


def _require_key(payload: dict[str, Any], key: str) -> Any:
    if key not in payload:
        raise ApprovalValidationError(f"missing required key: {key}")
    return payload[key]


def _require_nonempty_string(payload: dict[str, Any], key: str) -> str:
    value = _require_key(payload, key)
    if not isinstance(value, str) or not value.strip():
        raise ApprovalValidationError(f"{key} must be a non-empty string")
    return value


def _require_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = _require_key(payload, key)
    if not isinstance(value, list):
        raise ApprovalValidationError(f"{key} must be a list")
    return value


def _require_dict_key(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = _require_key(payload, key)
    if not isinstance(value, dict):
        raise ApprovalValidationError(f"{key} must be an object")
    return value


def load_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path).expanduser()
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ApprovalValidationError(f"{file_path} is not valid JSON: {exc}") from exc
    return _require_dict(payload, str(file_path))


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    file_path = Path(path).expanduser()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_proposal(payload: dict[str, Any]) -> dict[str, Any]:
    proposal = _require_dict(payload, "approval proposal")
    if _require_key(proposal, "schema_version") != SCHEMA_VERSION:
        raise ApprovalValidationError(f"schema_version must be {SCHEMA_VERSION}")
    gate_type = _require_nonempty_string(proposal, "gate_type")
    if gate_type not in GATE_TYPES:
        raise ApprovalValidationError(f"gate_type must be one of {sorted(GATE_TYPES)}")
    status = _require_nonempty_string(proposal, "status")
    if status not in PROPOSAL_STATUSES:
        raise ApprovalValidationError(f"status must be one of {sorted(PROPOSAL_STATUSES)}")
    _require_nonempty_string(proposal, "question")
    _require_dict_key(proposal, "agent_recommendation")
    _require_list(proposal, "alternatives")
    evidence = _require_dict_key(proposal, "evidence")
    for key in ("figures", "tables", "source_reports"):
        if key not in evidence:
            evidence[key] = []
        if not isinstance(evidence[key], list):
            raise ApprovalValidationError(f"evidence.{key} must be a list")
    _require_list(proposal, "risks")
    options = set(str(item) for item in _require_list(proposal, "approval_options"))
    missing = APPROVAL_OPTIONS - options
    if missing:
        raise ApprovalValidationError(f"approval_options missing: {sorted(missing)}")
    return proposal


def validate_decision(payload: dict[str, Any]) -> dict[str, Any]:
    decision = _require_dict(payload, "approval decision")
    if _require_key(decision, "schema_version") != SCHEMA_VERSION:
        raise ApprovalValidationError(f"schema_version must be {SCHEMA_VERSION}")
    _require_nonempty_string(decision, "proposal_path")
    value = _require_nonempty_string(decision, "decision")
    if value not in DECISIONS:
        raise ApprovalValidationError(f"decision must be one of {sorted(DECISIONS)}")
    _require_dict_key(decision, "approved_parameters")
    _require_dict_key(decision, "user_modifications")
    _require_nonempty_string(decision, "approval_source")
    _require_nonempty_string(decision, "approved_by")
    _require_nonempty_string(decision, "approved_at")
    return decision


def validate_report_links_decision(report: dict[str, Any], expected_decision_path: str | None = None) -> None:
    data = _require_dict(report, "execution report")
    approval = data.get("approval")
    if not isinstance(approval, dict):
        raise ApprovalValidationError("report must contain approval object")
    decision_path = approval.get("decision_path")
    if not isinstance(decision_path, str) or not decision_path.strip():
        raise ApprovalValidationError("report approval.decision_path must be a non-empty string")
    if expected_decision_path and decision_path != expected_decision_path:
        raise ApprovalValidationError(
            f"report approval.decision_path {decision_path!r} does not match {expected_decision_path!r}"
        )


def _html_list(items: list[Any]) -> str:
    if not items:
        return "<li>None recorded.</li>"
    return "\n".join(f"<li>{html.escape(str(item))}</li>" for item in items)


def render_review_html(proposal: dict[str, Any], template_text: str | None = None) -> str:
    data = validate_proposal(dict(proposal))
    recommendation_json = html.escape(json.dumps(data["agent_recommendation"], ensure_ascii=False, indent=2))
    alternatives_json = html.escape(json.dumps(data["alternatives"], ensure_ascii=False, indent=2))
    evidence = data["evidence"]
    values = {
        "question": html.escape(data["question"]),
        "gate_type": html.escape(data["gate_type"]),
        "status": html.escape(data["status"]),
        "recommendation_json": recommendation_json,
        "alternatives_json": alternatives_json,
        "risks_html": _html_list(data["risks"]),
        "evidence_html": _html_list(
            evidence.get("figures", []) + evidence.get("tables", []) + evidence.get("source_reports", [])
        ),
    }
    if template_text is None:
        template_text = DEFAULT_TEMPLATE
    out = template_text
    for key, value in values.items():
        out = out.replace("{{ " + key + " }}", value)
    return out


DEFAULT_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>STM/SJTM Approval Gate</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; line-height: 1.45; color: #1f2933; }
    main { max-width: 980px; margin: 0 auto; }
    pre { background: #f4f6f8; border: 1px solid #d9e2ec; padding: 12px; overflow-x: auto; }
    section { border-top: 1px solid #d9e2ec; padding-top: 18px; margin-top: 18px; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #e0f2fe; color: #075985; font-size: 13px; }
  </style>
</head>
<body>
  <main>
    <h1>{{ question }}</h1>
    <p><span class="badge">{{ gate_type }}</span> <span class="badge">{{ status }}</span></p>
    <section><h2>Agent Recommendation</h2><pre>{{ recommendation_json }}</pre></section>
    <section><h2>Alternatives</h2><pre>{{ alternatives_json }}</pre></section>
    <section><h2>Evidence</h2><ul>{{ evidence_html }}</ul></section>
    <section><h2>Risks</h2><ul>{{ risks_html }}</ul></section>
    <section><h2>Approval Instructions</h2><p>Reply with approve, modify, or reject. If modifying, provide exact parameter values.</p></section>
  </main>
</body>
</html>
"""
