"""The tools agents act through, offered by the controller over MCP (see :class:`agent_toolkit.tools.ToolBridge`).

Each agent's CLI starts :mod:`agent_toolkit.tool_server` with the tools of its
role (PROJECT.md §7); every call reaches the controller's ``_tool_*`` methods.
The descriptions below are what agents read.
"""

from agent_toolkit.tools import Tool

TEXT = {"type": "string"}


class ToolError(Exception):
    """A tool call the controller refuses; its message is returned to the agent."""


SPAWN = Tool(
    "spawn",
    "Start a subagent on a task, to solve a subproblem separately or in parallel.\n\n"
    "task: path of a Markdown brief you wrote (objective, how it serves your objective, relevant\n"
    "evidence and tools, expected result). It is copied to the subagent's TASK.md, its relative\n"
    "links rewritten to lead to the same files from there. backend, model, effort: the subagent's CLI, model and\n"
    "reasoning effort, all required. name: short id such as 'convergence-check'. You are told\n"
    "when it submits its result.",
    {"task": TEXT, "backend": TEXT, "model": TEXT, "effort": TEXT, "name": {"type": "string", "default": ""}},
    ("task", "backend", "model", "effort"),
)
AGENTS = Tool("agents", "List your subagents with their status and context use.")
MESSAGE = Tool(
    "message",
    "Message your parent or one of your own subagents; it receives the text during its turn.\n\n"
    "Messages are not stored: the recipient notes what matters. A subagent that has submitted\n"
    "its result receives none; accept, reject or cancel it instead.",
    {"agent": TEXT, "text": TEXT},
    ("agent", "text"),
)
ACCEPT = Tool("accept", "Accept the result a subagent submitted; it then ends.", {"agent": TEXT}, ("agent",))
REJECT = Tool(
    "reject",
    "Reject a subagent's submitted result; it continues with your feedback (what is missing or wrong).",
    {"agent": TEXT, "feedback": TEXT},
    ("agent", "feedback"),
)
CANCEL = Tool("cancel", "Cancel a subagent and everything it started.", {"agent": TEXT}, ("agent",))
RUN_JOB = Tool(
    "run_job",
    "Run a shell command as a job that survives your session; you are told when it ends.\n\n"
    "Use it for anything longer than a minute. timeout_seconds: required, any length (hours are\n"
    "fine). cwd: folder to run in (default: your folder). Output goes to your jobs/ folder.",
    {"command": TEXT, "timeout_seconds": {"type": "number"}, "cwd": {"type": "string", "default": ""}},
    ("command", "timeout_seconds"),
)
JOB_STATUS = Tool("job_status", "Show a job's status and the last lines of its output.", {"job": TEXT}, ("job",))
JOB_CANCEL = Tool("job_cancel", "Stop a job and all its processes.", {"job": TEXT}, ("job",))
SUBMIT_RESULT = Tool(
    "submit_result",
    "Submit your result (a Markdown file in your folder) to your parent; your session then ends.",
    {"result": {"type": "string", "default": "RESULT.md"}},
)
COMPLETE = Tool(
    "complete",
    "Propose COMPLETE: the phase's result shows every current objective met (or shown infeasible).\n\n"
    "An independent Reviewer then examines the work; COMPLETE needs its agreement.",
    {"result": {"type": "string", "description": "The phase's result file; by default the one you were told."}},
)
STOP = Tool(
    "stop",
    "Propose to STOP (continuing needs human intervention or is not justified), with your reason.\n\n"
    "The Reviewer first challenges it. Afterwards call stop(reason, final=True) to confirm, or simply continue.",
    {"reason": TEXT, "final": {"type": "boolean", "default": False}},
    ("reason",),
)
VERDICT = Tool(
    "verdict",
    "Deliver your review (a Markdown file in reviews/) and whether you agree with the proposal.",
    {"review": TEXT, "agree": {"type": "boolean"}},
    ("review", "agree"),
)

