from __future__ import annotations

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


def _run_analystm(args: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "analystm", *args],
        cwd=cwd,
        env=_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class AnalySTMExportTests(unittest.TestCase):
    def test_spec_dat_writer_matches_pysidam_header_and_value_format(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.export import build_nanonis_spec_header, format_nanonis_data_value, write_nanonis_spec_dat
        finally:
            sys.path.remove(str(SRC))

        self.assertEqual(format_nanonis_data_value(1230.0), "1.2300000E+3")
        self.assertEqual(format_nanonis_data_value(-0.001), "-1.0000000E-3")
        header = build_nanonis_spec_header({"User": "alice", "Comment01": "kept"}, extra_comments=["generated"])
        self.assertEqual(header["User"], "alice")
        self.assertEqual(header["Comment01"], "kept")
        self.assertEqual(header["Comment02"], "generated")

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "spec.dat"
            write_nanonis_spec_dat(
                out,
                [("Bias calc (V)", [-0.001, 0.0, 0.001]), ("LI Demod 1 X (A)", [1e-12, 2e-12, 3e-12])],
                header={"User": "alice"},
                extra_comments=["AnalySTM export"],
                saved_date="01.01.2026 00:00:00",
            )
            text = out.read_text(encoding="utf-8")
            self.assertIn("User\talice\t", text)
            self.assertIn("[DATA]", text)
            self.assertIn("Bias calc (V)\tLI Demod 1 X (A)", text)
            self.assertIn("-1.0000000E-3\t1.0000000E-12", text)

    def test_grid_3ds_writer_header_and_payload_size_match_contract(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.export import write_nanonis_grid_3ds
        finally:
            sys.path.remove(str(SRC))

        cube = np.arange(2 * 3 * 4, dtype=float).reshape(2, 3, 4)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "grid.3ds"
            write_nanonis_grid_3ds(out, {"LI Demod 1 X (A)": cube}, bias_mV=np.linspace(-1, 1, 4), scan_size_nm=12.0)
            raw = out.read_bytes()
            marker = b":HEADER_END:\r\n"
            header_blob, payload = raw.split(marker, 1)
            header = header_blob.decode("utf-8")
            self.assertIn("Grid dim=2 x 3", header)
            self.assertIn("Points=4", header)
            self.assertIn("Channels=LI Demod 1 X (A)", header)
            self.assertIn("# Parameters (4 byte)=10", header)
            self.assertEqual(len(payload), 3 * 2 * (10 + 4) * 4)

    def test_export_cli_writes_spec_dat_and_grid_3ds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = root / "export_inputs.npz"
            cube = np.arange(2 * 3 * 4, dtype=float).reshape(2, 3, 4)
            np.savez_compressed(inp, bias=np.linspace(-1, 1, 4), signal=np.arange(4, dtype=float), cube=cube)

            spec_out = root / "out.dat"
            spec_proc = _run_analystm(
                [
                    "export",
                    "spec-dat",
                    str(inp),
                    "--output",
                    str(spec_out),
                    "--column",
                    "Bias calc (V)=bias",
                    "--column",
                    "LI Demod 1 X (A)=signal",
                    "--saved-date",
                    "01.01.2026 00:00:00",
                ]
            )
            self.assertEqual(spec_proc.returncode, 0, spec_proc.stderr)
            self.assertTrue(spec_out.is_file())
            self.assertIn("[DATA]", spec_out.read_text(encoding="utf-8"))

            grid_out = root / "out.3ds"
            grid_proc = _run_analystm(
                [
                    "export",
                    "grid-3ds",
                    str(inp),
                    "--output",
                    str(grid_out),
                    "--bias-key",
                    "bias",
                    "--channel",
                    "LI Demod 1 X (A)=cube",
                    "--scan-size-nm",
                    "12",
                ]
            )
            self.assertEqual(grid_proc.returncode, 0, grid_proc.stderr)
            self.assertTrue(grid_out.is_file())
            self.assertIn(b":HEADER_END:\r\n", grid_out.read_bytes())


if __name__ == "__main__":
    unittest.main()
