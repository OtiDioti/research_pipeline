# Product documentation

Architecture, interfaces, operational guidance, and user documentation belong here as the product is implemented. The existing [project description](../project_description.md) remains the requirements reference.

Development control records are under [development/](../development/README.md). Scientific investigation notes belong in research project vaults, not in this folder by default.

Document implemented behavior and limitations explicitly. Do not present a planned capability as available.

The implemented [foundation architecture](architecture.md) describes the package,
CLI, validator, test isolation, and current limits. See the
[implementation guide](../implementation/README.md) for exact local commands.

The [synthetic oscillator paper walkthrough](synthetic-oscillator.md) traces the
development fixture, its public loading/validation contract, expected outcomes and
expert-review gaps. It is synthetic local material, not a scientific execution or
expert-audited evaluation set.

The [durable records and atomic submissions](durable-records.md) guide gives the
local Python API, an executable low-level generic graph/append/reopen example,
fingerprint and ordering semantics, ownership and durability rules, SQLite recovery and locking behavior,
metadata-only receipt reconciliation, and failure limits. Scientific truth/authority
verification, worker isolation and general migrations remain unsupported.

[Verified local backups](backups.md) documents explicit snapshot/inspection/restore
APIs, strict format and integrity checks, durable completeness markers, independent
continued use, exact restore defaults and explicit attributed v1→v2 migration.
Runnable synthetic examples include a source-local legacy fixture, historical
receipt preservation and a subsequent v2 backup. This is partial R-019/R-017 evidence;
full D02, periodic scheduling and research-run/session/job recovery remain outstanding.

[Typed scientific content](typed-content.md) documents the four pure versioned
contracts, strict codecs, exact envelope links, durable typed admission/read and
structural limits. Runnable codec and synthetic persistence examples demonstrate
exact historical scope and original-receipt retries. `submit_typed` is the explicit
structural admission boundary; generic `submit` is not a scientific admission gate.

[Attributed assessments](attributed-assessments.md) documents Review/Issue contracts,
independent reported dimensions, route judgments, exact envelopes and durable
admission/read alongside the four scientific kinds. Its executed synthetic example
retains disagreeing reviewers and separate Issue revisions through reopen and exact
restore. Exact route membership is structural; current eligibility/freshness,
Apply disposition and scientific qualification remain future work.

[Work-product manifests](work-products.md) documents immutable multi-file bundles,
portable path and alias rules, strict codecs, exact optional supersession and typed
admission alongside scientific/assessment values. The runnable example persists and
reopens a manifest without executing its bytes. Build/input references grant no
authority; checkout and preview/import remain later milestones, and D02 is partial.
