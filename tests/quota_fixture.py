"""Explicit sufficient account observation for local engineering doubles only."""
from research_pipeline import quota


PAYLOAD = {'rateLimits': {'limitId': 'engineering-fixture',
    'secondary': {'windowDurationMins': 10080, 'usedPercent': 20}}}


def sufficient(runtime):
    quota.observe(runtime.state['quota'], PAYLOAD,
        full=True, provenance='injected-engineering-fixture')
    runtime.save()
