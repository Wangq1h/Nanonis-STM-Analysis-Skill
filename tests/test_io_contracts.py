from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
