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
authority. [Safe durable checkout](checkout.md) adds bounded independent writable
copies, explicit exclusion roots, untrusted descriptors and durable incomplete-marker
publication, with an executed example. [Preview and explicit import](work-product-import.md)
adds canonical base validation,
bounded capture, change summaries and durable frozen proposals for separate typed
commit and original-ID recovery, with an executed round-trip example. D02 is partial.

[Versioned Source captures](sources.md) documents bounded typed acquisition declarations,
unknown metadata, original/derived lineage and locations, independent capture/upstream/report
versions, history admission and exact reference projections. Its runnable synthetic
persistence example appends and reopens captures without parsing or claiming reading.
Legacy generic sources and shallow source links remain supported.
[Bounded local Source capture](source-capture.md) adds explicit file selection, strict
saved proposals, separate commit and original-ID recovery. Scientific readiness and
D02/D03/M0-S qualifications remain partial/pending.


[Immutable seed inventories](corpus.md) documents strict CorpusManifest values,
exact original Source selection/location checks, attributed inspection and unresolved
links, immutable baseline/replacement history, complete traversal/projection tables,
recovery semantics and a runnable two-capture example. Empty/partial inventories
are recorded setup data; attributed readiness proposals are recorded by project
intake, while actual admission, authority and scientific interpretation remain later work.


[Versioned project intake](project-intake.md) specifies ProjectSetup constructors,
strict codecs, corpus/document/location history and readiness proposals without
authority. It contains the complete canonical ten-kind traversal/projection
tables and a self-contained runnable synthetic setup example.

[Immutable private readable snapshots](readable-snapshots.md) capture an explicit bounded
project/outgoing metadata closure in one read transaction and produce deterministic
companions, inert artifact-copy expectations, canonical manifests and verified relative
navigation. Protected independent copies publish through an exclusive atomic rename;
read-only offline inspection compares current bytes with the canonical plan. Plans
retain expectations separately from observed materialization/inspection results.
