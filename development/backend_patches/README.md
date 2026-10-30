# Reviewable backend repair patches

Store a sanitized, reviewable patch for a focused adopted/reverted backend maintenance event here when it is appropriate to track publicly. The actual backend remains a separate ignored repository. This folder need not contain a patch when none exists.

Link each patch from [coding_pipeline_changes.md](../../coding_pipeline_changes.md), with backend base/result revisions and a digest. Preserve failed attempts too. Do not commit raw private logs, credentials, or large unreviewed bundles; use a protected backup reference instead when needed.

Create tracked patch artifacts only at a safe parent checkpoint. Pending maintenance records and isolated tests stay under ignored `local/` while the target is live or base-bound. A patch file here is evidence/maintenance material, not permission to apply it or resume an old run with changed code.
