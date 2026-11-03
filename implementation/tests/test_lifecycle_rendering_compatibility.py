"""Frozen pre-extraction v1/v2 source and output references; predecessor fixture remains untouched."""

import hashlib
import json
from pathlib import Path
import unittest
from research_pipeline.reports import ReportObservation, dumps_observation, render_report


class LegacyRenderingCompatibilityTests(unittest.TestCase):
    """Pin historical bytes to independently supplied accepted references, never generated expectations."""

    def test_both_frozen_versions(self):
        """Verify fixture identity, exact canonical source identity and complete legacy outputs for both versions."""
        fixture = (Path(__file__).parent / 'fixtures/report_v1.json').read_bytes()
        self.assertEqual(hashlib.sha256(fixture).hexdigest(), '1bf3616c77c25736fe247e679d9e9e27b265c0c2da0981dc17fa9cd19e36c7ef')
        # Accepted fixture blob b71b783054ded895f8a65f225def0eb9785b1dd7;
        # pre-extraction reports.py blob 53a6087ca0dc575f3792199a6ef7a258bf5e71e8.
        original = json.loads(fixture)['objects']['source.json']
        cases = (
            (1, '8d836d48a4b275bbb5220533243eeb9323e9baba37060bc32b2b9aa5a3f31dd6',
             'c64fec2a1c9f121d273c1bd59c6bc894815519ae887cdff5138b0254836f130e', 7618,
             'f4680b14aa068100b96ec2cad457b13fb720ef36b65fde9ae6c4357608f0c6b6',
             '211cf063b9dec29195b5485d7e96d61991698e6c13809b90e6332c2903529afa'),
            (2, 'fff39849573c0d4fe0b4b6c8d4281601df734454ae4c5f263ca1ba210225e3ce',
             '88da7edd099f119cf866ea89d07d36e5218b7b9a4f0bf230b7fd2d07ab087b1c', 7697,
             '2c9d7ee54ae4611c246aab371b20a0998b832277220d737523c50be5d20ee613',
             '0a2a1e543e19f6220e2dcfdf94c15234a593f06ccc531de87ba659818fecc42f'))
        for version, source_hash, snapshot, md_size, md_hash, continuation_hash in cases:
            with self.subTest(version=version):
                value = json.loads(original)
                if version == 2:
                    value['version'] = 2
                    payload = {k: v for k, v in value.items() if k != 'snapshot_id'}
                    value['snapshot_id'] = hashlib.sha256(json.dumps(payload, sort_keys=True,
                        separators=(',', ':'), ensure_ascii=True).encode('ascii')).hexdigest()
                observation = ReportObservation(value)
                data = dumps_observation(observation).encode('ascii')
                self.assertEqual((len(data), hashlib.sha256(data).hexdigest()), (8167, source_hash))
                self.assertEqual(value['snapshot_id'], snapshot)
                outputs = render_report(observation)
                self.assertEqual(set(outputs), {'report.md', 'continuation.json'})
                for name, size, digest in (('report.md', md_size, md_hash), ('continuation.json', 6898, continuation_hash)):
                    self.assertEqual((len(outputs[name]), hashlib.sha256(outputs[name]).hexdigest()), (size, digest))
