"""The message log: what agents and the human said to an agent, kept in its folder (PROJECT.md §3, "Messages").

A message reaches its recipient as a notice in its session, which ends with the
session. So that nothing said is lost, the controller appends every message an
agent sends or receives (from its parent, a subagent or the human) to
MESSAGES.md in that agent's folder, with when it was sent, by whom and to whom.
The controller's own notices are not messages and are not logged.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from agent_toolkit.records import atomic_write

#: The log's name in an agent's folder.
MESSAGES = "MESSAGES.md"
#: Its one-line description in the folder's index.
DESCRIPTION = "Every message I sent or received (from my parent, my subagents or the human), kept by the controller."
_HEADER = "# Messages\n"


def record(folder: Path, root: Path, sender: str, recipient: str, text: str, at: datetime | None = None) -> None:
    """Append the message ``text`` from ``sender`` to ``recipient`` to the log in ``folder`` (inside ``root``)."""
    log = folder / MESSAGES
    previous = log.read_text(encoding="utf-8") if log.exists() else _HEADER
    when = (at or datetime.now()).strftime("%Y-%m-%d %H:%M")
    atomic_write(log, f"{previous.rstrip()}\n\n## {when}, from {sender} to {recipient}\n\n{text.strip()}\n", root=root)
