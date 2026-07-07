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


def _run_analystm(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "analystm", *args],
        cwd=ROOT,
        env=_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class AnalySTMDisplaySurfaceTests(unittest.TestCase):
    def test_topography_display_fft_linecut_and_lattice_math(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.topography_display import (
                compute_topography_fft_display,
                lattice_constant_from_delta_q,
                process_topography_display_map,
                sample_topography_linecut,
            )
        finally:
            sys.path.remove(str(SRC))

        data = np.arange(16, dtype=float).reshape(4, 4)
        processed = process_topography_display_map(data, background_mode="Sub Line Mean (0-order)")
        np.testing.assert_allclose(np.mean(processed, axis=1), np.zeros(4), atol=1e-12)
        line = sample_topography_linecut(data, scan_size_nm=4.0, p1_nm=(0.0, 1.0), p2_nm=(3.0, 1.0))
        np.testing.assert_allclose(line["distance_nm"], np.linspace(0.0, 3.0, 3))
        np.testing.assert_allclose(line["values"], [4.0, 5.5, 7.0])
        fft = compute_topography_fft_display(data, scan_size_nm=4.0, window_name="none", scale_mode="Sqrt")
        self.assertEqual(fft["fft_display"].shape, data.shape)
        self.assertAlmostEqual(fft["k_extent"][1], np.pi)
        self.assertAlmostEqual(lattice_constant_from_delta_q(2.0, lattice="square"), 2.0 * np.pi)
        self.assertIn("topography_display", fft["algorithm"]["pysidam_source_mapping"])

    def test_spectroscopy_pipeline_offset_derivative_and_export_payload(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.spectroscopy import auto_detect_offset, build_spectroscopy_export_payload, process_spectrum
        finally:
            sys.path.remove(str(SRC))

        x = np.linspace(-3.0, 3.0, 121)
        y = np.exp(-0.5 * ((x + 1.2) / 0.12) ** 2) + np.exp(-0.5 * ((x - 0.8) / 0.12) ** 2)
        offset = auto_detect_offset(x, y)
        self.assertAlmostEqual(offset["offset"], -0.2, delta=0.08)

        package = process_spectrum(
            x,
            y,
            offset=offset["offset"],
            symmetrize=True,
            smooth_method="Gaussian",
            smooth_param=1.0,
            norm_mode="Max",
            derivative_order=2,
            derivative_smooth=0.5,
        )
        self.assertEqual(package["processed_x"].shape, x.shape)
        self.assertLessEqual(float(np.max(np.abs(package["processed_y"]))), 1.0 + 1e-9)
        self.assertEqual(package["derivative_y"].shape, x.shape)
        payload = build_spectroscopy_export_payload(
            package["processed_x"],
            package["processed_y"],
            derivative_y=package["derivative_y"],
            derivative_order=2,
            export_kind="derivative",
            channel_name="LI Demod 1 X (A)",
        )
        self.assertEqual(payload["columns"][0][0], "Bias calc (V)")
        self.assertIn("-d3I/dV3", payload["columns"][1][0])
        self.assertIn("spectroscopy_display", package["algorithm"]["pysidam_source_mapping"])

    def test_topography_and_spectroscopy_cli_write_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topo = root / "topo.npz"
            spec = root / "spec.npz"
            np.savez_compressed(topo, topo=np.arange(16, dtype=float).reshape(4, 4))
            x = np.linspace(-2.0, 2.0, 41)
            y = np.exp(-0.5 * ((x - 0.7) / 0.12) ** 2) + np.exp(-0.5 * ((x + 0.7) / 0.12) ** 2)
            np.savez_compressed(spec, bias=x, didv=y)

            topo_dir = root / "topo_out"
            topo_proc = _run_analystm(
                [
                    "topography",
                    "display-fft",
                    str(topo),
                    "--image-key",
                    "topo",
                    "--scan-size-nm",
                    "4",
                    "--output-dir",
                    str(topo_dir),
                ]
            )
            self.assertEqual(topo_proc.returncode, 0, topo_proc.stderr)
            self.assertEqual(json.loads((topo_dir / "report.json").read_text(encoding="utf-8"))["tool"], "analystm topography display-fft")

            spec_dir = root / "spec_out"
            spec_proc = _run_analystm(
                [
                    "spectroscopy",
                    "process",
                    str(spec),
                    "--x-key",
                    "bias",
                    "--y-key",
                    "didv",
                    "--norm-mode",
                    "Max",
                    "--derivative-order",
                    "2",
                    "--output-dir",
                    str(spec_dir),
                ]
            )
            self.assertEqual(spec_proc.returncode, 0, spec_proc.stderr)
            self.assertEqual(json.loads((spec_dir / "report.json").read_text(encoding="utf-8"))["tool"], "analystm spectroscopy process")


if __name__ == "__main__":
    unittest.main()
