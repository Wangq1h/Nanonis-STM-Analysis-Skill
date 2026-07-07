from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from analystm.deconvolution import (
    build_linear_resample_matrix,
    build_pinv_operator,
    compute_r2_score,
    nanmean_cube_over_pixels,
)


class AnalySTMGridDeconvolutionTests(unittest.TestCase):
    def test_linear_resample_matrix_handles_interpolation_and_extrapolation(self) -> None:
        src = np.asarray([0.0, 1.0, 2.0])
        dst = np.asarray([-1.0, 0.0, 0.5, 2.0, 3.0])

        linear = build_linear_resample_matrix(src, dst, extrapolation="linear", edge_points=2)
        constant = build_linear_resample_matrix(src, dst, extrapolation="constant")

        np.testing.assert_allclose(
            linear,
            np.asarray(
                [
                    [2.0, -1.0, 0.0],
                    [1.0, 0.0, 0.0],
                    [0.5, 0.5, 0.0],
                    [0.0, 0.0, 1.0],
                    [0.0, -1.0, 2.0],
                ]
            ),
        )
        np.testing.assert_allclose(
            constant,
            np.asarray(
                [
                    [1.0, 0.0, 0.0],
                    [1.0, 0.0, 0.0],
                    [0.5, 0.5, 0.0],
                    [0.0, 0.0, 1.0],
                    [0.0, 0.0, 1.0],
                ]
            ),
        )

    def test_linear_resample_matrix_rejects_non_increasing_source_grid(self) -> None:
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            build_linear_resample_matrix([0.0, 0.0, 1.0], [0.5])

    def test_nanmean_cube_over_pixels_averages_each_bias_plane(self) -> None:
        cube = np.asarray(
            [
                [[1.0, 2.0, np.nan], [3.0, np.nan, 9.0]],
                [[5.0, 6.0, 7.0], [11.0, 12.0, 13.0]],
            ]
        )
        mask = np.asarray([[True, False], [True, True]])

        out = nanmean_cube_over_pixels(cube, mask)

        np.testing.assert_allclose(out, [17.0 / 3.0, 20.0 / 3.0, 10.0])

    def test_compute_r2_score_uses_residual_against_finite_y_true(self) -> None:
        r2 = compute_r2_score([1.0, 2.0, 3.0, np.nan], [0.0, 0.5, -0.5, 1.0])

        self.assertAlmostEqual(r2, 0.75)

    def test_build_pinv_operator_returns_weighted_operator_and_metadata(self) -> None:
        matrix = np.asarray([[1.0, 0.0], [0.0, 2.0], [1.0, 1.0], [2.0, -1.0]])
        weights = np.asarray([1.0, 0.25, 4.0, 2.0])

        operator, meta = build_pinv_operator(matrix, pinv_rcond=1e-12, weights=weights)
        expected = np.linalg.pinv(matrix * np.sqrt(weights)[:, None], rcond=1e-12) * np.sqrt(weights)[None, :]

        np.testing.assert_allclose(operator, expected)
        self.assertEqual(meta["rank_kept"], 2)
        self.assertEqual(meta["rank_total"], 2)
        self.assertTrue(meta["weighting"]["enabled"])
        self.assertAlmostEqual(meta["weighting"]["weight_min_applied"], 0.25)
        self.assertAlmostEqual(meta["weighting"]["weight_max_applied"], 4.0)

    def test_grid_helpers_are_exported_from_analystm_namespace(self) -> None:
        import analystm

        self.assertIs(analystm.build_linear_resample_matrix, build_linear_resample_matrix)
        self.assertIs(analystm.build_pinv_operator, build_pinv_operator)
        self.assertIs(analystm.compute_r2_score, compute_r2_score)
        self.assertIs(analystm.nanmean_cube_over_pixels, nanmean_cube_over_pixels)


if __name__ == "__main__":
    unittest.main()
