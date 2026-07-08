from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


class AnalySTMPublicBackendTests(unittest.TestCase):
    def test_import_analystm_without_private_pysidam_root(self) -> None:
        env = dict(os.environ)
        env.pop("PYSIDAM_ROOT", None)
        env["PYTHONPATH"] = str(SRC)

        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import analystm; print(analystm.__version__)",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertRegex(proc.stdout.strip(), r"^\d+(?:\.\d+){1,2}")

    def test_cli_help_lists_public_agent_commands(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC)

        proc = subprocess.run(
            [sys.executable, "-m", "analystm", "--help"],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        for command in [
            "read",
            "plot-spectrum",
            "fit-gap",
            "gap-map",
            "multipeak",
            "intensity",
            "qpi",
            "spstm",
            "topography",
            "spectroscopy",
            "path-viz",
            "publication",
            "waterfall",
            "histogram",
            "crop",
            "export",
            "bragg",
            "phase-lockin",
            "atom",
            "domain-wall",
            "sjtm",
            "deconvolve",
        ]:
            self.assertIn(command, proc.stdout)

    def test_migrated_helpers_are_importable_from_analystm_namespace(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.atom_ai import lattice_qc, scale_recommendation
            from analystm.domain_wall import build_domain_wall_masks
            from analystm.io import build_read_parameters
            from analystm.phase_lockin import q_cycles_to_pysidam_px_yx
        finally:
            sys.path.remove(str(SRC))

        self.assertEqual(build_read_parameters()["divider"], 1.0)
        self.assertEqual(
            scale_recommendation(
                shape_yx=(512, 512),
                scan_size_nm_xy=(20.0, 20.0),
                resize_ratio=1.5,
                expected_spacing_nm=0.3515625,
            )["scale_status"],
            "preferred",
        )
        qc = lattice_qc(np.array([[0.0, 0.0], [0.37, 0.0], [0.0, 0.37], [0.37, 0.37]]), expected_spacing_nm=0.37)
        self.assertIn("passes", qc)
        masks = build_domain_wall_masks(
            shape_yx=(4, 5),
            scan_size_nm_xy=(5.0, 4.0),
            regions=[{"type": "x_band", "x_min_nm": 1.0, "x_max_nm": 2.0}],
        )
        self.assertEqual(masks["counts"]["on_dw"], 4)
        self.assertEqual(q_cycles_to_pysidam_px_yx((0.25, 0.0), (4, 4), (4.0, 4.0)), [1.5, 2.5])

    def test_gap_models_do_not_require_private_pysidam_package(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            models = importlib.import_module("analystm.models")
        finally:
            sys.path.remove(str(SRC))

        energy = np.linspace(-5.0, 5.0, 21)
        rho = models.evaluate_gap_model_raw(
            energy,
            models.MODEL_TWO_BAND_S,
            {"delta1_meV": 2.0, "delta2_meV": 1.0, "weight": 0.6},
        )

        self.assertEqual(rho.shape, energy.shape)
        self.assertTrue(np.isfinite(rho).all())
        self.assertGreater(float(np.max(rho)), 0.0)

    def test_read_signals_accepts_raw_3ds_through_analystm_nanonis_reader(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.io import load_signals
        finally:
            sys.path.remove(str(SRC))

        fake_grid = SimpleNamespace(signals={"LI Demod 1 X (A)": np.zeros((2, 3, 5))})
        fake_file = SimpleNamespace(obj=fake_grid)
        with patch("analystm.nanonis_io.read_nanonis_file", return_value=fake_file):
            signals, reader = load_signals("fake.3ds")

        self.assertEqual(reader, "analystm.nanonis_io.read_nanonis_file")
        self.assertIn("LI Demod 1 X (A)", signals)

    def test_public_backend_source_has_no_private_runtime_or_gui_dependency(self) -> None:
        package_root = SRC / "analystm"
        self.assertTrue(package_root.is_dir(), "src/analystm must exist")
        forbidden = [
            "PYSIDAM_ROOT",
            "pysidam.",
            "PyQt5",
            "pyqtgraph",
            "QApplication",
            "/Users/",
            "Project FeSe",
            "pysidam-origin-main",
        ]
        for path in package_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            bad = [token for token in forbidden if token in text]
            self.assertFalse(bad, f"{path.relative_to(ROOT)} contains forbidden public-backend token(s): {bad}")

    def test_atom_lattice_qc_cli_reads_csv_and_writes_json(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            atoms = root / "atoms.csv"
            atoms.write_text(
                "atom_id,x_nm,y_nm,class\n"
                "1,0.0,0.0,A\n"
                "2,0.37,0.0,B\n"
                "3,0.0,0.37,A\n"
                "4,0.37,0.37,B\n",
                encoding="utf-8",
            )
            out = root / "qc.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "analystm",
                    "atom",
                    "lattice-qc",
                    str(atoms),
                    "--expected-spacing-nm",
                    "0.37",
                    "--allow-qc-fail",
                    "--output-json",
                    str(out),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["tool"], "analystm atom lattice-qc")
            self.assertEqual(payload["coordinate_columns"], ["x_nm", "y_nm"])
            self.assertIn("passes", payload["result"])

    def test_domain_wall_build_masks_cli_writes_reusable_mask_package(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            regions = root / "regions.json"
            regions.write_text(
                json.dumps(
                    {
                        "regions": [
                            {
                                "type": "x_band",
                                "x_min_nm": 1.0,
                                "x_max_nm": 2.0,
                                "label": "DW",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out_dir = root / "dw"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "analystm",
                    "domain-wall",
                    "build-masks",
                    "--shape-yx",
                    "4",
                    "5",
                    "--scan-size-nm",
                    "5",
                    "4",
                    "--regions-json",
                    str(regions),
                    "--near-width-nm",
                    "1.0",
                    "--output-dir",
                    str(out_dir),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tool"], "analystm domain-wall build-masks")
            self.assertEqual(report["counts"]["on_dw"], 4)
            archive = np.load(out_dir / "data" / "domain_wall_masks.npz")
            self.assertIn("on_dw_mask", archive.files)
            self.assertIn("away_mask", archive.files)


if __name__ == "__main__":
    unittest.main()
