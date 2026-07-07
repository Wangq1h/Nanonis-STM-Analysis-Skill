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


class AnalySTMQPITests(unittest.TestCase):
    def test_symmetrize_qpi_matches_rotate_average_contract(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.qpi import run_qpi_symmetry, symmetrize_qpi
        finally:
            sys.path.remove(str(SRC))

        qpi = np.zeros((7, 7), dtype=float)
        qpi[1, 3] = 4.0
        qpi[3, 5] = 8.0
        qpi[5, 3] = 12.0
        qpi[3, 1] = 16.0

        sym = symmetrize_qpi(qpi, order=4)
        np.testing.assert_allclose(sym, np.rot90(sym), atol=1e-10)
        self.assertAlmostEqual(float(sym[1, 3]), 10.0, places=8)
        package = run_qpi_symmetry(qpi, order=4)
        self.assertEqual(package["algorithm"]["engine"], "analystm.qpi.symmetrize_qpi")
        self.assertIn("qpi_symmetry.symmetrize_qpi", package["algorithm"]["pysidam_source_mapping"])

    def test_pr_qpi_volume_matches_single_and_multi_impurity_branches(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.qpi import compute_pr_qpi_volume
        finally:
            sys.path.remove(str(SRC))

        bias = np.array([-1.0, 0.0, 1.0], dtype=float)
        base = np.zeros((4, 4), dtype=float)
        base[1, 2] = 1.0
        cube = np.zeros((4, 4, 3), dtype=float)
        cube[:, :, 0] = 2.0 * base
        cube[:, :, 2] = base

        single = compute_pr_qpi_volume(
            cube,
            bias,
            slider_min=2,
            slider_max=2,
            is_multi_impurity=False,
            window_name="none",
            mask_dc=False,
            scale_mode="Linear",
        )
        multi = compute_pr_qpi_volume(
            cube,
            bias,
            slider_min=2,
            slider_max=2,
            is_multi_impurity=True,
            window_name="none",
            mask_dc=False,
            scale_mode="Linear",
        )

        fft_pos = np.asarray(single["fft_stack"][:, :, 2])
        expected_pos = np.abs(fft_pos).astype(np.float32)
        np.testing.assert_allclose(single["pr_qpi_pos"][:, :, 0], expected_pos)
        np.testing.assert_allclose(single["pr_qpi_neg"][:, :, 0], 2.0 * expected_pos, atol=1e-6)
        np.testing.assert_allclose(multi["pr_qpi_neg"][:, :, 0], (2.0 / (1.0 + 1e-6)) * expected_pos, atol=1e-5)
        self.assertEqual(single["positive_indices"].tolist(), [2])
        self.assertEqual(single["negative_indices"].tolist(), [0])
        self.assertEqual(single["algorithm"]["engine"], "analystm.qpi.compute_pr_qpi_volume")
        self.assertIn("_compute_pr_qpi_volume", single["algorithm"]["pysidam_source_mapping"])

    def test_fft_volume_matches_pysidam_display_contract(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.qpi import compute_fft_base_volume, postprocess_fft_volume, prepare_fft_block, run_qpi_fft
        finally:
            sys.path.remove(str(SRC))

        cube = np.ones((4, 4, 2), dtype=float)
        cube[1, 2, 0] = 5.0
        cube[2, 1, 1] = 7.0
        prepared = prepare_fft_block(cube, window_name="none")
        self.assertEqual(prepared.shape, cube.shape)
        np.testing.assert_allclose(np.nanmean(prepared, axis=(0, 1)), [0.0, 0.0], atol=1e-12)

        base = compute_fft_base_volume(cube, window_name="none", yield_sleep=0.0)
        manual = np.abs(np.fft.fftshift(np.fft.fft2(prepared, axes=(0, 1)), axes=(0, 1))).astype(np.float32)
        np.testing.assert_allclose(base, manual, atol=1e-6)
        sqrt_scaled = postprocess_fft_volume(base, mask_dc=False, scale_mode="Signed Sqrt")
        np.testing.assert_allclose(sqrt_scaled, np.sqrt(base), atol=1e-6)

        package = run_qpi_fft(cube, window_name="none", scale_mode="Linear")
        self.assertEqual(package["algorithm"]["engine"], "analystm.qpi.compute_fft_base_volume")
        self.assertIn("_compute_fft_base_volume", package["algorithm"]["pysidam_source_mapping"])
        self.assertEqual(package["fft_base"].shape, cube.shape)

    def test_real_phase_pll_matches_pysidam_wrapped_phase_formula(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.qpi import compute_real_phase_pll
        finally:
            sys.path.remove(str(SRC))

        yy, xx = np.mgrid[0:16, 0:16]
        image = np.cos(2 * np.pi * xx / 4.0) + 0.5 * np.cos(2 * np.pi * yy / 4.0)
        q1 = ((16 - 1) / 2.0, (16 - 1) / 2.0 + 4.0)
        q2 = ((16 - 1) / 2.0 + 4.0, (16 - 1) / 2.0)
        package = compute_real_phase_pll(image, image, q1_yx=q1, q2_yx=q2, sigma_px=2.0, window="none")

        pll = package["pll"]
        self.assertEqual(pll.shape, image.shape)
        self.assertLess(float(np.nanmax(np.abs(pll))), 1e-10)
        self.assertEqual(package["algorithm"]["engine"], "analystm.qpi.compute_real_phase_pll")
        self.assertIn("qpi_real_phase.lockin_phase", package["algorithm"]["pysidam_source_mapping"])

    def test_qpi_cli_writes_symmetry_and_pr_qpi_reports(self) -> None:
        qpi = np.zeros((7, 7), dtype=float)
        qpi[1, 3] = 4.0
        qpi[3, 5] = 8.0
        qpi[5, 3] = 12.0
        qpi[3, 1] = 16.0

        bias = np.array([-1.0, 0.0, 1.0], dtype=float)
        base = np.zeros((4, 4), dtype=float)
        base[1, 2] = 1.0
        cube = np.zeros((4, 4, 3), dtype=float)
        cube[:, :, 0] = 2.0 * base
        cube[:, :, 2] = base

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sym_in = root / "sym.npz"
            pr_in = root / "pr.npz"
            np.savez_compressed(sym_in, qpi=qpi)
            np.savez_compressed(pr_in, cube=cube, bias=bias)

            sym_dir = root / "sym_out"
            sym_proc = _run_analystm(
                [
                    "qpi",
                    "symmetry",
                    str(sym_in),
                    "--qpi-key",
                    "qpi",
                    "--order",
                    "4",
                    "--output-dir",
                    str(sym_dir),
                ]
            )
            self.assertEqual(sym_proc.returncode, 0, sym_proc.stderr)
            sym_report = json.loads((sym_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(sym_report["tool"], "analystm qpi symmetry")
            self.assertEqual(sym_report["algorithm"]["engine"], "analystm.qpi.symmetrize_qpi")
            self.assertTrue((sym_dir / "qpi_symmetry_outputs.npz").is_file())

            pr_dir = root / "pr_out"
            pr_proc = _run_analystm(
                [
                    "qpi",
                    "pr-qpi",
                    str(pr_in),
                    "--cube-key",
                    "cube",
                    "--bias-key",
                    "bias",
                    "--slider-min",
                    "2",
                    "--slider-max",
                    "2",
                    "--window",
                    "none",
                    "--no-mask-dc",
                    "--scale-mode",
                    "Linear",
                    "--output-dir",
                    str(pr_dir),
                ]
            )
            self.assertEqual(pr_proc.returncode, 0, pr_proc.stderr)
            pr_report = json.loads((pr_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(pr_report["tool"], "analystm qpi pr-qpi")
            self.assertEqual(pr_report["algorithm"]["engine"], "analystm.qpi.compute_pr_qpi_volume")
            archive = np.load(pr_dir / "qpi_pr_outputs.npz")
            self.assertIn("pr_qpi_pos", archive.files)
            self.assertIn("pr_qpi_neg", archive.files)

    def test_qpi_cli_writes_fft_and_real_phase_reports(self) -> None:
        cube = np.ones((4, 4, 2), dtype=float)
        cube[1, 2, 0] = 5.0
        cube[2, 1, 1] = 7.0
        yy, xx = np.mgrid[0:16, 0:16]
        image = np.cos(2 * np.pi * xx / 4.0) + 0.5 * np.cos(2 * np.pi * yy / 4.0)
        q1 = ((16 - 1) / 2.0, (16 - 1) / 2.0 + 4.0)
        q2 = ((16 - 1) / 2.0 + 4.0, (16 - 1) / 2.0)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fft_in = root / "fft.npz"
            real_in = root / "real.npz"
            np.savez_compressed(fft_in, cube=cube)
            np.savez_compressed(real_in, ref=image, target=image)

            fft_dir = root / "fft_out"
            fft_proc = _run_analystm(
                [
                    "qpi",
                    "fft-volume",
                    str(fft_in),
                    "--cube-key",
                    "cube",
                    "--window",
                    "none",
                    "--scale-mode",
                    "Linear",
                    "--output-dir",
                    str(fft_dir),
                ]
            )
            self.assertEqual(fft_proc.returncode, 0, fft_proc.stderr)
            fft_report = json.loads((fft_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(fft_report["tool"], "analystm qpi fft-volume")
            self.assertTrue((fft_dir / "qpi_fft_outputs.npz").is_file())

            real_dir = root / "real_out"
            real_proc = _run_analystm(
                [
                    "qpi",
                    "real-phase",
                    str(real_in),
                    "--ref-key",
                    "ref",
                    "--target-key",
                    "target",
                    "--q1",
                    str(q1[0]),
                    str(q1[1]),
                    "--q2",
                    str(q2[0]),
                    str(q2[1]),
                    "--sigma-px",
                    "2.0",
                    "--window",
                    "none",
                    "--output-dir",
                    str(real_dir),
                ]
            )
            self.assertEqual(real_proc.returncode, 0, real_proc.stderr)
            real_report = json.loads((real_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(real_report["tool"], "analystm qpi real-phase")
            archive = np.load(real_dir / "qpi_real_phase_outputs.npz")
            self.assertIn("pll", archive.files)


if __name__ == "__main__":
    unittest.main()
