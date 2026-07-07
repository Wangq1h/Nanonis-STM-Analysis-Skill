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


class AnalySTMWaterfallTests(unittest.TestCase):
    def test_linecut_indices_match_pysidam_flattening_order(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.waterfall import linecut_flat_indices
        finally:
            sys.path.remove(str(SRC))

        indices = linecut_flat_indices((5, 4), p1_xy=(0.0, 1.0), p2_xy=(4.0, 1.0))

        np.testing.assert_array_equal(indices, np.array([1, 5, 9, 13, 17]))

    def test_waterfall_fit_exports_table_and_points_payload(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.waterfall import export_waterfall_table, waterfall_points_payload, run_waterfall_fit
        finally:
            sys.path.remove(str(SRC))

        bias = np.linspace(-3.0, 3.0, 61)
        cube = np.zeros((2, 2, bias.size), dtype=float)
        for ix in range(2):
            for iy in range(2):
                scale = 1.0 + ix + 0.5 * iy
                cube[ix, iy] = scale * (
                    np.exp(-0.5 * ((bias + 1.0) / 0.12) ** 2)
                    + 1.5 * np.exp(-0.5 * ((bias - 1.0) / 0.12) ** 2)
                )

        package = run_waterfall_fit(
            cube,
            bias,
            selected_indices=[0, 1, 2, 3],
            neg_range=(-1.3, -0.7),
            pos_range=(0.7, 1.3),
            offset=10.0,
            use_fit=False,
        )
        table = export_waterfall_table(package["results"])
        payload = waterfall_points_payload(package["results"], set_index=0, offset=10.0, neg_range=(-1.3, -0.7), pos_range=(0.7, 1.3))

        self.assertEqual(table.shape, (4, 5))
        np.testing.assert_allclose(table[:, 0], [0, 1, 2, 3])
        np.testing.assert_allclose(table[:, 1], -1.0, atol=0.051)
        np.testing.assert_allclose(table[:, 3], 1.0, atol=0.051)
        self.assertEqual(payload["set_tag"], "Set01")
        self.assertEqual(payload["points"][2]["global_index"], 2)
        self.assertEqual(package["algorithm"]["engine"], "analystm.waterfall.run_waterfall_fit")
        self.assertIn("linecutmap_waterfall", package["algorithm"]["pysidam_source_mapping"])

    def test_peak_align_zero_matches_waterfall_offset_convention(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.waterfall import peak_align_zero_grid
        finally:
            sys.path.remove(str(SRC))

        bias = np.linspace(-3.0, 3.0, 61)
        cube = np.zeros((2, 1, bias.size), dtype=float)
        offsets = np.array([[0.2], [-0.1]])
        for ix in range(2):
            off = float(offsets[ix, 0])
            cube[ix, 0] = (
                np.exp(-0.5 * ((bias - (-1.0 + off)) / 0.09) ** 2)
                + np.exp(-0.5 * ((bias - (1.0 + off)) / 0.09) ** 2)
            )

        package = peak_align_zero_grid(cube, bias, neg_range=(-1.4, -0.6), pos_range=(0.6, 1.4))

        np.testing.assert_allclose(package["offset_map_mV"], offsets, atol=0.055)
        self.assertLessEqual(package["aligned_grid"].shape[2], cube.shape[2])
        self.assertEqual(package["aligned_bias_mV"].shape[0], package["aligned_grid"].shape[2])

    def test_waterfall_cli_writes_report_tables_and_payload(self) -> None:
        bias = np.linspace(-2.0, 2.0, 41)
        cube = np.zeros((2, 2, bias.size), dtype=float)
        cube[:] = np.exp(-0.5 * ((bias + 0.8) / 0.1) ** 2) + np.exp(-0.5 * ((bias - 0.8) / 0.1) ** 2)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = root / "wf.npz"
            np.savez_compressed(inp, cube=cube, bias=bias)
            out_dir = root / "wf_out"

            proc = _run_analystm(
                [
                    "waterfall",
                    "fit",
                    str(inp),
                    "--cube-key",
                    "cube",
                    "--bias-key",
                    "bias",
                    "--linecut",
                    "0",
                    "0",
                    "1",
                    "1",
                    "--neg-range",
                    "-1.0",
                    "-0.6",
                    "--pos-range",
                    "0.6",
                    "1.0",
                    "--offset",
                    "3.0",
                    "--output-dir",
                    str(out_dir),
                ]
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tool"], "analystm waterfall fit")
            self.assertEqual(report["summary"]["trace_count"], 2)
            self.assertTrue((out_dir / "waterfall_table.csv").is_file())
            self.assertTrue((out_dir / "waterfall_points.json").is_file())


if __name__ == "__main__":
    unittest.main()
