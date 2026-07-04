from __future__ import annotations

import unittest

import numpy as np

from pysidam_agent_core.phase_lockin import q_cycles_to_pysidam_px_yx, run_pysidam_lockin


class PhaseLockinCoreTests(unittest.TestCase):
    def test_q_cycles_convert_to_pysidam_absolute_pixels(self) -> None:
        q_px = q_cycles_to_pysidam_px_yx(
            q_xy_cycles_per_nm=(1.667, 0.233),
            shape_yx=(128, 128),
            scan_size_nm_xy=(30.0, 30.0),
        )

        self.assertAlmostEqual(q_px[0], 63.5 + 0.233 * 30.0)
        self.assertAlmostEqual(q_px[1], 63.5 + 1.667 * 30.0)

    def test_run_pysidam_lockin_emits_standard_maps_and_engine(self) -> None:
        image = np.arange(16, dtype=float).reshape(4, 4)
        calls = []

        def fake_engine(layer, q_px, sigma_px, window, unwrap_phase):
            calls.append(
                {
                    "shape": tuple(layer.shape),
                    "q_px": list(q_px),
                    "sigma_px": sigma_px,
                    "window": window,
                    "unwrap_phase": unwrap_phase,
                }
            )
            amp = np.full(layer.shape, 2.0)
            phase = np.full(layer.shape, 0.25)
            field = np.ones(layer.shape, dtype=complex) * (1 + 2j)
            return amp, phase, field

        def fake_unwrap(phase):
            return np.asarray(phase) + 1.0

        package = run_pysidam_lockin(
            image,
            q_vectors_xy_cycles_per_nm={"q1": (0.25, 0.0)},
            scan_size_nm_xy=(4.0, 4.0),
            sigma_px=2.5,
            window="hann",
            threshold_fractions=(0.2, 0.5),
            engine=fake_engine,
            unwrap_func=fake_unwrap,
        )

        self.assertEqual(package["metadata"]["lockin_engine"], "pysidam.qpi_analysis.qpi_phase_analysis.lockin_phase_extraction")
        self.assertEqual(calls[0]["shape"], (4, 4))
        self.assertEqual(calls[0]["q_px"], [1.5, 2.5])
        self.assertEqual(calls[0]["sigma_px"], 2.5)
        self.assertEqual(calls[0]["window"], "hann")
        self.assertFalse(calls[0]["unwrap_phase"])
        self.assertIn("q1_amp", package["maps"])
        self.assertIn("q1_phase_wrapped", package["maps"])
        self.assertIn("q1_phase_unwrapped", package["maps"])
        self.assertIn("q1_complex", package["maps"])
        self.assertIn("q1_mask_amp_0p2", package["maps"])
        self.assertTrue(np.all(package["maps"]["q1_mask_amp_0p2"]))
        self.assertAlmostEqual(float(package["maps"]["q1_phase_unwrapped"][0, 0]), 1.25)


if __name__ == "__main__":
    unittest.main()
