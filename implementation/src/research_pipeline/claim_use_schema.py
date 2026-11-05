"""Exact freshness projections and independent registration, policy and context origins.

Only explicit creation or verified forward migration installs these contracts.
"""

FRESHNESS_DDL = (
    """CREATE TABLE claim_use_origin (
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
        event_watermark INTEGER NOT NULL CHECK(typeof(event_watermark) = 'integer' AND event_watermark >= 0)
    )""",
    """CREATE TABLE claim_use_bindings (
        use_id TEXT NOT NULL, binding_revision INTEGER NOT NULL,
        registration_event INTEGER NOT NULL REFERENCES audit_events(event_id),
        PRIMARY KEY(use_id,binding_revision),
        UNIQUE(use_id,binding_revision,registration_event),
        FOREIGN KEY(use_id,binding_revision) REFERENCES revisions(record_id,revision)
    )""",
    """CREATE TABLE claim_use_dependencies (
        use_id TEXT NOT NULL, binding_revision INTEGER NOT NULL,
        ordinal INTEGER NOT NULL CHECK(typeof(ordinal) = 'integer' AND ordinal >= 0),
        target_id TEXT NOT NULL, target_revision INTEGER NOT NULL, target_kind TEXT NOT NULL,
        role TEXT NOT NULL, context_id TEXT NOT NULL, context_revision INTEGER NOT NULL,
        route_ordinal INTEGER NOT NULL, premise_ordinal INTEGER NOT NULL,
        registration_event INTEGER NOT NULL,
        PRIMARY KEY(use_id,binding_revision,ordinal),
        FOREIGN KEY(use_id,binding_revision) REFERENCES claim_use_bindings(use_id,binding_revision),
        FOREIGN KEY(use_id,binding_revision,registration_event)
            REFERENCES claim_use_bindings(use_id,binding_revision,registration_event),
        FOREIGN KEY(target_id,target_revision) REFERENCES revisions(record_id,revision)
    )""",
    """CREATE TABLE claim_use_upstreams (
        use_id TEXT NOT NULL, binding_revision INTEGER NOT NULL,
        route_ordinal INTEGER NOT NULL, premise_ordinal INTEGER NOT NULL,
        upstream_id TEXT NOT NULL, upstream_revision INTEGER NOT NULL,
        registration_event INTEGER NOT NULL,
        PRIMARY KEY(use_id,binding_revision,route_ordinal,premise_ordinal),
        FOREIGN KEY(use_id,binding_revision) REFERENCES claim_use_bindings(use_id,binding_revision),
        FOREIGN KEY(use_id,binding_revision,registration_event)
            REFERENCES claim_use_bindings(use_id,binding_revision,registration_event),
        FOREIGN KEY(upstream_id,upstream_revision) REFERENCES claim_use_bindings(use_id,binding_revision)
            DEFERRABLE INITIALLY DEFERRED
    )""",
    """CREATE TABLE claim_use_generations (
        use_id TEXT NOT NULL, generation INTEGER NOT NULL CHECK(typeof(generation) = 'integer' AND generation > 0),
        binding_revision INTEGER NOT NULL,
        submission_id TEXT NOT NULL REFERENCES submissions(submission_id),
        event_id INTEGER NOT NULL REFERENCES audit_events(event_id),
        status TEXT NOT NULL CHECK(status = 'requires_reassessment'), causes_json TEXT NOT NULL,
        PRIMARY KEY(use_id,generation), UNIQUE(use_id,event_id), UNIQUE(use_id,submission_id),
        FOREIGN KEY(use_id,binding_revision) REFERENCES claim_use_bindings(use_id,binding_revision)
    )""",
    """CREATE TABLE claim_use_current (
        use_id TEXT PRIMARY KEY NOT NULL, binding_revision INTEGER NOT NULL,
        generation INTEGER NOT NULL CHECK(typeof(generation) = 'integer' AND generation > 0),
        status TEXT NOT NULL CHECK(status = 'requires_reassessment'), last_event INTEGER NOT NULL REFERENCES audit_events(event_id),
        FOREIGN KEY(use_id,generation) REFERENCES claim_use_generations(use_id,generation),
        FOREIGN KEY(use_id,binding_revision) REFERENCES claim_use_bindings(use_id,binding_revision)
    )""",
    "CREATE INDEX claim_use_dependency_target ON claim_use_dependencies(target_id,target_revision,target_kind,registration_event,use_id,binding_revision,ordinal)",
    "CREATE INDEX claim_use_dependency_watch ON claim_use_dependencies(target_id,target_kind,role,registration_event,use_id,binding_revision,ordinal)",
    "CREATE INDEX claim_use_upstream_target ON claim_use_upstreams(upstream_id,upstream_revision,registration_event,use_id,binding_revision,route_ordinal,premise_ordinal)",
    "CREATE INDEX claim_use_binding_event ON claim_use_bindings(registration_event)",
    "CREATE INDEX claim_use_generation_event ON claim_use_generations(event_id,use_id)",
    "CREATE INDEX claim_use_generation_use_event ON claim_use_generations(use_id,event_id,generation)",
    """CREATE TABLE claim_use_revision_events (
        record_id TEXT NOT NULL, revision INTEGER NOT NULL,
        event_id INTEGER NOT NULL REFERENCES audit_events(event_id),
        PRIMARY KEY(record_id,revision), UNIQUE(record_id,revision,event_id),
        FOREIGN KEY(record_id,revision) REFERENCES revisions(record_id,revision)
    )""",
    "CREATE INDEX claim_use_revision_event ON claim_use_revision_events(record_id,event_id,revision)",
    """CREATE TABLE claim_use_association_links (
        record_id TEXT NOT NULL, revision INTEGER NOT NULL, ordinal INTEGER NOT NULL,
        event_id INTEGER NOT NULL,
        relationship TEXT NOT NULL CHECK(relationship IN ('candidate_claim','assessed_route','affected_record')),
        target_id TEXT NOT NULL, target_revision INTEGER NOT NULL,
        PRIMARY KEY(record_id,revision,ordinal),
        FOREIGN KEY(record_id,revision,ordinal) REFERENCES record_links(record_id,revision,ordinal),
        FOREIGN KEY(record_id,revision,event_id) REFERENCES claim_use_revision_events(record_id,revision,event_id)
    )""",
    "CREATE INDEX claim_use_association_target ON claim_use_association_links(target_id,target_revision,event_id,relationship,record_id,revision,ordinal)",
)

# Policy activation is independent of registration activation: migrating preserves
# every previously stored transition and only enables new policy events.
POLICY_ORIGIN_DDL = """CREATE TABLE claim_use_policy_origin (
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
        event_watermark INTEGER NOT NULL CHECK(typeof(event_watermark) = 'integer' AND event_watermark >= 0)
    )"""

# Target-context activation is independent of earlier registration/policy events.
CONTEXT_ORIGIN_DDL = """CREATE TABLE claim_use_context_origin (
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
        event_watermark INTEGER NOT NULL CHECK(typeof(event_watermark) = 'integer' AND event_watermark >= 0)
    )"""
