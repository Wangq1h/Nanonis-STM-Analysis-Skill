from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from pysidam_agent_core.domain_wall import build_domain_wall_masks
from scripts.pysidam_agent.domain_wall import load_numeric_map, write_mask_outputs


class DomainWallCliTests(unittest.TestCase):
    def test_load_numeric_map_reads_npy_and_npz(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            arr = np.arange(6, dtype=float).reshape(2, 3)
            np.save(root / "map.npy", arr)
            np.savez(root / "maps.npz", primary=arr)

            np.testing.assert_array_equal(load_numeric_map(root / "map.npy")[0], arr)
            np.testing.assert_array_equal(load_numeric_map(root / "maps.npz", npz_key="primary")[0], arr)

    def test_write_mask_outputs_saves_npz_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            masks = build_domain_wall_masks(
                shape_yx=(4, 5),
                scan_size_nm_xy=(5.0, 4.0),
                regions=[{"type": "x_band", "x_min_nm": 1.0, "x_max_nm": 2.0, "label": "DW"}],
            )

            outputs = write_mask_outputs(
                output_dir=root,
                masks=masks,
                source={"source": "unit-test"},
                policy={"mode": "user_preapproved_regions"},
            )

            report = json.loads(Path(outputs["report_json"]).read_text(encoding="utf-8"))
            self.assertEqual(report["tool"], "pysidam_agent/domain_wall.py build-masks")
            self.assertEqual(report["analysis"]["policy"], "user_preapproved_regions")
            archive = np.load(outputs["masks_npz"])
            self.assertIn("on_dw_mask", archive.files)
            self.assertIn("away_mask", archive.files)


if __name__ == "__main__":
    unittest.main()
