"""Disposable refresh fixtures reusing accepted capture/prior-state helpers."""

from dataclasses import replace

from research_pipeline.view_refresh import RefreshLimits, refresh_readable_view, inspect_readable_refresh
from tests.view_capture_fixtures import CaptureFixture, capture_limits, SOURCE
from tests.snapshot_fixtures import limits


def refresh_limits(**changes):
    """Supply every independent allowance explicitly, with focused boundary overrides."""
    return replace(RefreshLimits(capture_limits(), limits(), 10000, 5000, 5000, 40,
                   50_000_000, 200_000_000, 200_000_000, 20000, 4096), **changes)


class RefreshFixture(CaptureFixture):
    """Setup/helpers only; concrete test classes do not inherit test-bearing classes."""

    def refresh(self, destination=None, **changes):
        """Refresh a pinned fixture at a distinct absent sibling, accepting explicit test overrides."""
        arguments = dict(expected_plan=self.plan, new_plan=self.plan, source_root=SOURCE,
                         protected_roots=[], limits=refresh_limits())
        arguments.update(changes)
        return refresh_readable_view(self.store, self.view, destination or self.parent / "successor", **arguments)

    def inspect(self, result, **changes):
        """Inspect caller-specified retained evidence under independent fixture allowances."""
        arguments = dict(source_root=SOURCE, protected_roots=[self.runtime], limits=refresh_limits())
        arguments.update(changes)
        return inspect_readable_refresh(result.attempt_path, result.destination, **arguments)
