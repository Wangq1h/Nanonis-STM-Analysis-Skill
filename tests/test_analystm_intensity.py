from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    env.pop("PYSIDAM_ROOT", None)
    return env


def _run_analystm(args: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "analystm", *args],
        cwd=cwd,
        env=_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class AnalySTMIntensityTests(unittest.TestCase):
    def test_signal_modes_match_pysidam_gradient_logic(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.intensity import apply_intensity_signal_mode
        finally:
            sys.path.remove(str(SRC))

        bias = np.linspace(-2.0, 2.0, 9)
        data = np.vstack([bias**3 + 2.0 * bias, 0.5 * bias**2])

        didv = apply_intensity_signal_mode(bias, data, mode="didv")
        d2 = apply_intensity_signal_mode(bias, data, mode="d2")
        neg_d3 = apply_intensity_signal_mode(bias, data, mode="neg_d3")

        np.testing.assert_allclose(didv, data)
        np.testing.assert_allclose(d2, np.gradient(data, bias, axis=-1))
        np.testing.assert_allclose(neg_d3, -np.gradient(np.gradient(data, bias, axis=-1), bias, axis=-1))
        self.assertTrue(np.all(apply_intensity_signal_mode(bias[:-1], data, mode="d2") == 0.0))

    def test_process_intensity_matrix_applies_pysidam_order(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.intensity import process_intensity_matrix, remove_linear_baseline_1d, select_bias_indices_in_range
        finally:
            sys.path.remove(str(SRC))

        bias = np.linspace(-3.0, 3.0, 13)
        baseline = 0.4 * bias - 1.2
        spectra = np.vstack(
            [
                baseline + np.exp(-0.5 * ((bias - 1.0) / 0.5) ** 2),
                baseline + 2.0 + np.exp(-0.5 * ((bias + 1.0) / 0.45) ** 2),
            ]
        )

        package = process_intensity_matrix(
            bias,
            spectra,
            signal_mode="didv",
            bias_range=(-1.0, 1.0),
            remove_linear_baseline=True,
        )

        idx = select_bias_indices_in_range(bias, -1.0, 1.0)
        expected = np.vstack([remove_linear_baseline_1d(bias[idx], row[idx]) for row in spectra])
        np.testing.assert_allclose(package["processed_bias"], bias[idx])
        np.testing.assert_allclose(package["processed_data"], expected)
        self.assertEqual(package["algorithm"]["engine"], "analystm.intensity.process_intensity_matrix")
        self.assertIn("linecutmap_intensity", package["algorithm"]["pysidam_source_mapping"])

    def test_peak_align_zero_cube_migrates_bias_calibration(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.intensity import peak_align_zero_cube
        finally:
            sys.path.remove(str(SRC))

        bias = np.linspace(-3.0, 3.0, 61)
        cube = np.empty((2, 2, bias.size), dtype=float)
        offsets = np.array([[0.20, -0.10], [0.05, 0.00]])
        for y in range(2):
            for x in range(2):
                off = offsets[y, x]
                cube[y, x, :] = (
                    np.exp(-0.5 * ((bias - (1.0 + off)) / 0.08) ** 2)
                    + np.exp(-0.5 * ((bias - (-1.0 + off)) / 0.08) ** 2)
                )

        package = peak_align_zero_cube(bias, cube, neg_window=(-1.4, -0.6), pos_window=(0.6, 1.4))

        np.testing.assert_allclose(package["offset_map_mV"], offsets, atol=0.055)
        self.assertEqual(package["aligned_cube"].shape[:2], cube.shape[:2])
        self.assertLessEqual(package["aligned_cube"].shape[-1], cube.shape[-1])
        self.assertEqual(package["aligned_bias_mV"].shape[-1], package["aligned_cube"].shape[-1])
        self.assertEqual(package["algorithm"]["engine"], "analystm.intensity.peak_align_zero_cube")

    def test_z_ratio_uses_pysidam_negative_over_positive_regularization(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.intensity import compute_z_ratio_map
        finally:
            sys.path.remove(str(SRC))

        bias = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
        cube = np.zeros((2, 2, bias.size), dtype=float)
        cube[:, :, 1] = np.array([[2.0, 4.0], [6.0, 8.0]])
        cube[:, :, 3] = np.array([[1.0, 2.0], [3.0, 4.0]])

        package = compute_z_ratio_map(bias, cube, energy_mV=1.0)

        np.testing.assert_allclose(package["z_ratio_map"], (2.0 / (1.0 + 1e-6)) * np.ones((2, 2)))
        self.assertEqual(package["positive_bias_mV"], 1.0)
        self.assertEqual(package["negative_bias_mV"], -1.0)
        self.assertEqual(package["algorithm"]["engine"], "analystm.intensity.compute_z_ratio_map")
        self.assertIn("qpi_pr_pqi", package["algorithm"]["pysidam_source_mapping"])

    def test_intensity_cli_process_z_ratio_and_peak_align(self) -> None:
        bias = np.linspace(-2.0, 2.0, 21)
        spectra = np.vstack([bias**2, bias**2 + 1.0])
        cube = np.zeros((2, 2, bias.size), dtype=float)
        cube[:, :, np.argmin(np.abs(bias + 1.0))] = 4.0
        cube[:, :, np.argmin(np.abs(bias - 1.0))] = 2.0
        for y in range(2):
            for x in range(2):
                cube[y, x, :] += (
                    np.exp(-0.5 * ((bias + 1.0) / 0.12) ** 2)
                    + np.exp(-0.5 * ((bias - 1.0) / 0.12) ** 2)
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = root / "intensity_input.npz"
            np.savez_compressed(inp, bias=bias, spectra=spectra, cube=cube)

            proc_dir = root / "process"
            proc = _run_analystm(
                [
                    "intensity",
                    "process",
                    str(inp),
                    "--bias-key",
                    "bias",
                    "--data-key",
                    "spectra",
                    "--mode",
                    "d2",
                    "--bias-range",
                    "-1.0",
                    "1.0",
                    "--output-dir",
                    str(proc_dir),
                ]
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads((proc_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tool"], "analystm intensity process")
            self.assertEqual(report["algorithm"]["engine"], "analystm.intensity.process_intensity_matrix")
            self.assertTrue((proc_dir / "intensity_outputs.npz").is_file())

            z_dir = root / "z"
            z_proc = _run_analystm(
                [
                    "intensity",
                    "z-ratio",
                    str(inp),
                    "--bias-key",
                    "bias",
                    "--cube-key",
                    "cube",
                    "--energy-mv",
                    "1.0",
                    "--output-dir",
                    str(z_dir),
                ]
            )
            self.assertEqual(z_proc.returncode, 0, z_proc.stderr)
            z_report = json.loads((z_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(z_report["tool"], "analystm intensity z-ratio")
            self.assertEqual(z_report["algorithm"]["engine"], "analystm.intensity.compute_z_ratio_map")
            archive = np.load(z_dir / "intensity_z_ratio_outputs.npz")
            self.assertIn("z_ratio_map", archive.files)

            align_dir = root / "align"
            align_proc = _run_analystm(
                [
                    "intensity",
                    "peak-align-zero",
                    str(inp),
                    "--bias-key",
                    "bias",
                    "--cube-key",
                    "cube",
                    "--neg-window",
                    "-1.3",
                    "-0.7",
                    "--pos-window",
                    "0.7",
                    "1.3",
                    "--output-dir",
                    str(align_dir),
                ]
            )
            self.assertEqual(align_proc.returncode, 0, align_proc.stderr)
            align_report = json.loads((align_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(align_report["tool"], "analystm intensity peak-align-zero")
            self.assertEqual(align_report["algorithm"]["engine"], "analystm.intensity.peak_align_zero_cube")
            align_archive = np.load(align_dir / "intensity_aligned_outputs.npz")
            self.assertIn("aligned_cube", align_archive.files)


if __name__ == "__main__":
    unittest.main()