WRITE_PAGE = Tool(
    "write_page",
    "Write a Markdown page of library/, replacing it if it exists; empty text removes it.\n\n"
    "path: relative to library/, ending in .md (e.g. 'LIBRARY.md', 'methods/FOLDER_CONTENT.md').\n"
    "library/CATALOG.md and library/catalog/ are the controller's. Link to the agents' work with relative paths (from\n"
    "library/methods/x.md: '../../phases/1/agents/fit-check/notes.md'); a link to a folder covers everything in it.",
    {"path": TEXT, "text": TEXT},
    ("path", "text"),
)
SHELVED = Tool(
    "shelved",
    "Report a shelving request done: every file of the agent's folder is reachable from your pages.\n\n"
    "folder: as the request names it (e.g. 'phases/2/agents/fit-check').\n"
    "Refused, with the files and links concerned, while a file of the folder is reachable from no page,\n"
    "a link in library/ leads nowhere, or a folder of library/ lacks its FOLDER_CONTENT.md lines.",
    {"folder": TEXT},
    ("folder",),
)

# The setup assistant's tools (research_pipeline.assistant), before the first start.
QUESTION = {
    "type": "object",
    "properties": {
        "question": {"type": "string", "description": "The complete question."},
        "header": {"type": "string", "description": "A label of one or two words."},
        "multi": {"type": "boolean", "description": "True if several options may be chosen."},
        "options": {
            "type": "array",
            "minItems": 2,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {"label": TEXT, "description": TEXT},
                "required": ["label", "description"],
            },
        },
    },
    "required": ["question", "header", "options"],
}
ASK = Tool(
    "ask",
    "Ask the human one round of multiple-choice questions (1 to 4, each with 2 to 4 options); the page\n"
    "adds a free answer to each. End your turn afterwards: the answers come as your next request.",
    {"questions": {"type": "array", "minItems": 1, "maxItems": 4, "items": QUESTION}},
    ("questions",),
)
WRITE_OBJECTIVES = Tool(
    "write_objectives",
    "Write the phase's OBJECTIVES.md (Markdown, the whole file), replacing it; the human sees it\nin their editor.",
    {"text": TEXT},
    ("text",),
)
PLACE = Tool(
    "place",
    "Place loose material in starting_evidence/, each entry with a one-line description; nothing moves if any\n"
    "entry is refused (the reply names every problem).\n\n"
    "entries: [{path, folder, description}], path as listed, folder 'starting_evidence' or a subfolder of it.\n"
    "folders: [{path, description}] for every new folder on the way.",
    {
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"path": TEXT, "folder": TEXT, "description": TEXT},
                "required": ["path", "folder", "description"],
            },
        },
        "folders": {
            "type": "array",
            "default": [],
            "items": {
                "type": "object",
                "properties": {"path": TEXT, "description": TEXT},
                "required": ["path", "description"],
            },
        },
    },
    ("entries",),
)
SETUP_TOOLS = [ASK, WRITE_OBJECTIVES, PLACE]
# The further tool of the assistants of a reopening and of a new phase (research_pipeline.assistant).
WRITE_AGENTS_MD = Tool(
    "write_agents_md",
    "Write AGENTS.md (Markdown, the whole file), replacing it: the human's standing instructions to every\n"
    "agent. Only when the human asks for it.",
    {"text": TEXT},
    ("text",),
)
PHASE_TOOLS = [ASK, WRITE_OBJECTIVES, WRITE_AGENTS_MD, PLACE]

# The one tool of a talk session after the end (research_pipeline.talks).
WRITE_TALK_NOTE = Tool(
    "write_talk_note",
    "Save your talk note (Markdown), replacing the previous one: what the human asked, what you answered,\n"
    "what remains open. Your next talk session starts from it.",
    {"note": TEXT},
    ("note",),
)

_COMMON = [SPAWN, AGENTS, MESSAGE, ACCEPT, REJECT, CANCEL, RUN_JOB, JOB_STATUS, JOB_CANCEL]
#: Tools offered to each role.
ROLE_TOOLS = {
    "primary": _COMMON + [COMPLETE, STOP],
    "subagent": _COMMON + [SUBMIT_RESULT],
    "reviewer": _COMMON + [VERDICT],
    "librarian": [WRITE_PAGE, SHELVED],
}
