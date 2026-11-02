"""Pure authority wire, detached state, strict bounds and domain-separated host authentication."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import hashlib
import hmac
import json
import unittest

from research_pipeline import operating_authority as a
from research_pipeline.domain import ArtifactReference, CreationProvenance, RecordEnvelope, RecordReference
from tests.operating_fixtures import KEY, LIMITS, TIME, END, policy, scope, decision, sign
from tests.test_project import setup
from tests.test_source import dictionaries, at_path
from tests.test_typed_store import ref


def binding():
    """Construct explicit syntax-only evidence; absence of storage is never mistaken for readiness."""
    value = setup()
    return a.OperatingBinding({"format": "research_pipeline.operating_binding", "version": 1,
        "project": ref("project", "project_setup", "project").to_dict(),
        "dossier": {name: a.absent() if getattr(value, name) is None else getattr(value, name).to_dict()
                    for name in ("initial_corpus", "current_corpus", "context", "brief", "intake_report")},
        "record_evidence": [{"reference": ref("project", "authority_evidence", "project").to_dict(), "envelope_digest": "a" * 64}],
        "artifact_evidence": [{"record": ref("capture", "authority_artifact_record", "source").to_dict(),
                               "selector_kind": "source_original", "selector": "original", "artifact": {"digest": "b" * 64, "size": 12}}],
        "head_expectations": [{"record_id": "project", "revision": 1, "kind": "project"}]})


def rich_scope():
    """Include every permission and resource field in a structurally valid signed test payload."""
    value = scope("main_research", data=True).to_dict()
    value["data_access"][0]["operations"] = ["read", "reuse", "external_processing"]
    value["capability_releases"] = [{"capability_id": "reader", "release": ref("release", "allowed_release", "tool_release").to_dict()}]
    value["disclosures"] = [{"source": ref("capture", "disclosed_source", "source").to_dict(), "original_ids": ["original"],
        "recipient_id": "recipient", "policy_reference": ref("policy", "disclosure_policy", "event").to_dict()}]
    return a.OperatingScope(value)


def leaves(value, path=()):
    """Yield each scalar path for consequential-field signature tampering, retaining array positions."""
    if type(value) is dict:
        for name, child in value.items():
            yield from leaves(child, (*path, name))
    elif type(value) is list:
        for index, child in enumerate(value):
            yield from leaves(child, (*path, index))
    else:
        yield path, value


class OperatingCodecTests(unittest.TestCase):
    """Exercise closed documents and explicit secrets without file-system or database access."""

    def test_roundtrip_detachment_projection_and_forgery(self):
        """Canonical values are frozen, detach input/output and reject subclasses or bypassed state."""
        values = [(scope(), a.dumps_scope, a.loads_scope), (binding(), a.dumps_binding, a.loads_binding),
                  (decision(binding(), scope()), a.dumps_decision, a.loads_decision)]
        signed = sign(values[-1][0])
        values.append((signed, a.dumps_signed_decision, a.loads_signed_decision))
        for value, dumps, loads in values:
            wire = value.to_dict()
            self.assertEqual(loads(dumps(value)), value)
            self.assertEqual(loads(json.dumps(wire, ensure_ascii=False).encode()), value)
            wire["version"] = 99
            self.assertEqual(value.to_dict()["version"], 1)
            with self.assertRaises(FrozenInstanceError):
                value._json = "{}"
            forged = object.__new__(type(value))
            object.__setattr__(forged, "_json", '{"version":true}')
            with self.assertRaises(a.AuthorityValidationError):
                dumps(forged)
            with self.assertRaises(a.AuthorityValidationError):
                forged.to_dict()
        class Derived(a.OperatingScope):
            """Unsupported extension type used to prove exact consuming boundaries."""
        with self.assertRaises(a.AuthorityValidationError):
            Derived(scope().to_dict())
        envelope = a.encode_envelope(signed)
        self.assertEqual(a.decode_envelope(envelope), signed)
        self.assertEqual(envelope.provenance, CreationProvenance("operator", TIME, {}))
        self.assertEqual(envelope.artifact_references, ())
        self.assertEqual([r.relationship for r in envelope.record_references],
                         ["project_setup", "initial_corpus", "current_corpus", "authority_evidence", "authority_artifact_record"])
        for field, altered in (("record_id", "other"), ("revision", 2), ("kind", "event"),
                ("provenance", CreationProvenance("other", TIME, {}).to_dict()),
                ("record_references", [r.to_dict() for r in reversed(envelope.record_references)]),
                ("artifact_references", [ArtifactReference("a" * 64, 1).to_dict()])):
            wire = envelope.to_dict(); wire[field] = altered
            with self.subTest(field=field), self.assertRaises(a.AuthorityValidationError):
                a.decode_envelope(RecordEnvelope.from_dict(wire))

    def test_recursive_fields_duplicates_and_coercions(self):
        """Every nested field is required and closed; duplicate JSON names and coercions fail at every depth."""
        wire = sign(decision(binding(), rich_scope())).to_dict()
        for path in dictionaries(wire):
            for key in (*at_path(wire, path), "extension"):
                changed = deepcopy(wire)
                node = at_path(changed, path)
                if key == "extension":
                    node[key] = None
                else:
                    del node[key]
                with self.subTest(path=path, key=key), self.assertRaises(a.AuthorityValidationError):
                    a.SignedOperatingDecision(changed)
            # Insert a duplicate into each object independently, including null fields.
            key = next(iter(at_path(wire, path)))
            node_text = a.canonical(at_path(wire, path))
            duplicate = '{' + json.dumps(key) + ':null,' + node_text[1:]
            encoded = a.canonical(wire).replace(node_text, duplicate, 1)
            with self.assertRaises(a.AuthorityValidationError):
                a.loads_signed_decision(encoded)
        for invalid in (True, 1.0, "1", None, 0, 2**63):
            changed = deepcopy(wire); changed["decision"]["revision"] = invalid
            with self.assertRaises(a.AuthorityValidationError):
                a.SignedOperatingDecision(changed)
        for raw in ('NaN', 'Infinity', '1e999', '\ud800', '[' * 33 + '0' + ']' * 33, b'\xff'):
            with self.assertRaises(a.AuthorityValidationError):
                a.loads_signed_decision(raw)
        cycle = []; cycle.append(cycle)
        for value in (cycle, {1: "bad"}, {"bad": object()}, {"bad": float("inf")}, {"bad": "\ud800"}):
            with self.assertRaises(a.DomainValidationError):
                a.bounded(value, a.RESULT_BYTES)

    def test_hmac_preimage_and_every_consequential_scalar(self):
        """Every scalar statement/permission/resource/evidence change rejects or invalidates its original signature."""
        original = decision(binding(), rich_scope())
        signed = sign(original)
        expected = hmac.new(KEY, b"research_pipeline.operating_decision.v1\0" + a.dumps_decision(original).encode("ascii"), hashlib.sha256).hexdigest()
        self.assertEqual(signed.to_dict()["signature"]["value"], expected)
        self.assertEqual(a.verify_signature(signed, policy=policy()), "verified")
        for prefix in (b"", b"research_pipeline.operating_decision.v2\0", b"research_pipeline.operating_stream.v1\0"):
            wire = signed.to_dict()
            wire["signature"]["value"] = hmac.new(KEY, prefix + a.dumps_decision(original).encode("ascii"), hashlib.sha256).hexdigest()
            self.assertEqual(a.verify_signature(a.SignedOperatingDecision(wire), policy=policy()), "invalid")
        for path, value in leaves(signed.to_dict()["decision"]):
            wire = signed.to_dict()
            node = at_path(wire["decision"], path[:-1])
            node[path[-1]] = value + 1 if type(value) is int else (value + "x" if type(value) is str else "altered")
            try:
                changed = a.SignedOperatingDecision(wire)
            except a.AuthorityValidationError:
                continue
            with self.subTest(path=path):
                self.assertNotEqual(a.verify_signature(changed, policy=policy()), "verified")
        preceding = a.encode_envelope(sign(decision(binding(), scope())))
        next_value = decision(binding(), scope(), revision=2, previous=preceding, operation="next")
        for path, value in leaves(next_value.to_dict()["predecessor"]):
            wire = sign(next_value).to_dict()
            at_path(wire["decision"]["predecessor"], path[:-1])[path[-1]] = value + 1 if type(value) is int else value + "x"
            try:
                changed = a.SignedOperatingDecision(wire)
            except a.AuthorityValidationError:
                continue
            self.assertNotEqual(a.verify_signature(changed, policy=policy()), "verified")
        self.assertEqual(a.verify_signature(signed, policy=None), "unavailable")
        self.assertEqual(a.verify_signature(signed, policy=a.OperatorPolicy("synthetic", [])), "unavailable")
        self.assertEqual(a.verify_signature(signed, policy=policy(key=b"wrong-key" * 4)), "invalid")
        self.assertEqual(a.policy_status(signed, policy=policy(projects=[])), "denied")
        self.assertEqual(a.policy_status(signed, policy=policy(capabilities=[])), "denied")
        self.assertEqual(a.policy_status(signed, policy=policy(capabilities=["approve_setup"])), "denied")

    def test_exact_time_resource_and_permission_failures(self):
        """Strict times and deny-by-default pools/permissions reject ambiguous or unsupported declarations."""
        for invalid in (TIME.replace(".000000", ""), "2026-02-30T12:00:00.000000Z", TIME.replace("Z", "+00:00"), TIME.replace("T", " ")):
            with self.assertRaises(a.AuthorityValidationError):
                a.timestamp(invalid)
        for changes in ({"valid_until": TIME}, {"issued_at": END}, {"valid_until": "2028-11-03T12:00:00.000000Z"},
                        {"decision_id": "alternate"}, {"outcome": "revoke"}, {"outcome": "deny"}):
            with self.assertRaises(a.AuthorityValidationError):
                decision(binding(), scope(), **changes)
        wire = rich_scope().to_dict()
        for field, value in (("operations", ["reuse"]), ("operations", ["read", "read"]), ("original_ids", []), ("original_ids", ["*"])):
            altered = deepcopy(wire); altered["data_access"][0][field] = value
            with self.assertRaises(a.AuthorityValidationError):
                a.OperatingScope(altered)
        altered = deepcopy(wire); altered["disclosures"][0]["original_ids"] = ["unpermitted"]
        with self.assertRaises(a.AuthorityValidationError):
            a.OperatingScope(altered)
        for field in ("ceiling",):
            altered = deepcopy(wire)
            for entry in altered["resources"][field]:
                entry["quantity"] = 0
            with self.assertRaises(a.AuthorityValidationError):
                a.OperatingScope(altered)
        altered = deepcopy(wire); altered["resources"]["purpose_limits"]["ordinary"][0]["quantity"] = True
        with self.assertRaises(a.AuthorityValidationError):
            a.OperatingScope(altered)

    def test_protocol_and_caller_limit_equalities(self):
        """Exercise equality and over-limit scalar/container bounds plus every independent caller field."""
        self.assertEqual(len(a.text_value("α" * 4096)), 4096)
        with self.assertRaises(a.AuthorityValidationError):
            a.text_value("α" * 4097)
        a.stream_id("a" * 128, "p" * 128)
        with self.assertRaises(a.AuthorityValidationError):
            a.stream_id("a" * 129, "p")
        for maximum in (a.PERMISSION_ENTRIES, a.ORIGINAL_IDS, a.EVIDENCE_DECLARATIONS, a.EVIDENCE_ENTRIES):
            self.assertEqual(len(a.array([None] * maximum, maximum)), maximum)
            with self.assertRaises(a.AuthorityValidationError):
                a.array([None] * (maximum + 1), maximum)
        for maximum in (a.DECISION_BYTES, a.SIGNED_BYTES, a.ENVELOPE_BYTES, a.RESULT_BYTES):
            text = "x" * (maximum - 2)
            self.assertEqual(len(a.bounded(text, maximum)), maximum)
            with self.assertRaises(a.AuthorityValidationError):
                a.bounded(text + "x", maximum)
        self.assertEqual(a.bounded([0] * (a.JSON_NODES - 1), a.RESULT_BYTES).count("0"), a.JSON_NODES - 1)
        with self.assertRaises(a.AuthorityValidationError):
            a.bounded([0] * a.JSON_NODES, a.RESULT_BYTES)
        for depth in (32, 33):
            raw = '[' * depth + '0' + ']' * depth
            if depth == 32:
                self.assertIsInstance(a.strict_json(raw), list)
            else:
                with self.assertRaises(a.AuthorityValidationError):
                    a.strict_json(raw)
        # UTF-8 incoming bytes are checked before canonical ASCII expansion.
        with self.assertRaises(a.AuthorityValidationError):
            a.strict_json('"' + "α" * 20 + '"', 30)
        caps = {"max_decisions": 1024, "max_history_revisions": 4096, "max_records": 4096,
                "max_references": 32768, "max_record_bytes": a.ENVELOPE_BYTES, "max_metadata_bytes": a.RESULT_BYTES,
                "max_artifacts": 4096, "max_file_bytes": 2**63 - 1, "max_total_bytes": 2**63 - 1, "max_result_bytes": a.RESULT_BYTES}
        for name, cap in caps.items():
            self.assertEqual(getattr(a.checked_limits(replace(LIMITS, **{name: cap})), name), cap)
            for invalid in (cap + 1, True, 1.0, -1, "1"):
                with self.subTest(name=name, invalid=invalid), self.assertRaises(a.AuthorityValidationError):
                    replace(LIMITS, **{name: invalid})
        zero = {"max_history_revisions", "max_references", "max_artifacts", "max_total_bytes"}
        for item in fields(LIMITS):
            if item.name in zero:
                self.assertEqual(getattr(replace(LIMITS, **{item.name: 0}), item.name), 0)
            else:
                with self.assertRaises(a.AuthorityValidationError):
                    replace(LIMITS, **{item.name: 0})

    def test_policy_snapshot_secrets_and_limits(self):
        """Host collections detach; keys never appear in repr, wire documents, fingerprints or errors."""
        projects, capabilities = ["project"], ["approve_setup"]
        credential = a.OperatorCredential("operator", "key1", KEY, projects, capabilities)
        projects.clear(); capabilities.clear()
        trust = a.OperatorPolicy("synthetic", [credential])
        self.assertEqual(credential.projects, ("project",))
        self.assertNotIn(KEY.decode(), repr(trust))
        self.assertNotIn(KEY.decode(), a.dumps_signed_decision(sign(decision(binding(), scope()))))
        self.assertEqual(a.policy_fingerprint(trust), a.policy_fingerprint(policy(capabilities=["approve_setup"], key=b"Q" * 32)))
        for invalid in (bytearray(KEY), b"x" * 31, b"x" * 65, "credential-secret-text"):
            with self.assertRaises(a.AuthorityValidationError) as caught:
                a.OperatorCredential("operator", "key", invalid, [], [])
            self.assertNotIn(str(invalid), str(caught.exception))
        for length in (32, 64):
            a.OperatorCredential("operator", "key", b"x" * length, [], [])
        with self.assertRaises(a.AuthorityValidationError):
            a.OperatorPolicy("synthetic", [credential, credential])
        many = [a.OperatorCredential("operator", "key" + str(i), KEY, [], []) for i in range(129)]
        self.assertEqual(len(a.OperatorPolicy("synthetic", many[:128]).credentials), 128)
        with self.assertRaises(a.AuthorityValidationError):
            a.OperatorPolicy("synthetic", many)
        self.assertEqual(len(a.OperatorCredential("operator", "key", KEY, ["p" + str(i) for i in range(256)], []).projects), 256)
        with self.assertRaises(a.AuthorityValidationError):
            a.OperatorCredential("operator", "key", KEY, ["p" + str(i) for i in range(257)], [])

    def test_detached_results_and_public_collection_boundaries(self):
        """Validate all detached result codecs and actual public collection equality/overflow boundaries."""
        from research_pipeline.domain import SubmissionReceipt
        signed = sign(decision(binding(), scope()))
        envelope = a.encode_envelope(signed)
        submitted = a.submission(signed)
        fingerprint = hashlib.sha256(a.canonical({"fingerprint_version": 1, "submission": submitted.to_dict()}).encode()).hexdigest()
        receipt = SubmissionReceipt("approve", fingerprint, 1, TIME, envelope.provenance, ((envelope.record_id, 1),))
        watermark = {"event_id": 1, "submission_id": "approve", "committed_at": TIME, "fingerprint": fingerprint}
        reference = ref(envelope.record_id, "operating_decision", "decision").to_dict()
        committed = a.DecisionCommitResult({"format": "research_pipeline.operating_commit_result", "version": 1,
            "operation_id": "approve", "decision": reference, "envelope_digest": a.envelope_digest(envelope), "receipt": receipt.to_dict()})
        history = a.AuthorityHistory({"format": "research_pipeline.authority_history", "version": 1,
            "authority_domain": "synthetic", "project_id": "project", "decisions": [{"envelope": envelope.to_dict(),
                "receipt": receipt.to_dict(), "signature_status": "verified", "policy_status": "permitted"}], "watermark": watermark})
        eligibility = a.EligibilityResult({"format": "research_pipeline.operating_eligibility", "version": 1,
            "authority_domain": "synthetic", "project_id": "project", "purpose": "setup", "evaluated_at": TIME,
            "status": "missing_trust", "eligible": False, "decision": reference, "signature_status": "unavailable",
            "policy_status": "unavailable", "binding": binding().to_dict(), "observed_heads": [], "verified_artifacts": [],
            "history_signatures": [{"reference": reference, "envelope_digest": a.envelope_digest(envelope), "signature_status": "unavailable"}],
            "watermark": watermark, "policy_fingerprint": None, "recheck_required": True})
        for value, dumps, loads in ((committed, a.dumps_commit_result, a.loads_commit_result),
                (history, a.dumps_history, a.loads_history), (eligibility, a.dumps_eligibility, a.loads_eligibility)):
            self.assertEqual(loads(dumps(value)), value)
            for name in value.to_dict():
                altered = value.to_dict(); del altered[name]
                with self.assertRaises(a.AuthorityValidationError):
                    type(value)(altered)
            forged = object.__new__(type(value)); object.__setattr__(forged, "_json", "{}")
            with self.assertRaises(a.AuthorityValidationError):
                dumps(forged)
        for change in ({"eligible": True}, {"recheck_required": False}, {"status": "eligible_main_research"}):
            with self.assertRaises(a.AuthorityValidationError):
                a.EligibilityResult({**eligibility.to_dict(), **change})
        wire = scope().to_dict()
        wire["capability_releases"] = [{"capability_id": "c" + str(i), "release": ref("r" + str(i), "allowed_release", "tool_release").to_dict()} for i in range(128)]
        self.assertEqual(len(a.OperatingScope(wire).to_dict()["capability_releases"]), 128)
        wire["capability_releases"].append({"capability_id": "overflow", "release": ref("overflow", "allowed_release", "tool_release").to_dict()})
        with self.assertRaises(a.AuthorityValidationError):
            a.OperatingScope(wire)
        wire = scope(data=True).to_dict()
        wire["data_access"][0]["original_ids"] = ["o" + str(i) for i in range(1024)]
        a.OperatingScope(wire)
        wire["data_access"][0]["original_ids"].append("overflow")
        with self.assertRaises(a.AuthorityValidationError):
            a.OperatingScope(wire)
        for field in ("record_evidence", "artifact_evidence", "head_expectations"):
            wire = binding().to_dict()
            template = wire[field][0]
            wire[field] = []
            for index in range(4096):
                item = deepcopy(template)
                if field == "record_evidence":
                    item["reference"]["record_id"] = "r" + str(index)
                elif field == "artifact_evidence":
                    item["selector"] = "o" + str(index)
                else:
                    item["record_id"] = "r" + str(index)
                wire[field].append(item)
            self.assertEqual(len(a.OperatingBinding(wire).to_dict()[field]), 4096)
            wire[field].append(deepcopy(template))
            with self.assertRaises(a.AuthorityValidationError):
                a.OperatingBinding(wire)

    def test_permission_dimension_and_evidence_collection_extremes(self):
        """Actual permission arrays, resource dimensions/services and judgment selections accept their exact maxima."""
        for name in ("data_access", "disclosures"):
            wire = rich_scope().to_dict()
            template = wire[name][0]
            wire[name] = []
            for index in range(128):
                item = deepcopy(template)
                if name == "data_access":
                    item["source"]["record_id"] = "capture" if index == 0 else "capture" + str(index)
                else:
                    item["recipient_id"] = "recipient" + str(index)
                wire[name].append(item)
            self.assertEqual(len(a.OperatingScope(wire).to_dict()[name]), 128)
            wire[name].append(deepcopy(template))
            with self.assertRaises(a.AuthorityValidationError):
                a.OperatingScope(wire)
        wire = scope().to_dict()
        resources = wire["resources"]
        for currency in ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY", "INR"):
            identity = "money_" + currency
            resources["dimensions"].append({"dimension_id": identity, "kind": "monetary", "unit": "currency_quantum", "currency": currency, "scale": 100})
            for vector in (resources["ceiling"], *resources["purpose_limits"].values(),
                           *(resources["run_policy"][p + "_minimum"] for p in ("verification", "handoff", "closeout"))):
                vector.append({"dimension_id": identity, "quantity": 0})
            resources["run_policy"]["monetary_services"].append({"dimension_id": identity, "service_id": "service_" + currency,
                "mode": "monitored_target", "statement": "No provider hard cap is claimed"})
        self.assertEqual(len(a.OperatingScope(wire).to_dict()["resources"]["dimensions"]), 16)
        for field, value in (("dimensions", resources["dimensions"] + [resources["dimensions"][0]]),
                             ("ceiling", resources["ceiling"] + [resources["ceiling"][0]])):
            altered = deepcopy(wire); altered["resources"][field] = value
            with self.assertRaises(a.AuthorityValidationError):
                a.OperatingScope(altered)
        altered = deepcopy(wire); altered["resources"]["run_policy"]["monetary_services"].append(resources["run_policy"]["monetary_services"][0])
        with self.assertRaises(a.AuthorityValidationError):
            a.OperatingScope(altered)
        statement = decision(binding(), scope()).to_dict()
        statement["judgments"]["evidence_declarations"] = ["e" + str(i) for i in range(1024)]
        a.OperatingDecision(statement)
        statement["judgments"]["evidence_declarations"].append("overflow")
        with self.assertRaises(a.AuthorityValidationError):
            a.OperatingDecision(statement)
