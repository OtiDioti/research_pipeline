"""The human's actions on single agents and live settings (from the web app), and the web app's view of them."""

import unittest

from agent_toolkit.web import SettingsError

from research_pipeline.state import Options
from research_pipeline.web import ResearchDashboard
from tests.helpers import FAKE_DRIVERS, FakeSession, launch_options, remove, running, temp_project


def sent(harness, agent_id: str) -> str:
    """Everything the agent's current session was sent, as one text."""
    return "\n".join(harness.session(agent_id).sent)


async def spawn(harness, parent: str = "primary", name: str = "helper") -> str:
    """``parent`` starts a subagent; return its id."""
    harness.write(f"phases/1/agents/{parent}/brief-{name}.md", f"# Check {name}\n\nDo it.\n")
    reply = await harness.call(
        parent, "spawn", task=f"brief-{name}.md", name=name, backend="codex", model="gpt-test", effort="high"
    )
    assert "Started subagent" in reply, reply
    return reply.split()[2]


class HumanActionsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = temp_project()
        FakeSession.reset()

    def tearDown(self):
        remove(self.root)

    async def test_a_message_to_a_subagent_reaches_it_and_its_parent_gets_a_copy(self):
        async with running(self.root) as harness:
            child = await spawn(harness)
            await harness.controller.act("message", child, "Use SI units.")
            await harness.settle()
            self.assertIn("[human] Use SI units.", sent(harness, child))
            self.assertIn(f"The human wrote to your subagent {child}: Use SI units.", sent(harness, "primary"))
            senders = [(entry["kind"], entry["sender"]) for entry in harness.controller.activity.read(child)]
            self.assertIn(("message", "human"), senders)
            self.assertIn(("message", "controller"), senders)  # its opening message

    async def test_pausing_one_agent_holds_only_it_until_the_human_resumes_it(self):
        async with running(self.root) as harness:
            child = await spawn(harness)
            session = harness.session(child)
            await harness.controller.act("pause", child)
            self.assertIn("The human paused you", sent(harness, child))
            await harness.emit(child, "turn_ended", text="Stopped at a clean point.")
            agent = harness.state.agents[child]
            self.assertIs(harness.session(child), session)  # it waits in its session
            self.assertEqual((agent.status, agent.pause_reason), ("paused", "held"))
            self.assertEqual(harness.state.agents["primary"].status, "running")  # the rest keeps working
            self.assertIn(f"paused your subagent {child}", sent(harness, "primary"))
            # Pausing and resuming the whole investigation does not restart an agent held on its own.
            harness.controller.toggle_pause()
            await harness.settle()
            await harness.emit("primary", "turn_ended", text="Stopped.")
            self.assertEqual(harness.state.status, "paused")
            harness.controller.toggle_pause()
            await harness.settle(10)
            self.assertEqual(harness.state.agents["primary"].status, "running")
            self.assertEqual(harness.state.agents[child].pause_reason, "held")
            await harness.controller.act("resume", child)
            self.assertEqual((agent.status, agent.sessions), ("running", 1))  # in the same session
            self.assertIn("The human resumed you. Continue your work.", sent(harness, child))
            self.assertIn(f"resumed your subagent {child}", sent(harness, "primary"))

    async def test_a_forced_handoff_continues_in_a_fresh_session_even_below_the_threshold(self):
        async with running(self.root) as harness:
            await harness.controller.act("handoff", "primary")
            primary = harness.state.agents["primary"]
            self.assertEqual(primary.status, "handing_off")
            self.assertIn("fresh session", sent(harness, "primary"))
            await harness.emit(
                "primary", "context", tokens=10_000, window=100_000
            )  # not called off, unlike a context one
            self.assertEqual(primary.status, "handing_off")
            harness.handoff("primary")
            await harness.emit("primary", "turn_ended", text="Saved.")
            self.assertEqual((primary.status, primary.sessions), ("running", 2))

    async def test_cancelling_a_subagent_stops_its_subtree_and_tells_its_parent(self):
        async with running(self.root) as harness:
            child = await spawn(harness)
            grandchild = await spawn(harness, parent=child, name="deeper")
            await harness.controller.act("cancel", child)
            self.assertEqual({harness.state.agents[name].status for name in (child, grandchild)}, {"cancelled"})
            self.assertIn(f"cancelled your subagent {child}", sent(harness, "primary"))
            with self.assertRaises(ValueError):
                await harness.controller.act("cancel", "primary")  # only subagents can be cancelled
            with self.assertRaises(ValueError):
                await harness.controller.act("message", child, "Too late.")  # it has ended

    async def test_live_settings_apply_at_once_and_invalid_ones_change_nothing(self):
        async with running(self.root) as harness:
            await harness.controller.configure({"threshold": 0.7, "short_limit": 5, "max_agents": 2, "idle_limit": 0})
            options = harness.state.options
            self.assertEqual(
                (options.threshold, options.short_limit, options.max_agents, options.idle_limit), (0.7, 5.0, 2, 0)
            )
            self.assertEqual(harness.controller.watches["primary"].threshold, 0.7)
            self.assertEqual(harness.controller.guard.short_limit, 5.0)
            with self.assertRaises(ValueError):
                await harness.controller.configure({"threshold": 0.95, "max_agents": 3})
            with self.assertRaises(ValueError):
                await harness.controller.configure({"idle_limit": -5})
            self.assertEqual((options.threshold, options.max_agents), (0.7, 2))

    async def test_a_new_cli_choice_applies_from_the_agents_next_session(self):
        async with running(self.root) as harness:
            await harness.controller.configure({"primary": "claude:sonnet:high", "backends": ["claude"]})
            self.assertEqual(harness.session("primary").launch.model, launch_options().primary.split(":")[1])
            self.assertEqual(
                (harness.state.options.primary, harness.state.options.backends), ("claude:sonnet:high", ["claude"])
            )
            await harness.controller.act("handoff", "primary")
            harness.handoff("primary")
            await harness.emit("primary", "turn_ended", text="Saved.")
            self.assertEqual(
                (
                    harness.session("primary").backend,
                    harness.session("primary").launch.model,
                    harness.session("primary").launch.effort,
                ),
                ("claude", "sonnet", "high"),
            )
            with self.assertRaises(ValueError):
                await harness.controller.configure({"reviewer": "claude:sonnet:huge"})  # an effort claude refuses


