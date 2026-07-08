from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from analystm.cli.main import main as analystm_main
from scripts.pysidam_agent.phase_lockin import parse_q_args, write_outputs


class PhaseLockinCliTests(unittest.TestCase):
    def test_parse_q_args_accepts_labels_and_auto_labels(self) -> None:
        q_vectors = parse_q_args(["qA=1.0,2.0", "-0.5,0.25"])

        self.assertEqual(q_vectors["qA"], (1.0, 2.0))
        self.assertEqual(q_vectors["q2"], (-0.5, 0.25))

    def test_write_outputs_saves_report_npz_and_stats(self) -> None:
        package = {
            "metadata": {
                "schema_version": 1,
                "lockin_engine": "pysidam.qpi_analysis.qpi_phase_analysis.lockin_phase_extraction",
                "shape_yx": [2, 2],
                "scan_size_nm_xy": [4.0, 4.0],
                "q_results": {"q1": {"q_cycles_per_nm_xy": [0.25, 0.0]}},
            },
            "maps": {
                "q1_amp": np.ones((2, 2), dtype=float),
                "q1_phase_wrapped": np.zeros((2, 2), dtype=float),
                "q1_complex": np.ones((2, 2), dtype=complex),
            },
            "stats_rows": [
                {
                    "q_label": "q1",
                    "threshold_fraction_of_amp_max": 0.2,
                    "pixels_in_mask": 4,
                    "mask_fraction": 1.0,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = write_outputs(
                output_dir=Path(tmp),
                input_map=np.zeros((2, 2), dtype=float),
                processed_map=np.zeros((2, 2), dtype=float),
                package=package,
                source_info={"source_file": "synthetic.npy"},
                preprocessing={"steps": []},
            )

            report = json.loads(Path(out["report_json"]).read_text(encoding="utf-8"))
            self.assertEqual(report["analysis"]["lockin_engine"], package["metadata"]["lockin_engine"])
            self.assertTrue(Path(out["maps_npz"]).is_file())
            self.assertTrue(Path(out["stats_csv"]).is_file())

    def test_analystm_phase_lockin_cli_report_names_outputs_and_engine(self) -> None:
        image = np.cos(np.linspace(0.0, 2.0 * np.pi, 64, endpoint=False)).reshape(8, 8)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            map_path = root / "map.npy"
            out_dir = root / "out"
            np.save(map_path, image)

            rc = analystm_main(
                [
                    "phase-lockin",
                    str(map_path),
                    "--q",
                    "q2=0.25,0.0",
                    "--scan-size-nm",
                    "4",
                    "4",
                    "--sigma-px",
                    "2.5",
                    "--threshold",
                    "0.2",
                    "--output-dir",
                    str(out_dir),
                ]
            )

            self.assertEqual(rc, 0)
            report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tool"], "analystm phase-lockin")
            self.assertEqual(report["analysis"]["lockin_engine"], "analystm.phase_lockin.lockin_phase_extraction")
            self.assertEqual(report["input"]["path"], str(map_path))
            self.assertEqual(report["parameters"]["q_vectors_xy_cycles_per_nm"]["q2"], [0.25, 0.0])
            self.assertEqual(report["outputs"]["maps_npz"], "phase_lockin_maps.npz")
            self.assertEqual(report["outputs"]["stats_csv"], "phase_lockin_stats.csv")
            self.assertTrue((out_dir / report["outputs"]["maps_npz"]).is_file())
            stats_rows = (out_dir / report["outputs"]["stats_csv"]).read_text(encoding="utf-8").splitlines()
            self.assertGreaterEqual(len(stats_rows), 2)

    def test_validate_package_tracks_primary_analystm_lockin_api(self) -> None:
        from scripts import validate_package

        self.assertIn("run_lockin_phase", validate_package.REQUIRED_TOKENS["src/analystm/__init__.py"])
        self.assertIn("run_lockin_phase", validate_package.REQUIRED_TOKENS["src/analystm/phase_lockin.py"])


if __name__ == "__main__":
    unittest.main()
