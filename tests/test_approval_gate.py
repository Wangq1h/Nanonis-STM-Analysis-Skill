from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from pysidam_agent_core.approval import (
    ApprovalValidationError,
    render_review_html,
    validate_decision,
    validate_proposal,
    validate_report_links_decision,
)


def valid_proposal() -> dict:
    return {
        "schema_version": 1,
        "gate_type": "q_selection",
        "status": "pending_approval",
        "question": "Approve q vectors and lock-in sigma before phase analysis?",
        "agent_recommendation": {
            "q_vectors": {
                "x_plus": {"qx_cycles_per_nm": 2.2727, "qy_cycles_per_nm": 0.0}
            },
            "sigma_px": 3.0,
            "window": "Hanning",
        },
        "alternatives": [
            {
                "label": "off_axis_candidate",
                "parameters": {"qx_cycles_per_nm": 2.2727, "qy_cycles_per_nm": 0.2273},
                "reason": "Nearby FFT candidate has stronger target-map amplitude.",
            }
        ],
        "evidence": {
            "figures": ["figures/fft_candidates.png"],
            "tables": ["tables/fft_peak_candidates.csv"],
            "source_reports": ["report.json"],
        },
        "risks": ["q selection is pixel-limited by the finite map size"],
        "approval_options": ["approve", "modify", "reject"],
    }


class ApprovalGateTests(unittest.TestCase):
    def test_valid_q_selection_proposal_passes(self) -> None:
        proposal = validate_proposal(valid_proposal())
        self.assertEqual(proposal["gate_type"], "q_selection")

    def test_invalid_gate_type_fails(self) -> None:
        proposal = valid_proposal()
        proposal["gate_type"] = "crop_qc"
        with self.assertRaises(ApprovalValidationError):
            validate_proposal(proposal)

    def test_valid_decision_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proposal_path = Path(tmp) / "approval_proposal.json"
            proposal_path.write_text(json.dumps(valid_proposal()), encoding="utf-8")
            decision = {
                "schema_version": 1,
                "proposal_path": str(proposal_path),
                "decision": "approved",
                "approved_parameters": valid_proposal()["agent_recommendation"],
                "user_modifications": {},
                "approval_source": "chat",
                "approved_by": "user",
                "approved_at": "2026-06-23T00:00:00+08:00",
            }
            out = validate_decision(decision)
            self.assertEqual(out["decision"], "approved")

    def test_report_requires_decision_reference(self) -> None:
        report = {"approval": {"decision_path": "approval_decision.json"}}
        validate_report_links_decision(report, expected_decision_path="approval_decision.json")
        with self.assertRaises(ApprovalValidationError):
            validate_report_links_decision({"approval": {}}, expected_decision_path="approval_decision.json")

    def test_render_review_html_contains_question(self) -> None:
        html = render_review_html(valid_proposal())
        self.assertIn("Approve q vectors", html)
        self.assertIn("q_selection", html)


if __name__ == "__main__":
    unittest.main()
