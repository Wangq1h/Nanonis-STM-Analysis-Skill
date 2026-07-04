from __future__ import annotations

import unittest

import numpy as np

from pysidam_agent_core.atom_ai import apply_wipe_regions, lattice_qc, scale_recommendation


class AtomAICoreTests(unittest.TestCase):
    def test_resize_1p5_matches_fts_spin_pixel_scale(self) -> None:
        rec = scale_recommendation(
            shape_yx=(512, 512),
            scan_size_nm_xy=(20.0, 20.0),
            resize_ratio=1.5,
            expected_spacing_nm=0.3515625,
        )

        self.assertAlmostEqual(rec["native_pixel_nm_xy"][0], 0.0390625)
        self.assertAlmostEqual(rec["inference_pixel_nm_xy"][0], 0.0260416667)
        self.assertAlmostEqual(rec["expected_spacing_in_native_px"], 9.0)
        self.assertAlmostEqual(rec["expected_spacing_in_inference_px"], 13.5)
        self.assertEqual(rec["scale_status"], "preferred")

    def test_square_lattice_qc_passes_orderly_grid(self) -> None:
        spacing = 0.37
        yy, xx = np.mgrid[0:8, 0:8]
        coords = np.c_[xx.ravel() * spacing, yy.ravel() * spacing]

        qc = lattice_qc(coords, expected_spacing_nm=spacing)

        self.assertTrue(qc["passes"])
        self.assertGreater(qc["fourfold_order"], 0.95)
        self.assertLess(qc["duplicate_like_fraction"], 0.01)
        self.assertLess(qc["vacancy_like_fraction"], 0.01)

    def test_lattice_qc_flags_bad_detection_for_reparameterization(self) -> None:
        rng = np.random.default_rng(7)
        coords = rng.uniform(0, 3.0, size=(64, 2))

        qc = lattice_qc(coords, expected_spacing_nm=0.37)

        self.assertFalse(qc["passes"])
        self.assertTrue(qc["recommend_reparameterize"])
        self.assertIn("adjust", qc["recommendation"])

    def test_apply_wipe_regions_marks_dw_band_and_dirty_spot(self) -> None:
        rows = [
            {"atom_id": 1, "x_nm": 12.0, "y_nm": 4.0, "class": "A"},
            {"atom_id": 2, "x_nm": 5.0, "y_nm": 5.0, "class": "B"},
            {"atom_id": 3, "x_nm": 15.0, "y_nm": 15.0, "class": "A"},
        ]
        regions = [
            {"type": "x_band", "x_min_nm": 11.0, "x_max_nm": 13.0, "label": "DW"},
            {"type": "circle", "center_nm": [15.0, 15.0], "radius_nm": 0.4, "label": "dirty_spot"},
        ]

        wiped, summary = apply_wipe_regions(rows, regions)

        self.assertEqual(summary["wiped_count"], 2)
        self.assertEqual(wiped[0]["analysis_class"], "excluded_DW")
        self.assertEqual(wiped[1]["analysis_class"], "B")
        self.assertEqual(wiped[2]["analysis_class"], "excluded_dirty_spot")


if __name__ == "__main__":
    unittest.main()
