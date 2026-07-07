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


class AnalySTMTopographyTests(unittest.TestCase):
    def test_lf_corrector_peak_refinement_and_q_vector_match_pysidam(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.topography import LFDriftCorrector
        finally:
            sys.path.remove(str(SRC))

        image = np.zeros((8, 10), dtype=float)
        corrector = LFDriftCorrector(image)
        corrector.P[:] = 0.0
        corrector.P[2, 7] = 11.0

        py, px = corrector.refine_peak_local_max(3, 6, search_r=2)
        self.assertEqual((py, px), (2, 7))
        np.testing.assert_allclose(corrector.get_q_vector(2, 7), [2 * np.pi * (2 - 4) / 8, 2 * np.pi * (7 - 5) / 10])

    def test_drift_field_formula_uses_pysidam_sign_convention(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.topography import compute_lf_drift_field_from_phases
        finally:
            sys.path.remove(str(SRC))

        y, x = np.mgrid[:3, :4]
        phi1 = 2.0 + 0.3 * y
        phi2 = -1.0 + 0.5 * x
        package = compute_lf_drift_field_from_phases(phi1, phi2, q1_yx=(1.0, 0.0), q2_yx=(0.0, 1.0))

        np.testing.assert_allclose(package["uy_field"], -(phi1 - np.mean(phi1)))
        np.testing.assert_allclose(package["ux_field"], phi2 - np.mean(phi2))
        np.testing.assert_allclose(package["corr_coords_y"], y + (phi1 - np.mean(phi1)))
        np.testing.assert_allclose(package["corr_coords_x"], x + (phi2 - np.mean(phi2)))
        self.assertEqual(package["algorithm"]["engine"], "analystm.topography.compute_lf_drift_field_from_phases")
        self.assertIn("LFDriftCorrector.compute_drift_field", package["algorithm"]["pysidam_source_mapping"])

    def test_apply_lf_displacement_to_stack_identity_preserves_data(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.topography import apply_lf_displacement_to_stack, identity_lf_corr_coords
        finally:
            sys.path.remove(str(SRC))

        cube = np.arange(3 * 4 * 2, dtype=float).reshape(3, 4, 2)
        corr_coords = identity_lf_corr_coords((3, 4))
        corrected = apply_lf_displacement_to_stack(cube, corr_coords)

        np.testing.assert_allclose(corrected, cube)

    def test_topography_cli_lf_drift_writes_report_and_outputs(self) -> None:
        image = np.zeros((8, 8), dtype=float)
        image[3, 4] = 1.0

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = root / "topo.npz"
            np.savez_compressed(inp, topo=image)
            out_dir = root / "lf"
            proc = _run_analystm(
                [
                    "topography",
                    "lf-drift",
                    str(inp),
                    "--image-key",
                    "topo",
                    "--q1",
                    "1.0",
                    "0.0",
                    "--q2",
                    "0.0",
                    "1.0",
                    "--sigma",
                    "2.0",
                    "--output-dir",
                    str(out_dir),
                ]
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tool"], "analystm topography lf-drift")
            self.assertEqual(report["algorithm"]["engine"], "analystm.topography.estimate_lf_displacement_from_q_vectors")
            self.assertIn("LFDriftCorrector", report["algorithm"]["pysidam_source_mapping"])
            archive = np.load(out_dir / "topography_lf_outputs.npz")
            for key in ("corrected_image", "ux_field", "uy_field", "corr_coords_y", "corr_coords_x"):
                self.assertIn(key, archive.files)
                self.assertEqual(np.asarray(archive[key]).shape, image.shape)


if __name__ == "__main__":
    unittest.main()
