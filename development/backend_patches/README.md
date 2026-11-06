# Reviewable backend repair patches

Indexes preserved backend patches, backups and their audited adoption evidence.

Store a sanitized, reviewable patch for a focused adopted/reverted backend maintenance event here when it is appropriate to track publicly. The actual backend remains a separate ignored repository. This folder need not contain a patch when none exists.

Link each patch from its [backend incident record](../backend_changes/README.md), with backend base/result revisions and a digest; [coding_pipeline_changes.md](../../coding_pipeline_changes.md) indexes that record. Preserve failed attempts too. Do not commit raw private logs, credentials, or large unreviewed bundles; use a protected backup reference instead when needed.

Create tracked patch artifacts only at a safe parent checkpoint. Pending maintenance records and isolated tests stay under ignored `local/` while the target is live or base-bound. A patch file here is evidence/maintenance material, not permission to apply it or resume an old run with changed code.

- [CP-001 private final response](CP-001-private-final-response.patch): adopted backend c74df0b09b4883776b1889b859b2df065f0b2fe4, SHA25609983a00373d16f0c381cdf3c0dbd7d2fbfc61c22d64091fe6b0b9d1cccecd86; see [the CP-001 incident record](../backend_changes/CP-001.md) for tests, failed environment checks, exact adoption and recovery limits.
- [CP-004 final-only controller validation](CP-004-final-only-validation.patch): adopted backend `66f10ff82c54af103583ba8963c1bd12c9254e24`, SHA-256 `084874bc68f5fd6df25355b68b681caed6ca182cca60d49445c5a04e1a02316b`; see [the feature audit](../backend_changes/CP-004.md) for complete coverage, actual tool-boundary checks, source variants and historical-run restrictions.

CP-001 is a zero-context unified patch; use `git apply --unidiff-zero` if applying it to the recorded backend base. The exact full-context patch is also retained locally as documented in the audit.
