# Product implementation

Product code, tests, packaging, dependency manifests, and validation utilities belong here, keeping the repository root Markdown-only.

This directory currently contains only this note. D01 will create the actual implementation through CWI. The proposed initial layout is `pyproject.toml`, `src/research_pipeline/`, `tests/`, and `scripts/validate.py`. Python 3.11+ with stdlib unittest is a bootstrap proposal to confirm against the product specification.

Tests must import source from the **current CWI worktree**, not from an editable installation tied to the original checkout. The standard validation command is established in D01; it does not exist yet.

Dependencies are installed outside an active CWI run. Build outputs, caches, and environments are not evidence of accepted source and should be isolated or ignored by deliberately reviewed configuration. Nested `.gitignore` files are permitted by the root convention, but adding or changing any `.gitignore` can block CWI's automatic merge with the embedded checkout; use the reviewed manual integration process.
