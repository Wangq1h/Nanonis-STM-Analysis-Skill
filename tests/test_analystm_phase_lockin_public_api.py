from __future__ import annotations

import unittest

import numpy as np

import analystm
from analystm.phase_lockin import run_lockin_phase, run_pysidam_lockin


class AnalySTMPhaseLockinPublicApiTests(unittest.TestCase):
    def test_run_lockin_phase_is_primary_api_with_legacy_alias(self) -> None:
        self.assertIs(run_pysidam_lockin, run_lockin_phase)
        self.assertIs(analystm.run_lockin_phase, run_lockin_phase)

        def fake_engine(layer, q_px, sigma_px, window, unwrap_phase):
            amp = np.full(layer.shape, 2.0)
            phase = np.full(layer.shape, 0.25)
            field = np.ones(layer.shape, dtype=complex)
            return amp, phase, field

        package = run_lockin_phase(
            np.arange(16, dtype=float).reshape(4, 4),
            q_vectors_xy_cycles_per_nm={"q1": (0.25, 0.0)},
            scan_size_nm_xy=(4.0, 4.0),
            engine=fake_engine,
            unwrap_func=lambda phase: np.asarray(phase),
        )

        self.assertEqual(package["metadata"]["lockin_engine"], "analystm.phase_lockin.lockin_phase_extraction")
        self.assertIn("q1_phase_wrapped", package["maps"])


if __name__ == "__main__":
    unittest.main()
