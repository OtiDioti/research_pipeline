"""Command line options and status, and the terminal app's rendering (without a real terminal)."""

import argparse
import asyncio
import contextlib
import fcntl
import io
import unittest
from unittest import mock

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from research_pipeline import cli
from research_pipeline.controller import Controller
from research_pipeline.state import Agent, Options, State
from research_pipeline.view import TerminalApp, describe
from tests.helpers import FAKE_DRIVERS, launch_options, remove, temp_project


def arguments(**values):
    defaults = dict(
        primary=None,
        reviewer=None,
        librarian=None,
        setup=None,
        backends=None,
        max_agents=None,
        reference=None,
        short_limit=None,
        weekly_limit=None,
        context_threshold=None,
        idle_limit=None,
        durable=None,
    )
    return argparse.Namespace(**(defaults | values))


class CliTest(unittest.TestCase):
    def test_options_merge_with_stored_ones(self):
        fresh = cli.options_from(arguments(primary="claude:opus:high", reviewer="codex:gpt-test:high"), None)
        self.assertEqual(fresh.backends, ["claude", "codex"])
        stored = Options(primary="codex:gpt-test:high", backends=["codex"], max_agents=6)
        merged = cli.options_from(arguments(max_agents=3, context_threshold=0.5), stored)
        self.assertEqual(
            (merged.primary, merged.backends, merged.max_agents, merged.threshold),
            ("codex:gpt-test:high", ["codex"], 3, 0.5),
        )
        for threshold in (2, 0.9):  # at most 0.8: room is needed to write the handoff note
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                cli.options_from(arguments(context_threshold=threshold), None)
        self.assertEqual((fresh.idle_limit, cli.options_from(arguments(idle_limit=0), stored).idle_limit), (58, 0))
        with self.assertRaises(ValueError):
            cli.options_from(arguments(idle_limit=-1), None)
        self.assertTrue(merged.durable)
        self.assertFalse(cli.options_from(arguments(durable=False), stored).durable)
        with self.assertRaisesRegex(ValueError, "does not accept effort"):
            cli.options_from(arguments(primary="claude:opus:enormous"), None)
        with self.assertRaises(ValueError) as raised:
            cli.options_from(arguments(primary="claude:opus"), None)  # model and effort are always explicit
        self.assertIn("--primary", str(raised.exception))

    def test_the_web_page_is_the_default_and_the_terminal_app_an_option(self):
        root, seen = temp_project(), []

        async def web(project, options, args):
            seen.append(("web", args.tui))
            return 0

        async def terminal(controller, tui):
            seen.append(("no web", tui))
            return 0

        cases = (
            ([], ("web", False)),
            (["--tui"], ("web", True)),
            (["--no-web"], ("no web", False)),
            (["--no-web", "--tui"], ("no web", True)),
        )
        try:
            with (
                mock.patch.object(cli, "with_web", web),
                mock.patch.object(cli, "run", terminal),
                mock.patch.object(cli, "Controller", lambda root, options: None),
            ):
                for argv, expected in cases:
                    with self.subTest(argv=argv):
                        self.assertEqual(cli.main(["run", str(root), *argv]), 0)
                        self.assertEqual(seen.pop(), expected)
                for old in ("--web", "--no-tui"):  # the defaults' former opt-ins are gone
                    with (
                        self.subTest(old=old),
                        contextlib.redirect_stderr(io.StringIO()),
                        self.assertRaises(SystemExit),
                    ):
                        cli.main(["run", str(root), old])
                self.assertEqual(seen, [])
        finally:
            remove(root)

    def test_status_command(self):
        root = temp_project()
        try:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(cli.main(["status", str(root)]), 1)
            state = State(status="paused")
            state.agents["primary"] = Agent(
                "primary", "primary", None, "codex", "gpt-test", "high", status="paused", pause_reason="human"
            )
            state.save(root / ".research" / "state.json")
            with contextlib.redirect_stdout(output):
                self.assertEqual(cli.main(["status", str(root)]), 0)
            self.assertIn("Investigation: paused", output.getvalue())
            self.assertIn("paused (human)", output.getvalue())
        finally:
            remove(root)

    def test_status_tells_whether_a_controller_is_running(self):
        root = temp_project()
        try:
            state = State(status="running")
            state.agents["primary"] = Agent("primary", "primary", None, "codex", "gpt-test", "high", status="running")
            state.save(root / ".research" / "state.json")
            stopped = io.StringIO()
            with contextlib.redirect_stdout(stopped):
                cli.main(["status", str(root)])
            self.assertIn("Controller: not running", stopped.getvalue())
            self.assertIn("[no live session: controller not running]", stopped.getvalue())
            with open(root / ".research" / "lock", "w") as lock:  # held like a running controller holds it
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                live = io.StringIO()
                with contextlib.redirect_stdout(live):
                    cli.main(["status", str(root)])
            self.assertIn("Controller: running", live.getvalue())
            self.assertNotIn("no live session", live.getvalue())
        finally:
            remove(root)

    def test_run_rejects_a_project_without_objectives(self):
        root = temp_project()
        (root / "starting_evidence" / "OBJECTIVES.md").unlink()
        try:
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                self.assertEqual(cli.main(["run", str(root), "--no-web"]), 2)
            self.assertIn("OBJECTIVES.md is missing", errors.getvalue())
        finally:
            remove(root)


