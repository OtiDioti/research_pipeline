<!-- cwi:decisions -->
Fixed the native gate’s accounting assumption: preserve counters and uncertainty records, verify increased resumed usage, and disclose incomplete totals as lower bounds. Production behavior is unchanged. Updated documentation and regressions.
<!-- /cwi:decisions -->
<!-- cwi:tests -->
Focused suite: 49 tests, one skipped. Full discovery: 416 tests, ten skipped; no failures.

Read-only checks against retained native evidence passed. Fresh native/process gates failed preflight because Writer lacks the authorized user bus; trusted final/combined validation remains required.
<!-- /cwi:tests -->
CWI: ready
