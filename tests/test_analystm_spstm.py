from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


class AnalySTMSPSTMTests(unittest.TestCase):
    def test_didv_contrast_pipeline_symmetry_and_max_normalization(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.spstm import process_didv_contrast
        finally:
            sys.path.remove(str(SRC))

        x = np.linspace(-2.0, 2.0, 41)
        y_a = 2.0 + np.exp(-((x - 0.5) ** 2) / 0.08)
        y_b = 1.0 + 0.5 * np.exp(-((x + 0.5) ** 2) / 0.10)
        package = process_didv_contrast(
            x,
            y_a,
            y_b=y_b,
            symmetrize=True,
            norm_mode_a="Max",
            norm_mode_b="Max",
        )

        self.assertEqual(package["algorithm"]["engine"], "analystm.spstm.process_didv_contrast")
        self.assertIn("SPSTMDidVContrastWindow.run_pipeline", package["algorithm"]["pysidam_source_mapping"])
        self.assertLessEqual(float(np.nanmax(np.abs(package["y_a"]))), 1.0 + 1e-12)
        self.assertLessEqual(float(np.nanmax(np.abs(package["y_b"]))), 1.0 + 1e-12)
        np.testing.assert_allclose(package["x"], x)

    def test_qpi_r90_and_spin_contrast_match_pysidam_formulae(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.spstm import build_qpi_r90_contrast, build_qpi_spin_contrast
        finally:
            sys.path.remove(str(SRC))

        arr = np.arange(16, dtype=float).reshape(4, 4)
        r90 = build_qpi_r90_contrast(arr, operation="diff", rotation="ccw")
        expected_rot = np.rot90(arr, 1)
        expected_norm = r90["bragg_norm"]
        np.testing.assert_allclose(r90["result"], (arr - expected_rot) / expected_norm)
        self.assertIn("SPSTMQPIContrastWindow._build_result", r90["algorithm"]["pysidam_source_mapping"])

        pos = np.ones((4, 4), dtype=float) * 3.0
        neg = np.ones((5, 5), dtype=float)
        spin = build_qpi_spin_contrast(pos, neg)
        self.assertEqual(spin["contrast"].shape, (4, 4))
        np.testing.assert_allclose(spin["contrast"], 2.0)
        np.testing.assert_allclose(spin["average"], 4.0)

    def test_linecut_sampling_and_profile_normalization(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.spstm import normalize_profile, sample_linecut
        finally:
            sys.path.remove(str(SRC))

        data = np.arange(25, dtype=float).reshape(5, 5)
        dist, prof = sample_linecut(data, scan_size_nm=4.0, p1_nm=(0.0, 0.0), p2_nm=(4.0, 4.0))
        self.assertEqual(dist.shape, prof.shape)
        self.assertGreaterEqual(dist.size, 5)
        self.assertAlmostEqual(float(prof[0]), 0.0)
        self.assertAlmostEqual(float(prof[-1]), 24.0)
        norm = normalize_profile(np.array([1.0, 2.0, 3.0]))
        np.testing.assert_allclose(norm, [-1.0, 0.0, 1.0])

    def test_spstm_cli_writes_didv_and_qpi_reports(self) -> None:
        env = {"PYTHONPATH": str(SRC)}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            didv_in = root / "didv.npz"
            qpi_in = root / "qpi.npz"
            x = np.linspace(-2.0, 2.0, 41)
            y_a = 2.0 + np.exp(-((x - 0.5) ** 2) / 0.08)
            y_b = 1.0 + 0.5 * np.exp(-((x + 0.5) ** 2) / 0.10)
            np.savez_compressed(didv_in, x=x, a=y_a, b=y_b)
            np.savez_compressed(qpi_in, qpi=np.arange(16, dtype=float).reshape(4, 4), pos=np.ones((4, 4)) * 3, neg=np.ones((4, 4)))

            didv_dir = root / "didv_out"
            didv_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "analystm",
                    "spstm",
                    "didv",
                    str(didv_in),
                    "--x-key",
                    "x",
                    "--a-key",
                    "a",
                    "--b-key",
                    "b",
                    "--norm-mode-a",
                    "Max",
                    "--norm-mode-b",
                    "Max",
                    "--output-dir",
                    str(didv_dir),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(didv_proc.returncode, 0, didv_proc.stderr)
            didv_report = json.loads((didv_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(didv_report["tool"], "analystm spstm didv")

            qpi_dir = root / "qpi_out"
            qpi_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "analystm",
                    "spstm",
                    "qpi-r90",
                    str(qpi_in),
                    "--map-key",
                    "qpi",
                    "--output-dir",
                    str(qpi_dir),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(qpi_proc.returncode, 0, qpi_proc.stderr)
            qpi_report = json.loads((qpi_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(qpi_report["tool"], "analystm spstm qpi-r90")


if __name__ == "__main__":
    unittest.main()
