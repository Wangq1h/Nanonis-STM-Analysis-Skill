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


class AnalySTMPublicationTests(unittest.TestCase):
    def test_publication_payload_helpers_match_pysidam_geometry_rules(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.publication import (
                FigurePayload,
                ImagePayload,
                LinePayload,
                apply_image_contrast,
                axis_centers_from_extent,
                downsample_image_for_editor,
                nice_length,
                payload_data_limits,
                regularize_image_extent,
                suggest_scalebar_length,
                thin_line_points,
            )
        finally:
            sys.path.remove(str(SRC))

        image = np.arange(10, dtype=float).reshape(1, 10)
        extent = regularize_image_extent(image, (0.0, 10.0, 2.0, 2.0))
        self.assertLess(extent[2], 2.0)
        self.assertGreater(extent[3], 2.0)
        np.testing.assert_allclose(axis_centers_from_extent(0.0, 10.0, 5), [1, 3, 5, 7, 9])
        x, y = thin_line_points(np.arange(10), np.arange(10) ** 2, max_points=4)
        self.assertEqual(x.size, 4)
        large = np.zeros((2000, 2000), dtype=float)
        self.assertLess(downsample_image_for_editor(large).shape[0], large.shape[0])
        payload = FigurePayload(
            images=[ImagePayload(data=np.arange(9).reshape(3, 3), extent=(0.0, 3.0, 0.0, 3.0))],
            lines=[LinePayload(x=np.array([0.0, 4.0]), y=np.array([-1.0, 1.0]), label="line")],
        )
        xlim, ylim = payload_data_limits(payload)
        self.assertLess(xlim[0], 0.0)
        self.assertGreater(ylim[1], 3.0)
        self.assertEqual(nice_length(2.8), 2.0)
        self.assertEqual(suggest_scalebar_length(payload.images[0]), 0.5)
        self.assertEqual(apply_image_contrast(np.array([-2.0, 0.0, 3.0]), mode="symmetric"), (-3.0, 3.0))

    def test_publication_cli_writes_payload_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = root / "pub.npz"
            np.savez_compressed(inp, image=np.arange(9, dtype=float).reshape(3, 3), x=np.arange(5.0), y=np.arange(5.0) ** 2)
            out_dir = root / "pub_out"

            proc = _run_analystm(
                [
                    "publication",
                    "payload",
                    str(inp),
                    "--image-key",
                    "image",
                    "--x-key",
                    "x",
                    "--y-key",
                    "y",
                    "--output-dir",
                    str(out_dir),
                ]
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tool"], "analystm publication payload")
            self.assertEqual(report["summary"]["image_count"], 1)
            self.assertTrue((out_dir / "publication_payload.json").is_file())


if __name__ == "__main__":
    unittest.main()