class SettlingTest(unittest.IsolatedAsyncioTestCase):
    """A message that reached the CLI too late for a turn runs in a further one: the controller waits for it."""

    def setUp(self):
        self.root = temp_project()
        FakeSession.reset()

    def tearDown(self):
        remove(self.root)

    async def test_a_handoff_request_that_arrived_too_late_is_waited_for_not_asked_again(self):
        async with running(self.root) as harness:
            await harness.emit("primary", "context", tokens=60_000, window=100_000)
            self.assertEqual(harness.state.agents["primary"].status, "handing_off")
            asked = len(harness.session("primary").sent)
            # The turn ends with the request still unread by the CLI: a further turn runs it.
            await harness.emit("primary", "turn_ended", text="Answered.", pending=1)
            self.assertEqual(len(harness.session("primary").sent), asked)  # not asked again, nothing closed
            harness.handoff("primary")
            await harness.emit("primary", "turn_ended", text="Saved.")
            primary = harness.state.agents["primary"]
            self.assertEqual((primary.status, primary.sessions), ("running", 2))


class RecommendationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = temp_project()
        FakeSession.reset()

    def tearDown(self):
        remove(self.root)

    async def test_the_recommended_models_reach_the_prompt_and_change_from_each_agents_next_session(self):
        async with running(self.root) as harness:
            first = harness.session("primary").launch.instructions
            self.assertIn(
                "coding (writing, debugging and running code, simulations, tools) on claude-opus-5-5 "
                "(backend claude, effort xhigh)",
                first,
            )
            self.assertIn(
                "analysis (derivations, literature, data interpretation, critique) on gpt-6.1-sol "
                "(backend codex, effort xhigh)",
                first,
            )
            self.assertIn("use the best model you can on an available backend", first)
            with self.assertRaises(ValueError):
                await harness.controller.configure({"coding": "claude:sonnet:huge"})  # an effort claude refuses
            await harness.controller.configure({"coding": "codex:gpt-test:high"})
            self.assertEqual(harness.state.options.coding, "codex:gpt-test:high")
            self.assertEqual(harness.session("primary").launch.instructions, first)  # its session keeps them
            await harness.controller.act("handoff", "primary")
            harness.handoff("primary")
            await harness.emit("primary", "turn_ended", text="Saved.")
            self.assertIn("on gpt-test (backend codex, effort high)", harness.session("primary").launch.instructions)


class DashboardTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = temp_project()
        FakeSession.reset()

    def tearDown(self):
        remove(self.root)

    async def test_the_setup_page_refuses_invalid_settings_and_starts_with_valid_ones(self):
        dashboard = ResearchDashboard(self.root, launch_options(), drivers=FAKE_DRIVERS, read_quota=lambda backend: [])
        values = dashboard.values()
        self.assertEqual(values["primary"], launch_options().primary)  # prefilled from the given options
        with self.assertRaises(SettingsError) as refusal:
            await dashboard.start(values | {"primary": "codex:gpt-test", "threshold": 0.95, "backends": []})
        self.assertEqual(set(refusal.exception.errors), {"primary", "threshold", "backends"})
        await dashboard.start(values | {"max_agents": 3})
        assert dashboard.controller is not None and dashboard.controller.launch_options is not None
        self.assertEqual(dashboard.controller.launch_options.max_agents, 3)
        self.assertEqual(
            {field["name"] for field in dashboard.live()["fields"]},
            {
                "primary",
                "reviewer",
                "librarian",
                "backends",
                "coding",
                "analysis",
                "max_agents",
                "threshold",
                "idle_limit",
                "short_limit",
                "weekly_limit",
            },
        )

    async def test_the_recommended_models_are_set_on_the_page_and_warn_outside_the_subagents_clis(self):
        dashboard = ResearchDashboard(self.root, launch_options(), drivers=FAKE_DRIVERS, read_quota=lambda backend: [])
        values = dashboard.values()
        self.assertEqual((values["coding"], values["analysis"]), (Options().coding, Options().analysis))
        fields = {field.name: field for field in dashboard.fields()}
        self.assertEqual((fields["coding"].within, fields["analysis"].within), ("backends", "backends"))
        with self.assertRaises(SettingsError) as refusal:
            await dashboard.start(values | {"coding": "codex:gpt-test"})
        self.assertEqual(set(refusal.exception.errors), {"coding"})
        # Outside the CLIs for subagents it is only a recommendation: Start accepts it (the page warns).
        await dashboard.start(values | {"coding": "claude:sonnet:high", "backends": ["codex"]})
        assert dashboard.controller is not None and dashboard.controller.launch_options is not None
        self.assertEqual(dashboard.controller.launch_options.coding, "claude:sonnet:high")

    async def test_the_graph_shows_agents_their_documents_websites_jobs_and_actions(self):
        async with running(self.root) as harness:
            dashboard = ResearchDashboard(self.root, launch_options(), drivers=FAKE_DRIVERS)
            dashboard.controller = harness.controller
            harness.controller.activity.listeners.append(lambda entry: dashboard._entry(1, entry))
            pushed = []
            dashboard.publish = pushed.append
            child = await spawn(harness)
            await harness.emit(child, "tool", text="web fetch https://arxiv.org/abs/1234.5678", server=None)
            await harness.call(child, "run_job", command="true", timeout_seconds=30)
            graph = dashboard.snapshot()["graph"]
            nodes = {item["id"]: item for item in graph["nodes"]}
            self.assertEqual(
                {item["id"] for item in graph["nodes"] if item["kind"] == "agent"},
                {"primary", "reviewer", "librarian", child},
            )
            agent = nodes[child]
            self.assertEqual((agent["parent"], agent["role"], agent["backend"]), ("primary", "subagent", "codex"))
            self.assertEqual(set(agent["actions"]), {"message", "pause", "handoff", "cancel"})
            names = [path.rsplit("/", 1)[1] for path in agent["documents"]]
            self.assertEqual(names[0], "TASK.md")
            self.assertNotIn("FOLDER_CONTENT.md", names)
            self.assertEqual(nodes["site:https://arxiv.org/abs/1234.5678"]["owners"], [child])
            self.assertTrue(any(item["kind"] == "job" and item["owners"] == [child] for item in graph["nodes"]))
            kinds = {(item["source"], item["target"], item["kind"]) for item in graph["edges"]}
            self.assertIn(("primary", child, "child"), kinds)
            self.assertIn((child, "site:https://arxiv.org/abs/1234.5678", "owns"), kinds)
            self.assertTrue(any(entry["agent"] == child and entry["kind"] == "tool" for entry in pushed))
            status = dashboard.snapshot()["status"]
            self.assertEqual([control["action"] for control in status["controls"]], ["pause", "shutdown"])
            self.assertRegex(status["summary"], r"^\d+/\d+ sessions$")
            self.assertIn("Delivered", await dashboard.act("message", child, {"text": "Hello."}) or "")
            await dashboard.act("pause", None, {})
            await harness.settle()
            self.assertEqual(harness.state.status, "pausing")

    def test_only_noteworthy_controller_entries_become_notifications(self):
        dashboard = ResearchDashboard(self.root, launch_options())

        def level(kind: str, source: str, text: str) -> str | None:
            return (dashboard.notice(kind, source, text) or {}).get("level")

        self.assertEqual(level("alert", "primary", "Waiting for you."), "alert")
        self.assertEqual(level("controller", "primary", "Usage quota: codex held (short)."), "info")
        self.assertEqual(level("controller", "primary", "Phase 1 is COMPLETE: x"), "alert")
        self.assertIsNone(dashboard.notice("controller", "helper", "Session 2 started (codex:x:high)."))
        self.assertIsNone(dashboard.notice("agent", "helper", "Thinking."))


if __name__ == "__main__":
    unittest.main()
