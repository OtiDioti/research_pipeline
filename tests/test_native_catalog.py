"""Retained consequential native evidence tests, adapted from the pre-L1 suite."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from tests import use_checkout
use_checkout()
from research_pipeline import codex, isolation

class NativeCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        context = self.root/'session/jobs/context.json'
        context.parent.mkdir(parents=True)
        self.config = SimpleNamespace(job_context=context)

    def test_final_006_surface_reports_all_unsupported_routes_and_missing_adapter(self):
        # Names/namespace layout from the session-bound native request in the
        # preserved m4-live-qm3yf9ki receipt. No adapter declarations were present.
        nested = ("apply_patch", "create_goal", "get_goal", "list_mcp_resource_templates",
                  "list_mcp_resources", "read_mcp_resource", "update_goal", "view_image",
                  "clock__curr_time", "image_gen__imagegen", "web__run")
        description = "Run JavaScript code to orchestrate/compose tool calls\n" + "".join(
            f"\n### `{name}`\nNative operation.\n\nexec tool declaration:\n"
            f"```ts\ndeclare const tools: {{ {name}(args: {{}}): Promise<unknown>; }};\n```\n"
            for name in nested)
        declarations = [
            {"type": "namespace", "name": "functions", "tools": [
                {"type": "custom", "name": "exec", "description": description},
                *({"type": "function", "name": name} for name in
                  ("wait", "request_user_input", "request_user_input_async"))]},
            {"type": "namespace", "name": "clock", "tools": [
                {"type": "function", "name": "sleep"}]},
            {"type": "namespace", "name": "collaboration", "tools": [
                {"type": "function", "name": name} for name in
                ("followup_task", "interrupt_agent", "list_agents",
                 "send_message", "spawn_agent", "wait_agent")]}]
        catalog = codex.request_tool_catalog(declarations)
        self.assertEqual([c["name"] for c in catalog], [
            "functions.exec", *nested, "functions.wait", "functions.request_user_input",
            "functions.request_user_input_async", "clock.sleep", "collaboration.followup_task",
            "collaboration.interrupt_agent", "collaboration.list_agents",
            "collaboration.send_message", "collaboration.spawn_agent", "collaboration.wait_agent"])
        with self.assertRaises(isolation.RuntimeUnavailable) as caught:
            codex.validate_tool_catalog(catalog)
        diagnostic = str(caught.exception)
        for unsupported in ("image_gen__imagegen", "collaboration.followup_task",
                            "collaboration.interrupt_agent", "collaboration.send_message",
                            "collaboration.spawn_agent"):
            self.assertIn("Unsupported native tool surface: " + unsupported, diagnostic)
        self.assertIn("Controlled adapter unavailable", diagnostic)
        for name in ("job_run", "job_status", "job_wait", "job_cancel", "write_draft", "control"):
            self.assertIn(name, diagnostic)
        for harmless in ("create_goal", "get_goal", "update_goal", "web__run",
                         "collaboration.list_agents", "collaboration.wait_agent"):
            self.assertNotIn("Unsupported native tool surface: " + harmless, diagnostic)


    def test_native_request_evidence_retained_and_bound_to_fresh_session(self):
        home, session = self.root / "private-home", self.config.job_context.parent.parent
        bundle = home / "native-trace/trace-fixture"
        (bundle / "payloads").mkdir(parents=True)
        names = ["mcp__research_jobs__" + name for name in
                 ("job_run", "job_wait", "job_status", "job_cancel", "write_draft", "control")]
        declarations = [{"type": "function", "name": name, "description": "Controlled adapter"}
                        for name in names]
        manifest = {"schema_version": 2, "root_thread_id": "fresh", "rollout_id": "fresh"}
        event = {"schema_version": 2, "thread_id": "fresh", "rollout_id": "fresh",
                 "payload": {"type": "inference_started", "thread_id": "fresh",
                             "request_payload": {"kind": {"type": "inference_request"},
                                                 "path": "payloads/1.json"}}}
        request = {"model": "fixture", "tools": declarations[:3], "input": [
            {"type": "message", "role": "user", "content": "Not tool evidence"},
            {"type": "additional_tools", "role": "developer", "tools": declarations[3:]}]}
        (bundle / "manifest.json").write_text(json.dumps(manifest))
        (bundle / "trace.jsonl").write_text(json.dumps(event) + "\n")
        (bundle / "payloads/1.json").write_text(json.dumps(request))
        with codex.native_tool_trace(home, session):
            pass
        catalogs = codex.native_catalog_observations(session, "fresh")
        self.assertEqual([codex.validate_tool_catalog(c) for c in catalogs], [names])
        receipt = json.loads((session / "native-tools.json").read_text())
        self.assertEqual(receipt["inference_starts"], 1)
        self.assertNotIn("Not tool evidence", json.dumps(receipt))
        self.assertEqual(len(receipt["observations"][0]["request_sha256"]), 64)
        with self.assertRaisesRegex(isolation.RuntimeUnavailable, "different session"):
            codex.native_catalog_observations(session, "previous")
        # Native message prose and user-supplied declarations cannot substitute.
        request["input"][1]["role"] = "user"
        (bundle / "payloads/1.json").write_text(json.dumps(request))
        with codex.native_tool_trace(home, session):
            pass
        with self.assertRaisesRegex(isolation.RuntimeUnavailable, "additional_tools role"):
            codex.native_catalog_observations(session, "fresh")
        # A change only in top-level tools must not be deduplicated away.
        request["input"][1]["role"] = "developer"
        (bundle / "payloads/1.json").write_text(json.dumps(request))
        request["tools"].append({"type": "function", "name": "exec_command"})
        (bundle / "payloads/2.json").write_text(json.dumps(request))
        event["payload"]["request_payload"]["path"] = "payloads/2.json"
        with (bundle / "trace.jsonl").open("a") as stream:
            stream.write(json.dumps(event) + "\n")
        with codex.native_tool_trace(home, session):
            pass
        catalogs = codex.native_catalog_observations(session, "fresh")
        self.assertEqual(len(catalogs), 2)
        with self.assertRaisesRegex(isolation.RuntimeUnavailable, "exec_command"):
            codex.validate_tool_catalog(catalogs[1])
        # Equal tool declarations still represent distinct inference boundaries.
        (bundle / "payloads/3.json").write_text(json.dumps(request))
        event["payload"]["request_payload"]["path"] = "payloads/3.json"
        with (bundle / "trace.jsonl").open("a") as stream:
            stream.write((json.dumps(event) + "\n") * 2)  # duplicate native event
        with codex.native_tool_trace(home, session):
            pass
        self.assertEqual(len(codex.native_catalog_observations(session, "fresh")), 2)
        receipt = json.loads((session / "native-tools.json").read_text())
        self.assertEqual(receipt["inference_starts"], 3)
        # Earlier receipts omitted top-level tools; they cannot certify completeness.
        receipt = json.loads((session / "native-tools.json").read_text())
        del receipt["observations"][0]["tools"]
        (session / "native-tools.json").write_text(json.dumps(receipt))
        with self.assertRaisesRegex(isolation.RuntimeUnavailable, "capture is incomplete"):
            codex.native_catalog_observations(session, "fresh")
        (bundle / "payloads/1.json").write_text("{incomplete")
        with codex.native_tool_trace(home, session):
            pass
        with self.assertRaisesRegex(isolation.RuntimeUnavailable, "incomplete"):
            codex.native_catalog_observations(session, "fresh")


    def test_native_code_mode_declarations_include_nested_command_routes(self):
        names = ["mcp__research_jobs__" + name for name in
                 ("job_run", "job_wait", "job_status", "job_cancel", "write_draft", "control")]
        def declarations(names):
            detail = "Run JavaScript code with no filesystem or network.\n" + "".join(
                f"\n### `{name}`\nControlled operation.\n\nexec tool declaration:\n"
                f"```ts\ndeclare const tools: {{ {name}(args: {{}}): Promise<unknown>; }};\n```\n"
                for name in names)
            return [{"type": "namespace", "name": "functions", "tools": [
                {"type": "custom", "name": "exec", "description": detail}]}]
        self.assertEqual(codex.validate_tool_catalog(codex.request_tool_catalog(declarations(names))),
                         ["functions.exec", *names])
        direct = [{"type": "namespace", "name": "mcp__research_jobs", "tools": [
            {"type": "function", "name": name.rsplit("__", 1)[-1]} for name in names]},
            {"type": "web_search"}]
        self.assertEqual(len(codex.validate_tool_catalog(codex.request_tool_catalog(direct))), 7)
        with self.assertRaisesRegex(isolation.RuntimeUnavailable, "Unsupported native"):
            codex.validate_tool_catalog(codex.request_tool_catalog(declarations([*names, "exec_command"])))
        with self.assertRaisesRegex(isolation.RuntimeUnavailable, "declarations unavailable"):
            codex.request_tool_catalog([{"type": "namespace", "name": "functions", "tools": [
                {"type": "custom", "name": "exec", "description": "JavaScript, missing nested metadata"}]}])


    def test_native_trace_stays_outside_scientific_job_and_retains_unknown_on_interruption(self):
        home, session = self.root / "private-home", self.config.job_context.parent.parent
        command = isolation.bubblewrap_command(self.root, ["/bin/true"], auth_home=home)
        self.assertIn("CODEX_ROLLOUT_TRACE_ROOT", command)
        scientific = isolation.bubblewrap_command(self.root, ["/bin/true"])
        self.assertNotIn("CODEX_ROLLOUT_TRACE_ROOT", scientific)
        self.assertNotIn(str(home), scientific)
        with self.assertRaises(KeyboardInterrupt):
            with codex.native_tool_trace(home, session):
                raise KeyboardInterrupt
        self.assertEqual(codex.native_catalog_observations(session, "fresh"), [])

