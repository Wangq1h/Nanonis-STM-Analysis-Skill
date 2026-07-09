from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"


def load_script(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RuntimeDefaultsTests(unittest.TestCase):
    def test_default_probe_modules_exclude_legacy_ui_and_ai_detector(self) -> None:
        probe_runtime = load_script("probe_runtime")

        modules = getattr(probe_runtime, "DEFAULT_MODULES", getattr(probe_runtime, "MODULES"))
        module_names = {name for name, _tier in modules}

        self.assertIn("analystm", module_names)
        self.assertIn("nanonispy", module_names)
        self.assertIn("igorwriter", module_names)
        self.assertNotIn("pysidam", module_names)
        self.assertNotIn("PyQt5.QtCore", module_names)
        self.assertNotIn("pyqtgraph", module_names)
        self.assertNotIn("Atom_Identificator_core", module_names)

    def test_default_probe_json_does_not_report_legacy_ui_or_ai_as_missing(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "probe_runtime.py"), "--json"],
            cwd=ROOT,
            env={"PYTHONPATH": str(SRC)},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        module_names = {item["module"] for item in payload["modules"]}
        capability_names = set(payload["capabilities"])

        self.assertNotIn("pysidam", module_names)
        self.assertNotIn("PyQt5.QtCore", module_names)
        self.assertNotIn("pyqtgraph", module_names)
        self.assertNotIn("Atom_Identificator_core", module_names)
        self.assertNotIn("ibw_import_via_pysidam", capability_names)
        self.assertNotIn("ui_wrapped_modules", capability_names)
        self.assertEqual(payload["capabilities"]["ai_atom_detection"], "planned")

    def test_bootstrap_headless_and_all_groups_do_not_include_ui_or_ai(self) -> None:
        bootstrap_runtime = load_script("bootstrap_runtime")

        self.assertEqual(bootstrap_runtime.parse_groups("headless"), ["core", "nanonis", "ibw"])
        self.assertEqual(bootstrap_runtime.parse_groups("all"), ["core", "nanonis", "ibw"])
        self.assertNotIn("ui", bootstrap_runtime.GROUP_REQUIREMENTS)
        self.assertNotIn("ai", bootstrap_runtime.GROUP_ALIASES["all"])

    def test_resolver_bootstrap_command_ignores_pysidam_host_by_default(self) -> None:
        resolve_runtime = load_script("resolve_runtime")

        command = resolve_runtime.build_bootstrap_command(
            {
                "base_python": "/usr/bin/python3",
                "default_groups": "headless",
                "pysidam_root": "/tmp/legacy-pysidam",
            },
            Path("/tmp/stm-cache"),
        )

        self.assertNotIn("--pysidam-root", command)
        self.assertNotIn("/tmp/legacy-pysidam", command)
        self.assertIn("--pysidam-mode", command)
        mode_index = command.index("--pysidam-mode")
        self.assertEqual(command[mode_index + 1], "none")


if __name__ == "__main__":
    unittest.main()
