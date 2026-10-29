# Development environment contract

Complete this record on the actual machine before starting a run. No local installation is asserted by this starter kit. Do not store credentials or the complete environment here.

| Field | Actual value |
| --- | --- |
| Operating system | Not yet inspected; Linux is the reviewed backend's verification target |
| Python version and absolute executable | Not yet inspected; CWI requires Python 3.11+ |
| Git version | Not yet inspected; must support `git worktree list --porcelain -z` |
| Target repository branch | Not yet inspected |
| Target repository absolute path | Record locally if publishing it would disclose private information |
| Controller remote and commit | Record the credential-free remote and `git -C coding_pipeline rev-parse HEAD`; never publish embedded remote tokens |
| Controller working tree | Must be clean before a new run |
| Reviewed archive identity | Archive comment reports `122f86588f829387ea460a1e2a997a87ce325c53`; verify against the clone before treating it as the same revision |
| Codex executable selected by CWI | Record the actual frozen path/version, not merely the first `codex` on PATH |
| Model and reasoning choice | Explicitly select or record the resolved default; no model ID is assumed here |
| Authentication source | Normal Codex login or approved existing CODEX_HOME; do not copy credentials into Git |
| Stable launch environment | Record the chosen variable names and non-secret values; private paths may remain in `local/` |
| Product dependencies | Initial proposal: stdlib runtime/test foundation; later dependencies require explicit preparation |
| Backend verification evidence | Local results to be added; see supplied-snapshot review separately |
| Permission to launch CWI outside outer sandbox | Not yet established |
| Phase/merge/spending authorization | See STATUS; first run has no automatic merge |

The reviewed backend hashes every inherited environment name/value for resume, before minimizing the child-agent environment. A different exported variable can therefore prevent continuation. The runbook uses a small explicit environment as a proposed operational mitigation. Corporate certificate paths or other necessary variables must be deliberately included and kept identical; do not silently strip a required setting.

Record installation/version changes **between** safely completed runs. Updating Codex while a run is unfinished can invalidate its frozen executable digest. Updating the controller itself also changes the reviewed implementation even if its package version remains unchanged.
