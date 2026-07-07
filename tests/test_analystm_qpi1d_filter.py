from __future__ import annotations

import json
import math
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


class AnalySTMQPI1DAndFFTFilterTests(unittest.TestCase):
    def test_qpi1d_discrete_q0_notch_matches_pysidam_formula(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.qpi import build_fft_q0_gaussian_notch_1d_discrete
        finally:
            sys.path.remove(str(SRC))

        sigma = 1.25
        xx = np.arange(7, dtype=float) - 3.0
        denom = math.sqrt(2.0) * sigma
        scale = math.sqrt(math.pi / 2.0) * sigma
        expected = 1.0 - scale * np.array(
            [math.erf((x + 0.5) / denom) - math.erf((x - 0.5) / denom) for x in xx],
            dtype=float,
        )
        expected = np.clip(expected, 0.0, 1.0)

        np.testing.assert_allclose(build_fft_q0_gaussian_notch_1d_discrete(7, sigma_px=sigma), expected)

    def test_qpi1d_fft_matches_pysidam_linecut_contract(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.qpi import compute_qpi_1d_fft
        finally:
            sys.path.remove(str(SRC))

        cube = np.zeros((5, 3, 4), dtype=float)
        for ix in range(cube.shape[0]):
            for iy in range(cube.shape[1]):
                for iz in range(cube.shape[2]):
                    cube[ix, iy, iz] = 10.0 * ix + iy + 0.25 * iz

        package = compute_qpi_1d_fft(
            cube,
            bias=[-1.5, -0.5, 0.5, 1.5],
            scan_size_nm=(4.0, 2.0),
            p1_nm=(0.0, 1.0),
            p2_nm=(4.0, 1.0),
            cube_order="xyb",
            window_name="none",
            mask_q0=False,
            scale_mode="Linear",
        )

        expected_line = cube[:, 1, :]
        expected_fft = np.abs(np.fft.fftshift(np.fft.fft(expected_line, axis=0), axes=0)).astype(np.float32)
        expected_q = np.fft.fftshift(np.fft.fftfreq(5, d=1.0)) * (2.0 * np.pi)

        np.testing.assert_allclose(package["line_matrix_raw"], expected_line)
        np.testing.assert_allclose(package["fft_map_raw"], expected_fft)
        np.testing.assert_allclose(package["q_axis"], expected_q)
        self.assertEqual(package["algorithm"]["engine"], "analystm.qpi.compute_qpi_1d_fft")
        self.assertIn("QPI1DWindow.recompute_linecut_and_fft", package["algorithm"]["pysidam_source_mapping"])

    def test_fft_filter_roi_mask_and_ifft_match_pysidam_contract(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.fft_filter import build_fft_roi_mask, run_fft_filter
            from analystm.qpi import prepare_fft_block
        finally:
            sys.path.remove(str(SRC))

        image = np.zeros((8, 8), dtype=float)
        image[2, 3] = 1.0
        image[5, 4] = -0.5
        region = {"shape": "circle", "center": [2.0 * np.pi / 8.0, 0.0], "radius": 0.2}
        package = run_fft_filter(
            image,
            scan_size_nm=(8.0, 8.0),
            regions=[region],
            include_neg=True,
            mode="pass",
            invert=False,
            window_name="none",
            scale_mode="Linear",
        )

        kx = np.fft.fftshift(np.fft.fftfreq(8, d=1.0)) * (2.0 * np.pi)
        ky = np.fft.fftshift(np.fft.fftfreq(8, d=1.0)) * (2.0 * np.pi)
        kx_grid, ky_grid = np.meshgrid(kx, ky, indexing="xy")
        expected_mask = build_fft_roi_mask(
            kx_grid,
            ky_grid,
            [region],
            include_neg=True,
            mode="pass",
            invert=False,
        )
        expected_fft = np.fft.fftshift(np.fft.fft2(prepare_fft_block(image, window_name="none")))
        expected_filtered = np.real(np.fft.ifft2(np.fft.ifftshift(expected_fft * expected_mask)))

        np.testing.assert_array_equal(package["mask"], expected_mask)
        np.testing.assert_allclose(package["filtered"], expected_filtered, atol=1e-12)
        self.assertEqual(package["algorithm"]["engine"], "analystm.fft_filter.run_fft_filter")
        self.assertIn("topography_filter.FFTFilterWindow.update_filtered", package["algorithm"]["pysidam_source_mapping"])

    def test_cli_writes_qpi1d_and_fft_filter_reports(self) -> None:
        cube = np.zeros((5, 3, 4), dtype=float)
        for ix in range(cube.shape[0]):
            for iy in range(cube.shape[1]):
                cube[ix, iy, :] = 10.0 * ix + iy + np.arange(4, dtype=float)
        topo = np.zeros((8, 8), dtype=float)
        topo[2, 3] = 1.0

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qpi_in = root / "qpi.npz"
            topo_in = root / "topo.npz"
            np.savez_compressed(qpi_in, cube=cube, bias=np.linspace(-1.5, 1.5, 4), topo=topo)
            np.savez_compressed(topo_in, topo=topo)

            qpi1d_dir = root / "qpi1d_out"
            qpi1d_proc = _run_analystm(
                [
                    "qpi",
                    "1d-fft",
                    str(qpi_in),
                    "--cube-key",
                    "cube",
                    "--bias-key",
                    "bias",
                    "--scan-size-nm",
                    "4.0",
                    "2.0",
                    "--p1",
                    "0.0",
                    "1.0",
                    "--p2",
                    "4.0",
                    "1.0",
                    "--cube-order",
                    "xyb",
                    "--window",
                    "none",
                    "--no-mask-q0",
                    "--scale-mode",
                    "Linear",
                    "--output-dir",
                    str(qpi1d_dir),
                ]
            )
            self.assertEqual(qpi1d_proc.returncode, 0, qpi1d_proc.stderr)
            qpi1d_report = json.loads((qpi1d_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(qpi1d_report["tool"], "analystm qpi 1d-fft")
            self.assertTrue((qpi1d_dir / "qpi_1d_fft_outputs.npz").is_file())

            qpi_filter_dir = root / "qpi_filter_out"
            qpi_filter_proc = _run_analystm(
                [
                    "qpi",
                    "fft-filter",
                    str(qpi_in),
                    "--cube-key",
                    "cube",
                    "--scan-size-nm",
                    "4.0",
                    "2.0",
                    "--circle",
                    str(2.0 * np.pi / 4.0),
                    "0.0",
                    "0.3",
                    "--window",
                    "none",
                    "--output-dir",
                    str(qpi_filter_dir),
                ]
            )
            self.assertEqual(qpi_filter_proc.returncode, 0, qpi_filter_proc.stderr)
            qpi_filter_report = json.loads((qpi_filter_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(qpi_filter_report["tool"], "analystm qpi fft-filter")
            self.assertEqual(qpi_filter_report["parameters"]["input_kind"], "qpi_cube")

            topo_filter_dir = root / "topo_filter_out"
            topo_filter_proc = _run_analystm(
                [
                    "topography",
                    "fft-filter",
                    str(topo_in),
                    "--image-key",
                    "topo",
                    "--scan-size-nm",
                    "8.0",
                    "8.0",
                    "--circle",
                    str(2.0 * np.pi / 8.0),
                    "0.0",
                    "0.2",
                    "--window",
                    "none",
                    "--output-dir",
                    str(topo_filter_dir),
                ]
            )
            self.assertEqual(topo_filter_proc.returncode, 0, topo_filter_proc.stderr)
            topo_filter_report = json.loads((topo_filter_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(topo_filter_report["tool"], "analystm topography fft-filter")
            self.assertEqual(topo_filter_report["parameters"]["input_kind"], "topography")


if __name__ == "__main__":
    unittest.main()
