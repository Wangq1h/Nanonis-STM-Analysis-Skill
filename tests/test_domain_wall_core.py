from __future__ import annotations

import unittest

import numpy as np

from pysidam_agent_core.domain_wall import (
    build_domain_wall_masks,
    domain_wall_policy,
    region_stats,
)


class DomainWallCoreTests(unittest.TestCase):
    def test_policy_asks_before_agent_dw_search_without_user_regions(self) -> None:
        decision = domain_wall_policy(regions=None, allow_agent_proposal=False)

        self.assertEqual(decision["mode"], "ask_user_for_dw_regions")
        self.assertIn("human", decision["message"].lower())

    def test_build_masks_from_user_x_band_with_near_and_away_regions(self) -> None:
        masks = build_domain_wall_masks(
            shape_yx=(4, 5),
            scan_size_nm_xy=(5.0, 4.0),
            regions=[{"type": "x_band", "x_min_nm": 1.0, "x_max_nm": 2.0, "label": "DW"}],
            near_width_nm=1.0,
        )

        np.testing.assert_array_equal(
            masks["on_dw_mask"][0],
            np.array([False, True, False, False, False]),
        )
        np.testing.assert_array_equal(
            masks["near_dw_mask"][0],
            np.array([True, False, True, False, False]),
        )
        np.testing.assert_array_equal(
            masks["away_mask"][0],
            np.array([False, False, False, True, True]),
        )
        self.assertEqual(masks["counts"]["on_dw"], 4)
        self.assertEqual(masks["counts"]["near_dw"], 8)
        self.assertEqual(masks["counts"]["away"], 8)

    def test_line_strip_mask_tracks_slanted_human_domain_wall(self) -> None:
        masks = build_domain_wall_masks(
            shape_yx=(5, 5),
            scan_size_nm_xy=(5.0, 5.0),
            regions=[
                {
                    "type": "line_strip",
                    "point_nm": [2.5, 2.5],
                    "normal_nm": [1.0, -1.0],
                    "width_nm": 1.0,
                    "label": "DW",
                }
            ],
        )

        self.assertTrue(masks["on_dw_mask"][0, 0])
        self.assertTrue(masks["on_dw_mask"][2, 2])
        self.assertTrue(masks["on_dw_mask"][4, 4])
        self.assertFalse(masks["on_dw_mask"][0, 4])

    def test_refined_on_dw_keeps_broad_strip_out_of_away_region(self) -> None:
        z = np.zeros((4, 5), dtype=float)
        z[:, 1] = [0.1, 3.0, 4.0, 0.2]
        masks = build_domain_wall_masks(
            shape_yx=z.shape,
            scan_size_nm_xy=(5.0, 4.0),
            regions=[{"type": "x_band", "x_min_nm": 1.0, "x_max_nm": 2.0, "label": "broad_DW"}],
            refine_map_yx=z,
            refine_percentile=60.0,
        )

        self.assertEqual(masks["counts"]["broad_dw"], 4)
        self.assertEqual(masks["counts"]["on_dw"], 2)
        self.assertFalse(masks["away_mask"][0, 1])
        self.assertFalse(masks["away_mask"][3, 1])

    def test_region_stats_reports_dw_over_away_ratio(self) -> None:
        metric = np.ones((4, 5), dtype=float)
        metric[:, 1] = 4.0
        masks = build_domain_wall_masks(
            shape_yx=metric.shape,
            scan_size_nm_xy=(5.0, 4.0),
            regions=[{"type": "x_band", "x_min_nm": 1.0, "x_max_nm": 2.0, "label": "DW"}],
        )

        stats = region_stats(metric, masks)

        self.assertEqual(stats["regions"]["on_dw"]["n"], 4)
        self.assertAlmostEqual(stats["regions"]["on_dw"]["mean"], 4.0)
        self.assertAlmostEqual(stats["regions"]["away"]["mean"], 1.0)
        self.assertAlmostEqual(stats["ratios"]["on_dw_over_away_mean"], 4.0)


if __name__ == "__main__":
    unittest.main()
