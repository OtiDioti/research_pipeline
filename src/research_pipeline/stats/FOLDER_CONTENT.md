# Folder contents

- [__init__.py](__init__.py) — The package's entry points: Statistics (the Stats view) and summary (the terminal).
- [sources.py](sources.py) — What is read from a project, incrementally: phases, agents, jobs and activity logs.
- [calls.py](calls.py) — What one tool call did to files: shell command rules, Claude Code's tools, the research tools.
- [analysis.py](analysis.py) — Accesses resolved and attributed per agent: timelines, brief links, the parent's files, reviews.
- [figures.py](figures.py) — The numbers and lines over time drawn from an analysis.
- [tabs.py](tabs.py) — The overview strip and the tabs: Library, Spawning, Checking, Resources, Comparison.
- [view.py](view.py) — Statistics: scopes, compared projects, notes and agent cards; the whole Stats view.
- [summary.py](summary.py) — The terminal summary of `research-pipeline stats`.
