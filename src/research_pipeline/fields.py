"""The launch options as the web page's settings: the setup page's fields, and which of them change live.

A phase's own settings (its title, and the earlier phase it builds on) come first on the setup page.
"""

from __future__ import annotations

from agent_toolkit.web import Field

#: The options the page shows, in the order :meth:`ResearchDashboard.values` gives them.
NAMES = (
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
    "references",
    "durable",
)


def phase_fields(earlier: list[int]) -> list[Field]:
    """A phase's title and the phase it builds on (``earlier``: the phases it may build on)."""
    return [
        Field("title", "Phase title", "line", "A short name for this phase, shown in the Phases list."),
        Field(
            "builds_on",
            "Builds on",
            "select",
            "An earlier phase whose result and status the primary starts from; every phase's finished work is "
            "in the library anyway.",
            options=["none", *(str(number) for number in earlier)],
        ),
    ]


def fields(backends: list[str]) -> list[Field]:
    """Every launch option as a setting of the page (``backends``: the CLIs one may choose)."""
    return [
        Field(
            "primary",
            "Primary researcher",
            "spec",
            "Leads the investigation. Changed while it runs: from its next session.",
            options=backends,
            live=True,
        ),
        Field(
            "reviewer",
            "Reviewer",
            "spec",
            "Reviews a proposal to finish. Changed while it runs: from its next session.",
            options=backends,
            live=True,
        ),
        Field(
            "librarian",
            "Librarian",
            "spec",
            "Keeps the library's pages. Changed while it runs: from its next session.",
            options=backends,
            live=True,
        ),
        Field(
            "backends",
            "CLIs for subagents",
            "multiselect",
            "The CLIs agents may choose for their subagents.",
            options=backends,
            live=True,
        ),
        Field(
            "coding",
            "Recommended for coding",
            "spec",
            "The model the prompt recommends for subagents that write, debug and run code, simulations and "
            "tools (agents may choose another). Changed while it runs: from each agent's next session.",
            options=backends,
            live=True,
            within="backends",
            advisory=True,
        ),
        Field(
            "analysis",
            "Recommended for analysis",
            "spec",
            "The model the prompt recommends for subagents that derive, read literature, interpret data and "
            "critique (agents may choose another). Changed while it runs: from each agent's next session.",
            options=backends,
            live=True,
            within="backends",
            advisory=True,
        ),
        Field(
            "max_agents",
            "Sessions at once",
            "integer",
            "Agent sessions open at the same time, idle ones included.",
            min=2,
            max=16,
            step=1,
            live=True,
        ),
        Field(
            "idle_limit",
            "Idle limit",
            "number",
            "Minutes an idle session waits before it saves its handoff and closes (0: never).",
            min=0,
            max=240,
            step=1,
            unit="min",
            live=True,
        ),
        Field(
            "threshold",
            "Handoff threshold",
            "number",
            "Context fill at which an agent hands off.",
            min=0.05,
            max=0.8,
            step=0.01,
            live=True,
        ),
        Field(
            "short_limit",
            "Short-window limit",
            "number",
            "Usage left in a short window that pauses its CLI.",
            min=0,
            max=50,
            step=1,
            unit="%",
            live=True,
        ),
        Field(
            "weekly_limit",
            "Weekly limit",
            "number",
            "Usage left in a weekly window that pauses its CLI until you resume it.",
            min=0,
            max=50,
            step=1,
            unit="%",
            live=True,
        ),
        Field(
            "references",
            "Reference folders",
            "paths",
            "Read-only folders of other projects agents may consult.",
            group="advanced",
        ),
        Field(
            "durable",
            "Durable state",
            "bool",
            "Force every state write to disk (off: faster on network filesystems).",
            group="advanced",
        ),
    ]
