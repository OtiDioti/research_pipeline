"""The statistics: what tool calls touched, attributed per agent, and the Stats view and summary built from them.

The scenario runs a real controller with fake CLIs; the tests act as the agents, calling
the research tools and reporting each tool call as a CLI would, so the activity log
holds what a run would.
"""

from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path

from research_pipeline.cli import main
from research_pipeline.stats import Statistics, summary
from research_pipeline.stats.calls import call, shell
from research_pipeline.web import ResearchDashboard
from tests.helpers import launch_options, remove, running, temp_project


def accesses(command: str) -> list[tuple[str, str]]:
    return [(access.op, access.path) for access in shell(command, None).accesses]


class CallsTest(unittest.TestCase):
    def test_shell_commands_read_run_write_and_move(self):
        self.assertEqual(
            accesses("/bin/bash -lc 'sed -n 1,20p ../y/RESULT.md | head -5'"), [("read", "../y/RESULT.md")]
        )
        self.assertEqual(accesses("rg -n 'fit' notes ../x"), [("search", "notes"), ("search", "../x")])
        self.assertEqual(accesses("uv run --locked python ../x/fit.py --n 3"), [("run", "../x/fit.py")])
        self.assertEqual(accesses("cd ../x && python run.py > out.log 2>&1"), [("write", "out.log"), ("run", "run.py")])
        self.assertEqual(shell("cd ../x && python run.py", None).accesses[0].cwd, "../x")
        self.assertEqual(accesses("for f in a b; do cat notes/$f.md; done"), [("read", "notes/$f.md")])
        self.assertEqual(
            accesses("cp ../x/a.py tools/ && pytest tests/"),
            [("read", "../x/a.py"), ("write", "tools/"), ("run", "tests/")],
        )
        self.assertEqual(
            accesses("cat > PLAN.md <<'EOF'\n# Plan\nrm -rf everything\nEOF\nls"), [("write", "PLAN.md"), ("list", ".")]
        )
        self.assertEqual(shell("frobnicate x", None).unparsed, 1)
        self.assertTrue(shell("cat 'unbalanced", None).cut)

    def test_whole_calls_and_summaries_of_older_runs(self):
        read = call({"call": {"name": "Read", "input": {"file_path": "/p/a.md"}}})
        self.assertEqual((read.kind, read.accesses[0].op, read.accesses[0].path), ("read", "read", "/p/a.md"))
        job = call({"call": {"name": "mcp__research__run_job", "input": {"command": "python ../x/fit.py", "cwd": ""}}})
        self.assertEqual(
            (job.kind, job.name, [(a.op, a.path) for a in job.accesses]),
            ("research", "run_job", [("run", "../x/fit.py")]),
        )
        accept = call({"call": {"name": "accept", "input": {"agent": "fit"}}})
        self.assertEqual(accept.arguments, {"agent": "fit"})
        old = call({"text": "$ cat ../x/RESULT.md  → exit 0"})
        self.assertEqual(([(a.op, a.path) for a in old.accesses], old.cut), ([("read", "../x/RESULT.md")], False))
        self.assertTrue(call({"text": "$ " + "cat a " * 60 + "  → exit 0"}).cut)
        cut = call({"text": 'Bash({"command": "cat ../x/RESULT.md", "description": "Read the res)'})
        self.assertEqual(([(a.op, a.path) for a in cut.accesses], cut.cut), ([("read", "../x/RESULT.md")], True))
        self.assertEqual(call({"text": "edit /p/a.md, /p/b.md"}).accesses[1].path, "/p/b.md")


class StatisticsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = temp_project()

    def tearDown(self):
        remove(self.root)

    async def test_a_run_is_attributed_per_agent_and_shown(self):
        primary = "phases/1/agents/primary"
        async with running(self.root, launch_options()) as harness:

            async def tool(agent: str, called: str, server: str | None = None, /, **arguments) -> None:
                await harness.emit(agent, "tool", text=called, server=server, call={"name": called, "input": arguments})

            harness.write(f"{primary}/notes/plan.md", "# Plan\n")
            harness.write(f"{primary}/notes/scratch.md", "# Scratch\n")
            harness.write(
                f"{primary}/brief-fit.md",
                "# Fit the data\n\n## Prior work\n\n[The plan](../primary/notes/plan.md) and "
                "[the library](../../../../library/LIBRARY.md).\n",
            )
            await tool("primary", "shell", command="cat ../../../../library/LIBRARY.md ../../../../library/CATALOG.md")
            reply = await harness.call(
                "primary", "spawn", task="brief-fit.md", name="fit", backend="codex", model="gpt-test", effort="high"
            )
            self.assertIn("Started subagent fit", reply)
            await tool("primary", "spawn", "research", task="brief-fit.md", name="fit")
            await tool("fit", "Read", file_path=str(self.root / primary / "notes" / "plan.md"))  # a link it was given
            await tool("fit", "shell", command="cat ../primary/notes/scratch.md")  # a file it was not given
            await tool("fit", "message", "research", agent="primary", text="Which data?")
            harness.write("phases/1/agents/fit/fit.py", "print(1)\n")
            harness.write("phases/1/agents/fit/data.csv", "x\n1\n")
            harness.write("phases/1/agents/fit/RESULT.md", "# Result\n\nFitted.\n")
            harness.handoff("fit")
            harness.index("phases/1/agents/fit", "TASK.md", "RESULT.md", "HANDOFF.md", "fit.py", "data.csv")
            self.assertIn("was submitted", await harness.call("fit", "submit_result"))
            await tool("fit", "submit_result", "research")
            await tool("primary", "shell", command="cat ../fit/RESULT.md ../fit/data.csv && python ../fit/fit.py")
            self.assertIn("Accepted", await harness.call("primary", "accept", agent="fit"))
            await tool("primary", "accept", "research", agent="fit")

            statistics = Statistics(self.root)
            view = statistics.describe(None, [])
            self.assertEqual(view["scope"], "1")
            self.assertEqual([tab["id"] for tab in view["tabs"]], ["library", "spawning", "checking", "resources"])
            overview = {item["label"]: item["value"] for item in view["overview"]}
            self.assertEqual(overview["Subagents"], "1")
            self.assertEqual(overview["Brief links opened"], "1 of 2 (50%)")
            self.assertEqual(overview["Parent's files read unlinked"], "1")
            self.assertEqual(overview["Results rejected"], "0 of 1 (0%)")
            self.assertEqual(overview["Reads of work under review"], "1")  # data.csv; RESULT.md is the protocol's
            fit = {section["title"]: dict(section["rows"]) for section in view["agents"]["fit"]["sections"]}
            self.assertEqual(fit["Its brief's links"], {
                "Prior work section": "yes",
                f"{primary}/notes/plan.md": "opened",
                "library/LIBRARY.md": "not opened",
            })  # fmt: skip
            self.assertEqual(list(fit["Its parent's files it read without a link"]), [f"{primary}/notes/scratch.md"])
            self.assertEqual(fit["Its results"]["Messages to its parent"], "1")
            card = {section["title"]: dict(section["rows"]) for section in view["agents"]["primary"]["sections"]}
            self.assertEqual(card["Its children"]["Review of fit"], "accept, 1 reads, 1 runs")
            self.assertEqual(card["Library"]["Read before its first spawn"], "yes")
            self.assertEqual(card["Library"]["Catalogue reads"], "1")
            lanes = next(item for item in view["tabs"][1]["items"] if item["type"] == "timeline")["lanes"]
            fit_lane = next(lane for lane in lanes if lane["id"] == "fit")
            self.assertIn("submitted", [segment["state"] for segment in fit_lane["segments"]])
            matrix = next(item for item in view["tabs"][1]["items"] if item["type"] == "matrix")
            self.assertEqual(matrix["values"][matrix["rows"].index("fit")][matrix["columns"].index("primary")], 2)

            compared = statistics.describe("all", [str(self.root)])
            self.assertEqual(compared["tabs"][0]["id"], "comparison")
            self.assertTrue(
                any(
                    line["run"]
                    for item in compared["tabs"][1]["items"]
                    if item["type"] == "series"
                    for line in item["series"]
                )
            )
            with self.assertRaises(ValueError):
                statistics.describe(None, [str(self.root.parent)])  # not a project
            with self.assertRaises(ValueError):
                statistics.describe("7", [])
            self.assertIn("Brief links opened", summary(statistics, "1"))
            dashboard = ResearchDashboard(self.root, launch_options())
            self.assertTrue(dashboard.offers_stats)
            self.assertEqual(dashboard.stats(None, [])["scope"], "1")

    def test_the_command_line_prints_the_summary_or_refuses_what_is_not_a_project(self):
        self.assertEqual(main(["stats", str(self.root.parent / "nowhere")]), 2)
        project = Path(self.root)
        (project / ".research").mkdir(exist_ok=True)
        (project / ".research" / "state.json").write_text('{"agents": {}, "jobs": {}}')  # a project from before phases
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            self.assertEqual(main(["stats", str(project)]), 0)
        self.assertIn("Subagents", printed.getvalue())
