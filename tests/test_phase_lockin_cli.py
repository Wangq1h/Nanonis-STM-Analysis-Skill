from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

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


if __name__ == "__main__":
    unittest.main()
