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


class AnalySTMHistogramCropTests(unittest.TestCase):
    def test_histogram_bins_stats_and_small_sample_fit_match_pysidam(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.histogram import compute_histogram, histogram_max_bin_count
        finally:
            sys.path.remove(str(SRC))

        data = np.array([[1.0, 2.0, np.nan], [3.0, 4.0, 5.0]], dtype=float)
        package = compute_histogram(data, vmin=1.0, vmax=5.0, bin_size=1.0)

        self.assertEqual(package["parameters"]["bins"], 5)
        np.testing.assert_allclose(package["counts"], np.ones(5))
        np.testing.assert_allclose(package["fit_x"], package["centers"])
        np.testing.assert_allclose(package["fit_y"], package["counts"])
        self.assertEqual(package["stats"]["count"], 5)
        self.assertAlmostEqual(package["stats"]["mean"], 3.0)
        self.assertAlmostEqual(package["stats"]["median"], 3.0)
        self.assertIn("usefultools_histogram", package["algorithm"]["pysidam_source_mapping"])
        self.assertEqual(histogram_max_bin_count([0.0, 0.2, 1.0, 2.0], 0.0, 2.0, 1.0), 2.0)

    def test_histogram_cli_writes_report_and_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = root / "map.npz"
            np.savez_compressed(inp, signal=np.arange(12, dtype=float).reshape(3, 4))
            out_dir = root / "hist"

            proc = _run_analystm(
                [
                    "histogram",
                    str(inp),
                    "--data-key",
                    "signal",
                    "--vmin",
                    "0",
                    "--vmax",
                    "11",
                    "--bin-size",
                    "2",
                    "--output-dir",
                    str(out_dir),
                ]
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tool"], "analystm histogram")
            self.assertEqual(report["stats"]["count"], 12)
            self.assertTrue((out_dir / "histogram.csv").is_file())
            self.assertTrue((out_dir / "fit_curve.csv").is_file())

    def test_square_crop_geometry_sampling_and_header_match_pysidam(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.map_crop import build_generated_header, compute_square_crop_geometry, sample_display_patch
        finally:
            sys.path.remove(str(SRC))

        arr = np.arange(24, dtype=float).reshape(4, 6)
        geometry = compute_square_crop_geometry(
            preview_shape_yx=arr.shape,
            center_xy_px=(3.0, 2.0),
            side_px=2.0,
            angle_deg=0.0,
            source_size_nm_xy=(12.0, 8.0),
        )
        patch = sample_display_patch(arr, geometry)

        np.testing.assert_allclose(patch, np.array([[8.0, 9.0], [14.0, 15.0]]))
        self.assertEqual(geometry["out_shape"], (2, 2))
        self.assertEqual(geometry["crop_size_nm"], (4.0, 4.0))
        header = build_generated_header(
            {"size_xy": [12e-9, 8e-9], "grid_dim": [6, 4]},
            geometry,
            dtype="3ds",
            bias_len=7,
            source_file="source.3ds",
            source_channel="LI Demod",
        )
        self.assertEqual(header["grid_dim"], [2, 2])
        self.assertEqual(header["num_sweep_signal"], 7)
        self.assertEqual(header["crop_source_file"], "source.3ds")
        np.testing.assert_allclose(header["size_xy"], [4e-9, 4e-9])

    def test_crop_3ds_and_sxm_orientation_match_pysidam(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.map_crop import (
                compute_square_crop_geometry,
                crop_3ds_signals,
                crop_sxm_signals,
                extract_sxm_display_map,
                undo_sxm_display_orientation,
            )
        finally:
            sys.path.remove(str(SRC))

        geometry = compute_square_crop_geometry(
            preview_shape_yx=(4, 6),
            center_xy_px=(3.0, 2.0),
            side_px=2.0,
            angle_deg=0.0,
            source_size_nm_xy=(12.0, 8.0),
        )
        cube = np.arange(6 * 4 * 2, dtype=float).reshape(6, 4, 2)
        cropped = crop_3ds_signals({"lockin": cube}, geometry)
        np.testing.assert_allclose(cropped["lockin"], cube[2:4, 1:3, :])

        header = {"scan_dir": "up"}
        raw = np.array([[1.0, 2.0], [3.0, 4.0]])
        display = extract_sxm_display_map({"backward": raw}, header=header)
        restored = undo_sxm_display_orientation(display, "backward", header=header)
        np.testing.assert_allclose(restored, raw)
        cropped_sxm = crop_sxm_signals({"topo": {"backward": raw}}, geometry, header=header)
        self.assertIn("topo", cropped_sxm)

    def test_crop_cli_writes_npz_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = root / "cube.npz"
            cube = np.arange(6 * 4 * 2, dtype=float).reshape(6, 4, 2)
            np.savez_compressed(inp, cube=cube)
            out_dir = root / "crop"

            proc = _run_analystm(
                [
                    "crop",
                    "map",
                    str(inp),
                    "--data-key",
                    "cube",
                    "--kind",
                    "3ds",
                    "--center-px",
                    "3",
                    "2",
                    "--side-px",
                    "2",
                    "--scan-size-nm",
                    "12",
                    "8",
                    "--output-dir",
                    str(out_dir),
                ]
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tool"], "analystm crop map")
            self.assertEqual(report["outputs"]["data_npz"], str(out_dir / "cropped_data.npz"))
            archive = np.load(out_dir / "cropped_data.npz")
            np.testing.assert_allclose(archive["cube"], cube[2:4, 1:3, :])


if __name__ == "__main__":
    unittest.main()
