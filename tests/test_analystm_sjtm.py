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


def _sjtm_cube() -> tuple[np.ndarray, np.ndarray]:
    bias = np.linspace(-2.5, 2.5, 81)
    cube = np.empty((3, 2, bias.size), dtype=float)
    for x in range(cube.shape[0]):
        for y in range(cube.shape[1]):
            cube[x, y, :] = (
                (0.16 + 0.02 * x) * bias
                + 0.34 * np.exp(-0.5 * ((bias - 0.72) / 0.12) ** 2)
                - 0.29 * np.exp(-0.5 * ((bias + 0.68) / 0.13) ** 2)
                + 0.05 * np.exp(-0.5 * (bias / 0.08) ** 2)
            ) * 1e-12
    return bias, cube


class AnalySTMSJTMTests(unittest.TestCase):
    def test_ic_map_exposes_pysidam_quick_and_accurate_configs(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.sjtm import compute_ic_map
        finally:
            sys.path.remove(str(SRC))

        bias, cube = _sjtm_cube()
        quick = compute_ic_map(
            bias,
            cube,
            neg_window=(-1.1, -0.35),
            pos_window=(0.35, 1.1),
            min_points=5,
            fit_mode="quick",
            random_seed=1,
        )
        accurate = compute_ic_map(
            bias,
            cube,
            neg_window=(-1.1, -0.35),
            pos_window=(0.35, 1.1),
            min_points=5,
            fit_mode="accurate",
            random_seed=1,
        )

        self.assertEqual(quick["parameters"]["fit_mode"], "Quick")
        self.assertEqual(quick["parameters"]["maxfev"], 1200)
        self.assertEqual(quick["parameters"]["retries"], 0)
        self.assertEqual(accurate["parameters"]["fit_mode"], "Accurate")
        self.assertEqual(accurate["parameters"]["maxfev"], 4200)
        self.assertEqual(accurate["parameters"]["retries"], 2)
        self.assertEqual(quick["fit_params_neg"].shape, cube.shape[:2] + (4,))
        self.assertEqual(quick["fit_params_pos"].shape, cube.shape[:2] + (4,))
        self.assertGreater(int(np.count_nonzero(np.isfinite(quick["ic_map"]))), 0)

    def test_superfluid_g0_window_does_not_silently_expand_by_default(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.sjtm import compute_superfluid_metrics
        finally:
            sys.path.remove(str(SRC))

        bias = np.array([-1.0, 0.0, 1.0], dtype=float)
        cube = np.ones((2, 2, bias.size), dtype=float) * 1e-12
        with self.assertRaisesRegex(ValueError, "G\\(0\\) window has"):
            compute_superfluid_metrics(
                bias,
                cube,
                cube,
                rn_points=3,
                g0_window=(0.2, 0.3),
                g0_min_points=3,
            )

    def test_sjtm_cli_accepts_accurate_ic_mode(self) -> None:
        env = dict()
        env.update({"PYTHONPATH": str(SRC)})
        bias, cube = _sjtm_cube()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = root / "sjtm.npz"
            out_dir = root / "out"
            np.savez_compressed(inp, bias=bias, current=cube)
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "analystm",
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
                    "--ic-fit-mode",
                    "accurate",
                    "--random-seed",
                    "1",
                    "--output-dir",
                    str(out_dir),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["parameters"]["ic"]["fit_mode"], "Accurate")
            self.assertEqual(report["parameters"]["ic"]["retries"], 2)


if __name__ == "__main__":
    unittest.main()
