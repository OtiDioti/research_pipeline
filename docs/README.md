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
metadata-only receipt reconciliation, and failure limits. Scientific assessment,
worker isolation and general migrations remain unsupported.

[Verified local backups](backups.md) documents explicit snapshot/inspection/restore
APIs, strict format and integrity checks, durable completeness markers, independent
continued use and a runnable synthetic example. This is partial R-019/R-017 evidence;
full D02, periodic scheduling and research-run/session/job recovery remain outstanding.

[Typed scientific content](typed-content.md) documents the four pure versioned
contracts, strict codecs, exact envelope links and structural limits. Its runnable
example requires no storage or execution. Typed durable admission/read remains
unimplemented; the trusted generic RecordStore is not a scientific admission gate.
