from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _two_peak_linecut() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    bias = np.linspace(-3.0, 3.0, 181)
    position = np.linspace(0.0, 4.0, 5)
    rows = []
    for idx, pos in enumerate(position):
        left = -1.05 + 0.04 * np.sin(pos)
        right = 1.10 + 0.03 * np.cos(pos)
        signal = (
            0.08
            + 0.015 * bias
            + (1.2 + 0.05 * idx) * np.exp(-((bias - left) ** 2) / (2.0 * 0.18**2))
            + (0.95 + 0.04 * idx) * np.exp(-((bias - right) ** 2) / (2.0 * 0.22**2))
        )
        rows.append(signal)
    return bias, position, np.asarray(rows, dtype=float)


class AnalySTMMultipeakTests(unittest.TestCase):
    def test_run_multipeak_fit_matches_pysidam_engine_contract(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.multipeak import run_multipeak_fit
        finally:
            sys.path.remove(str(SRC))

        bias, position, data = _two_peak_linecut()
        package = run_multipeak_fit(
            bias,
            position,
            data,
            n_peaks=2,
            fit_range=(-2.4, 2.4),
            fixed_sigma=0.20,
            background_mode="full_trace_linear",
            peak_snr_min=0.0,
            peak_amp_frac_min=0.0,
            r2_threshold=0.5,
            random_seed=7,
        )

        self.assertEqual(package["algorithm"]["engine"], "analystm.multipeak.run_multipeak_fit")
        self.assertIn("UniversalVortexFitterEngine.run_fit", package["algorithm"]["pysidam_source_mapping"])
        outputs = package["outputs"]
        self.assertEqual(outputs["centers"].shape, (position.size, 2))
        self.assertEqual(outputs["amps"].shape, (position.size, 2))
        self.assertEqual(outputs["sigmas"].shape, (position.size, 2))
        self.assertEqual(outputs["r2"].shape, (position.size,))
        self.assertGreaterEqual(package["summary"]["successful_fits"], 4)

        centers = np.sort(outputs["centers"], axis=1)
        self.assertLess(abs(float(np.nanmedian(centers[:, 0])) + 1.05), 0.15)
        self.assertLess(abs(float(np.nanmedian(centers[:, 1])) - 1.10), 0.15)

    def test_universal_vortex_fitter_engine_remains_public(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from analystm.multipeak import UniversalVortexFitterEngine
        finally:
            sys.path.remove(str(SRC))

        bias, position, data = _two_peak_linecut()
        engine = UniversalVortexFitterEngine(bias, position, data)
        summary = engine.run_fit(
            n_peaks=2,
            fit_range=(-2.4, 2.4),
            fixed_sigma=0.20,
            background_mode="full_trace_linear",
            peak_snr_min=0.0,
            peak_amp_frac_min=0.0,
            r2_threshold=0.5,
        )
        payload = engine.collect_debug_state_payload(n_peaks=2)

        self.assertGreaterEqual(summary["valid_count"], 4)
        self.assertEqual(payload["n_peaks"], 2)
        self.assertEqual(payload["centers"].shape, (position.size, 2))
        self.assertEqual(str(payload["background_mode"]), "full_trace_linear")

    def test_multipeak_cli_writes_outputs_and_report(self) -> None:
        env = dict()
        env.update({"PYTHONPATH": str(SRC)})
        bias, position, data = _two_peak_linecut()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "linecut.npz"
            out_dir = root / "out"
            np.savez_compressed(src, bias=bias, position=position, data=data)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "analystm",
                    "multipeak",
                    "fit",
                    str(src),
                    "--bias-key",
                    "bias",
                    "--position-key",
                    "position",
                    "--data-key",
                    "data",
                    "--n-peaks",
                    "2",
                    "--fit-range",
                    "-2.4",
                    "2.4",
                    "--fixed-sigma",
                    "0.20",
                    "--background-mode",
                    "full_trace_linear",
                    "--peak-snr-min",
                    "0.0",
                    "--peak-amp-frac-min",
                    "0.0",
                    "--r2-threshold",
                    "0.5",
                    "--random-seed",
                    "7",
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
            self.assertEqual(report["tool"], "analystm multipeak fit")
            self.assertIn("UniversalVortexFitterEngine.run_fit", report["algorithm"]["pysidam_source_mapping"])
            self.assertTrue((out_dir / "multipeak_outputs.npz").exists())
            self.assertTrue((out_dir / "multipeak_summary.csv").exists())
            saved = np.load(out_dir / "multipeak_outputs.npz")
            self.assertEqual(saved["centers"].shape, (position.size, 2))


if __name__ == "__main__":
    unittest.main()
