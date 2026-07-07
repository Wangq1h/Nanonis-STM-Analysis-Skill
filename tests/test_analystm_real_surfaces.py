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


class AnalySTMRealSurfaceTests(unittest.TestCase):
    def test_gap_map_cli_runs_pysidam_peakfitter_algorithm(self) -> None:
        bias = np.linspace(-4.0, 4.0, 81)
        cube = np.empty((3, 4, bias.size), dtype=float)
        for y in range(cube.shape[0]):
            for x in range(cube.shape[1]):
                left = -1.45 - 0.03 * y
                right = 1.55 + 0.02 * x
                cube[y, x, :] = (
                    0.08
                    + np.exp(-0.5 * ((bias - left) / 0.16) ** 2)
                    + 1.15 * np.exp(-0.5 * ((bias - right) / 0.18) ** 2)
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = root / "gap_input.npz"
            np.savez_compressed(inp, bias=bias, cube=cube)
            out_dir = root / "gap"
            proc = _run_analystm(
                [
                    "gap-map",
                    str(inp),
                    "--bias-key",
                    "bias",
                    "--cube-key",
                    "cube",
                    "--left-window",
                    "-2.2",
                    "-0.8",
                    "--right-window",
                    "0.8",
                    "2.2",
                    "--interp-factor",
                    "4",
                    "--output-dir",
                    str(out_dir),
                ]
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tool"], "analystm gap-map")
            self.assertEqual(report["algorithm"]["engine"], "analystm.gap_map.extract_gap_map")
            self.assertIn("PeakFitter.fit_single_pixel", report["algorithm"]["pysidam_source_mapping"])
            self.assertNotIn("reserved", json.dumps(report).lower())
            archive = np.load(out_dir / "gap_map_outputs.npz")
            gap = np.asarray(archive["gap_map_mV"], dtype=float)
            self.assertEqual(gap.shape, cube.shape[:2])
            self.assertLess(float(abs(np.nanmean(gap) - 1.5)), 0.2)
            self.assertTrue((out_dir / "gap_map_summary.csv").is_file())

    def test_sjtm_cli_runs_ic_and_superfluid_algorithms(self) -> None:
        bias = np.linspace(-2.5, 2.5, 101)
        cube = np.empty((2, 3, bias.size), dtype=float)
        for y in range(cube.shape[0]):
            for x in range(cube.shape[1]):
                slope = 0.18 + 0.02 * x
                cube[y, x, :] = (
                    slope * bias
                    + 0.35 * np.exp(-0.5 * ((bias - 0.75) / 0.12) ** 2)
                    - 0.30 * np.exp(-0.5 * ((bias + 0.70) / 0.13) ** 2)
                    + 0.05 * np.exp(-0.5 * (bias / 0.08) ** 2)
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = root / "sjtm_input.npz"
            np.savez_compressed(inp, bias=bias, current=cube)
            out_dir = root / "sjtm"
            proc = _run_analystm(
                [
                    "sjtm",
                    str(inp),
                    "--bias-key",
                    "bias",
                    "--cube-key",
                    "current",
                    "--neg-window",
                    "-1.1",
                    "-0.35",
                    "--pos-window",
                    "0.35",
                    "1.1",
                    "--rn-window",
                    "1.2",
                    "2.2",
                    "--g0-window",
                    "-0.2",
                    "0.2",
                    "--output-dir",
                    str(out_dir),
                ]
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tool"], "analystm sjtm")
            self.assertEqual(report["algorithm"]["engine"], "analystm.sjtm.compute_sjtm_package")
            self.assertIn("SJTMIcExtractionWindow._compute_ic_map", report["algorithm"]["ic_pysidam_source_mapping"])
            self.assertIn("SJTMSuperfluidDensityWindow._compute_metrics", report["algorithm"]["superfluid_pysidam_source_mapping"])
            archive = np.load(out_dir / "sjtm_outputs.npz")
            for key in ("ic_map", "rn_map", "g0_map", "ns_map"):
                arr = np.asarray(archive[key], dtype=float)
                self.assertEqual(arr.shape, cube.shape[:2])
                self.assertGreater(int(np.count_nonzero(np.isfinite(arr))), 0)
            self.assertTrue((out_dir / "sjtm_summary.csv").is_file())

    def test_deconvolve_cli_runs_real_sis_deconvolution_not_proxy(self) -> None:
        bias = np.linspace(-3.0, 3.0, 61)
        didv = 0.25 + np.exp(-0.5 * ((np.abs(bias) - 1.2) / 0.20) ** 2)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = root / "deconv_input.npz"
            np.savez_compressed(inp, bias=bias, didv=didv)
            out_dir = root / "deconv"
            proc = _run_analystm(
                [
                    "deconvolve",
                    str(inp),
                    "--bias-key",
                    "bias",
                    "--didv-key",
                    "didv",
                    "--mode",
                    "sis",
                    "--temperature-k",
                    "0.4",
                    "--tip-delta-mev",
                    "1.2",
                    "--tip-gamma-mev",
                    "0.03",
                    "--pinv-rcond",
                    "0.01",
                    "--output-dir",
                    str(out_dir),
                ]
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            report_text = (out_dir / "report.json").read_text(encoding="utf-8")
            report = json.loads(report_text)
            self.assertEqual(report["tool"], "analystm deconvolve")
            self.assertEqual(report["algorithm"]["engine"], "analystm.deconvolution.run_sis_didv_deconvolution")
            self.assertIn("run_sis_didv_deconvolution", report["algorithm"]["pysidam_source_mapping"])
            lowered = report_text.lower()
            self.assertNotIn("proxy", lowered)
            self.assertNotIn("reserved", lowered)
            archive = np.load(out_dir / "deconvolution_outputs.npz")
            self.assertIn("sample_dos", archive.files)
            self.assertIn("reconvolved_didv", archive.files)
            self.assertEqual(np.asarray(archive["sample_dos"]).shape, bias.shape)
            self.assertTrue(np.isfinite(np.asarray(archive["reconvolved_didv"], dtype=float)).any())
            self.assertTrue((out_dir / "deconvolution_summary.csv").is_file())


if __name__ == "__main__":
    unittest.main()
