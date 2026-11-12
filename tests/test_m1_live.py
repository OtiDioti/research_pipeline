import os
import unittest
@unittest.skipUnless(os.environ.get("RESEARCH_PIPELINE_M1_LIVE") == "1", "historical paid gate disabled")
class LiveM1Acceptance(unittest.TestCase):
    def test_legacy_gate_is_explicitly_rejected(self):
        self.fail("The timed M1 harness is superseded. Do not repeat accepted science; use tests.test_v0_l1_native for L1 and the future V0-L6 integrated lifecycle harness.")
