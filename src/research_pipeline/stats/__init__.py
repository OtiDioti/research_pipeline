"""Statistics of an investigation, for the web page's Stats view and ``research-pipeline stats``.

Deterministic and read-only: the activity logs, the phases' states and the briefs
are read (:mod:`.sources`), each tool call is turned into the files it read, ran or
wrote (:mod:`.calls`), attributed to their owners and gathered per agent
(:mod:`.analysis`), counted (:mod:`.figures`) and laid out (:mod:`.view`), or
summarised for the terminal (:mod:`.summary`). No model is asked anything.
"""

from research_pipeline.stats.summary import summary
from research_pipeline.stats.view import Statistics

__all__ = ["Statistics", "summary"]
