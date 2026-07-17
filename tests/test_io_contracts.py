from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from analystm import dataset_utils
from pysidam_agent_core.io import build_read_parameters


class IOContractTests(unittest.TestCase):
    def test_default_divider_records_no_extra_bias_scaling(self) -> None:
        params = build_read_parameters(divider=1.0, divider_explicit=False, quick=True)

        self.assertEqual(params["divider"], 1.0)
        self.assertEqual(params["divider_source"], "default_no_rescale_bias_already_corrected")
        self.assertIn("already divider-corrected", params["divider_policy"])
        self.assertTrue(params["quick"])

    def test_explicit_divider_is_recorded_as_user_requested_extra_scaling(self) -> None:
        params = build_read_parameters(divider=100.0, divider_explicit=True, quick=False)

        self.assertEqual(params["divider"], 100.0)
        self.assertEqual(params["divider_source"], "explicit_user_requested_extra_scaling")
        self.assertIn("extra", params["divider_policy"])
        self.assertFalse(params["quick"])


class SXMOrientationContractTests(unittest.TestCase):
    @staticmethod
    def _corners() -> np.ndarray:
        # 11=top-left, 12=top-right, 21=bottom-left, 22=bottom-right.
        return np.array([[21.0, 22.0], [11.0, 12.0]])

    def _prepare(self, raw: np.ndarray, *, scan_dir: str, direction: str):
        prepare = getattr(dataset_utils, "prepare_sxm_map", None)
        self.assertTrue(callable(prepare), "prepare_sxm_map public API is missing")
        return prepare(
            raw,
            direction=direction,
            header={"scan_dir": scan_dir},
            frame="physical_xy",
        )

    def test_physical_xy_down_forward_flips_y(self) -> None:
        raw = np.array([[11.0, 12.0], [21.0, 22.0]])

        view = self._prepare(raw, scan_dir="down", direction="forward")

        np.testing.assert_array_equal(view.data_yx, self._corners())
        self.assertEqual(view.plot_origin, "lower")
        self.assertEqual(view.frame, "physical_xy")
        self.assertEqual(view.scan_dir, "down")
        self.assertEqual(view.direction, "forward")
        self.assertFalse(view.x_flip)
        self.assertTrue(view.y_flip)

    def test_physical_xy_up_forward_preserves_y(self) -> None:
        raw = np.array([[21.0, 22.0], [11.0, 12.0]])

        view = self._prepare(raw, scan_dir="up", direction="forward")

        np.testing.assert_array_equal(view.data_yx, self._corners())
        self.assertFalse(view.x_flip)
        self.assertFalse(view.y_flip)

    def test_physical_xy_down_backward_flips_x_and_y(self) -> None:
        raw = np.array([[12.0, 11.0], [22.0, 21.0]])

        view = self._prepare(raw, scan_dir="down", direction="backward")

        np.testing.assert_array_equal(view.data_yx, self._corners())
        self.assertTrue(view.x_flip)
        self.assertTrue(view.y_flip)

    def test_physical_xy_up_backward_flips_x_only(self) -> None:
        raw = np.array([[22.0, 21.0], [12.0, 11.0]])

        view = self._prepare(raw, scan_dir="up", direction="backward")

        np.testing.assert_array_equal(view.data_yx, self._corners())
        self.assertTrue(view.x_flip)
        self.assertFalse(view.y_flip)

    def test_nanonis_display_binds_scan_normalization_to_upper_origin(self) -> None:
        prepare = getattr(dataset_utils, "prepare_sxm_map", None)
        self.assertTrue(callable(prepare), "prepare_sxm_map public API is missing")
        raw = np.array([[21.0, 22.0], [11.0, 12.0]])

        view = prepare(
            raw,
            direction="forward",
            header={"scan_dir": "up"},
            frame="nanonis_display",
        )

        np.testing.assert_array_equal(
            view.data_yx,
            np.array([[11.0, 12.0], [21.0, 22.0]]),
        )
        self.assertEqual(view.plot_origin, "upper")
        self.assertTrue(view.y_flip)

    def test_legacy_normalizer_keeps_scan_display_order(self) -> None:
        raw = np.array([[21.0, 22.0], [11.0, 12.0]])

        legacy = dataset_utils.normalize_sxm_direction_map(
            raw,
            direction="backward",
            header={"scan_dir": "up"},
        )

        np.testing.assert_array_equal(
            legacy,
            np.array([[12.0, 11.0], [22.0, 21.0]]),
        )

    def test_legacy_normalizer_preserves_non_map_input(self) -> None:
        raw = np.array([1.0, 2.0, 3.0])

        legacy = dataset_utils.normalize_sxm_direction_map(
            raw,
            direction="backward",
            header={"scan_dir": "up"},
        )

        np.testing.assert_array_equal(legacy, raw)

    def test_legacy_normalizer_treats_unknown_direction_as_forward(self) -> None:
        raw = np.array([[1.0, 2.0], [3.0, 4.0]])

        legacy = dataset_utils.normalize_sxm_direction_map(
            raw,
            direction="reverse",
            header={"scan_dir": "down"},
        )

        np.testing.assert_array_equal(legacy, raw)

    def test_explicit_scan_dir_overrides_header(self) -> None:
        raw = np.array([[11.0, 12.0], [21.0, 22.0]])

        view = dataset_utils.prepare_sxm_map(
            raw,
            header={"scan_dir": "up"},
            scan_dir="down",
            frame="physical_xy",
        )

        np.testing.assert_array_equal(view.data_yx, self._corners())
        self.assertEqual(view.scan_dir, "down")
        self.assertTrue(view.y_flip)

    def test_explicit_orientation_rejects_unknown_frame_direction_and_scan_dir(self) -> None:
        prepare = getattr(dataset_utils, "prepare_sxm_map", None)
        self.assertTrue(callable(prepare), "prepare_sxm_map public API is missing")
        raw = np.ones((2, 2), dtype=float)

        with self.assertRaisesRegex(ValueError, "frame"):
            prepare(raw, frame="screen")
        with self.assertRaisesRegex(ValueError, "direction"):
            prepare(raw, direction="reverse")
        with self.assertRaisesRegex(ValueError, "scan_dir"):
            prepare(raw, header={"scan_dir": "sideways"})
        with self.assertRaisesRegex(ValueError, "2D"):
            prepare(np.ones(3), frame="physical_xy")

    def test_orientation_api_is_exported_from_analystm(self) -> None:
        import analystm

        self.assertTrue(callable(getattr(analystm, "prepare_sxm_map", None)))
        self.assertIsNotNone(getattr(analystm, "SXMMapView", None))


if __name__ == "__main__":
    unittest.main()
