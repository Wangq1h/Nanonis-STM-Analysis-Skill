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


class AnalySTMPathVizTests(unittest.TestCase):
    def test_path_viz_batches_match_pysidam_pending_segment_logic(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.path_viz import autoscale_bounds, build_path_from_batches, path_log_rows
        finally:
            sys.path.remove(str(SRC))

        package = build_path_from_batches(
            [
                {"moves": [("+X", 3), ("+Y", 2)], "z": 5, "mark": "Good"},
                {"moves": [("-X", 1)], "z": 2, "mark": "Bad"},
            ]
        )

        self.assertEqual(package["points"], [(0.0, 0.0), (3.0, 0.0), (3.0, 2.0), (2.0, 2.0)])
        self.assertEqual(package["steps"][0]["move"], "+X 3 -> +Y 2")
        rows = path_log_rows(package["steps"])
        self.assertEqual(rows[0]["End (x,y)"], "(3.00, 2.00)")
        self.assertEqual(rows[1]["Mark"], "Bad")
        fit_bounds = autoscale_bounds(package["points"], mode="fit")
        origin_bounds = autoscale_bounds(package["points"], mode="origin")
        self.assertLess(fit_bounds["xlim"][0], 0.0)
        self.assertEqual(origin_bounds["xlim"][0], -origin_bounds["xlim"][1])
        self.assertIn("usefultools_path_viz", package["algorithm"]["pysidam_source_mapping"])

    def test_path_viz_cli_writes_json_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "path.json"
            plan.write_text(
                json.dumps(
                    {
                        "batches": [
                            {"moves": [["+X", 3], ["+Y", 2]], "z": 5, "mark": "Good"},
                            {"moves": [["-X", 1]], "z": 2, "mark": "Bad"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out_dir = root / "path_out"
            proc = _run_analystm(["path-viz", "build", str(plan), "--output-dir", str(out_dir)])

            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tool"], "analystm path-viz build")
            self.assertEqual(report["summary"]["step_count"], 2)
            self.assertTrue((out_dir / "path_log.csv").is_file())
            self.assertTrue((out_dir / "path_points.json").is_file())


if __name__ == "__main__":
    unittest.main()
