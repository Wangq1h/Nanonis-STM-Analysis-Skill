from __future__ import annotations

import unittest
import warnings
from pathlib import Path
import sys

import numpy as np
from scipy.integrate import simpson

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from analystm.deconvolution import (
    _fermi_dirac_mev,
    _fermi_dirac_prime_mev,
    compute_sis_didv_from_dos,
    dynes_dos,
    normalize_sample_dos_display,
    run_sis_didv_deconvolution,
)


class AnalySTMReplacementBackendTests(unittest.TestCase):
    def test_sis_forward_model_uses_direct_integral_not_inverse_matrix_shortcut(self) -> None:
        energy = np.linspace(-3.0, 3.0, 61)
        bias = np.linspace(-2.5, 2.5, 51)
        sample = 0.2 + np.exp(-0.5 * ((energy - 0.9) / 0.24) ** 2) + np.exp(-0.5 * ((energy + 1.1) / 0.31) ** 2)
        tip_bias = np.linspace(-5.0, 5.0, 121)
        tip_dos = dynes_dos(tip_bias, 1.2, 0.04)
        temperature_k = 0.55

        tip_derivative = np.gradient(tip_dos, tip_bias, edge_order=2)
        f_energy = _fermi_dirac_mev(energy, temperature_k)
        expected = np.empty_like(bias)
        for idx, voltage in enumerate(bias):
            shifted = energy - float(voltage)
            rho_eval = np.interp(shifted, tip_bias, tip_dos, left=float(tip_dos[0]), right=float(tip_dos[-1]))
            drho_eval = np.interp(shifted, tip_bias, tip_derivative, left=float(tip_derivative[0]), right=float(tip_derivative[-1]))
            f_shift = _fermi_dirac_mev(shifted, temperature_k)
            fp_shift = _fermi_dirac_prime_mev(shifted, temperature_k)
            integrand = sample * (-drho_eval * (f_shift - f_energy) - rho_eval * fp_shift)
            expected[idx] = float(simpson(integrand, x=energy))

        actual = compute_sis_didv_from_dos(energy, sample, bias, tip_bias, tip_dos, temperature_k)

        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)

    def test_dos_display_normalization_uses_robust_tail_window(self) -> None:
        bias = np.linspace(-3.0, 3.0, 61)
        dos = 0.1 + np.exp(-0.5 * ((bias - 1.0) / 0.3) ** 2) + np.exp(-0.5 * ((bias + 1.0) / 0.3) ** 2)

        normalized, meta = normalize_sample_dos_display(bias, dos)

        self.assertTrue(meta["enabled"])
        self.assertAlmostEqual(meta["tail_threshold_mV"], 2.1)
        self.assertAlmostEqual(meta["edge_trim_mV"], 0.4)
        self.assertEqual(meta["tail_count"], 10)
        self.assertAlmostEqual(meta["scale"], 0.10076966131136536)
        self.assertAlmostEqual(float(np.nanmax(normalized)), float(np.nanmax(dos / meta["scale"])))

    def test_deconvolution_reports_analystm_as_engine_and_pysidam_as_source_mapping(self) -> None:
        bias = np.linspace(-3.0, 3.0, 61)
        didv = 0.2 + np.exp(-0.5 * ((np.abs(bias) - 1.2) / 0.25) ** 2)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", RuntimeWarning)
            result = run_sis_didv_deconvolution(
                bias,
                didv,
                n_grid=61,
                temperature_K=0.4,
                tip_delta_meV=1.2,
                tip_gamma_meV=0.04,
                pinv_rcond=0.03,
                zero_peak_region=(-0.2, 0.2),
            )
        runtime_warnings = [item for item in caught if issubclass(item.category, RuntimeWarning)]
        self.assertEqual(runtime_warnings, [])

        algorithm = result["algorithm"]
        self.assertEqual(algorithm["engine"], "analystm.deconvolution.run_sis_didv_deconvolution")
        self.assertEqual(algorithm["name"], "AnalySTM SIS dI/dV deconvolution")
        self.assertIn("run_sis_didv_deconvolution", algorithm["pysidam_source_mapping"])
        self.assertNotIn("proxy", str(algorithm).lower())
        self.assertIn("sample_dos_raw_norm", result)
        self.assertIn("sample_dos_solve", result)
        self.assertIn("solve_mask", result)


if __name__ == "__main__":
    unittest.main()
