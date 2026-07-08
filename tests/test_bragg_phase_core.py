from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

import numpy as np

from analystm.cli.main import main as analystm_main
from pysidam_agent_core.bragg_phase import (
    find_peak_in_roi,
    q_axes_cycles_per_nm,
    q_selection_policy,
)


class BraggPhaseCoreTests(unittest.TestCase):
    def test_q_axes_use_scan_size_and_fft_shift_order(self) -> None:
        qx, qy = q_axes_cycles_per_nm((4, 4), (4.0, 2.0))

        np.testing.assert_allclose(qx, [-0.5, -0.25, 0.0, 0.25])
        np.testing.assert_allclose(qy, [-1.0, -0.5, 0.0, 0.5])

    def test_find_peak_in_user_roi_reports_plus_minus_symmetric_peak(self) -> None:
        log_amp = np.zeros((5, 5), dtype=float)
        log_amp[4, 2] = 7.0
        log_amp[0, 2] = 7.0
        qx_axis = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
        qy_axis = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])

        plus = find_peak_in_roi(
            log_amp,
            qx_axis,
            qy_axis,
            {"qx_min": -0.5, "qx_max": 0.5, "qy_min": 1.5, "qy_max": 2.5},
            sign=1,
        )
        minus = find_peak_in_roi(
            log_amp,
            qx_axis,
            qy_axis,
            {"qx_min": -0.5, "qx_max": 0.5, "qy_min": 1.5, "qy_max": 2.5},
            sign=-1,
        )

        self.assertEqual(plus["offset_px_yx"], [2, 0])
        self.assertEqual(minus["offset_px_yx"], [-2, 0])
        self.assertEqual(plus["q_cycles_per_nm_xy"], [0.0, 2.0])
        self.assertEqual(minus["q_cycles_per_nm_xy"], [0.0, -2.0])

    def test_phase_analysis_without_user_q_or_roi_must_ask_before_agent_search(self) -> None:
        policy = q_selection_policy(user_q=None, user_roi=None, allow_agent_search=False)

        self.assertEqual(policy["mode"], "ask_user_before_search")
        self.assertIn("user-specified", policy["message"])

    def test_user_supplied_q_or_roi_has_priority(self) -> None:
        q_policy = q_selection_policy(user_q=[2.5, 0.0], user_roi=None, allow_agent_search=False)
        roi_policy = q_selection_policy(
            user_q=None,
            user_roi={"qx_min": -0.5, "qx_max": 0.5, "qy_min": 2.0, "qy_max": 3.0},
            allow_agent_search=False,
        )

        self.assertEqual(q_policy["mode"], "user_preapproved_q")
        self.assertEqual(roi_policy["mode"], "user_preferred_roi")

    def test_cli_agent_search_policy_is_not_misread_as_user_q(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bragg_policy.json"
            rc = analystm_main(["bragg", "policy", "--allow-agent-search", "--output-json", str(out)])

            self.assertEqual(rc, 0)
            policy = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(policy["mode"], "agent_proposal_required")


if __name__ == "__main__":
    unittest.main()
