# Status

**2026-11-14.** V0 restart. The new [PROJECT.md](PROJECT.md) is approved, and the old
specifications, code, tests and development evidence have been removed from `main`.

- Previous state: tag `pre-v0-restart` (accepted L1–L4 at `3a23c69`). The unmerged
  L5 work is on the remote branch `cwi/20261113T063709_7f21ba4a`. Reuse parts only
  where they fit the new design.
- Kept: `research_example/` (benchmark inputs and the archived 2026-11-11 attempt).
- Transport and confinement assumptions verified live with Codex and Claude Code
  (PROJECT.md §12). Decision: one `bwrap` per agent session for every CLI.

**Next:** design and hand-build the core (PROJECT.md §12, "Order").