class ViewTest(unittest.TestCase):
    def test_render_status_and_agent_selection(self):
        controller = Controller(temp_project(), launch_options(), drivers=FAKE_DRIVERS)
        try:
            controller.state = State(options=launch_options())
            controller.state.agents["primary"] = Agent(
                "primary",
                "primary",
                None,
                "codex",
                "gpt-test",
                "high",
                status="paused",
                pause_reason="quota",
                activity="Deriving.",
            )
            controller.state.agents["helper"] = Agent(
                "helper", "subagent", "primary", "claude", "haiku", "low", status="submitted"
            )
            app_alert = ("alert", "primary", "The primary has stopped and is waiting for you.")
            with create_pipe_input() as pipe:
                app = TerminalApp(controller, input=pipe, output=DummyOutput())
                app.add("agent", "primary", "The integral is 1/3.")
                app.add("controller", "helper", "Session 1 started.")
                app.add(*app_alert)
                app.render()
                self.assertIn("The integral is 1/3.", app.log.text)
                self.assertIn("primary ALERT", app.log.text)
                self.assertIn("paused (quota)", app.agents.text)
                self.assertIn("RUNNING", app.status())
                app.cycle()  # first agent alone: helper
                app.render()
                self.assertNotIn("The integral", app.log.text)
                app.select(None)
                app.render()
                self.assertIn("The integral", app.log.text)
            lines = describe(controller)
            self.assertTrue(lines[0].startswith("primary"))
            self.assertIn("claude:haiku:low", lines[1])
        finally:
            remove(controller.project.root)


class AppLifecycleTest(unittest.IsolatedAsyncioTestCase):
    async def test_app_runs_the_controller_and_exits_after_a_clean_shutdown(self):
        from research_pipeline import controller as controller_module

        root = temp_project()
        saved = controller_module.WATCH_INTERVAL
        controller_module.WATCH_INTERVAL = 0.02
        try:
            controller = Controller(root, launch_options(), drivers=FAKE_DRIVERS, read_quota=lambda backend: [])
            with create_pipe_input() as pipe:
                app = TerminalApp(controller, input=pipe, output=DummyOutput())
                running = asyncio.ensure_future(app.run())
                for _ in range(200):
                    await asyncio.sleep(0.02)
                    if "primary" in controller.sessions:
                        break
                session = controller.sessions["primary"]
                app.shutdown()  # Ctrl+Q: agents hand off, then the app exits
                await asyncio.sleep(0.1)
                (root / "agents" / "primary" / "HANDOFF.md").write_text("# Handoff\n")
                session.emit("turn_ended", text="")
                self.assertEqual(await asyncio.wait_for(running, 10), 0)
                self.assertEqual(controller.state.status, "paused")
                self.assertTrue(any("Shutting down cleanly" in entry.text for entry in app.entries))
        finally:
            controller_module.WATCH_INTERVAL = saved
            remove(root)


if __name__ == "__main__":
    unittest.main()
