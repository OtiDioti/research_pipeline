# Development environment contract

Complete this on the actual machine before model-dependent work. This template establishes no local installation, authentication, approved spending, or completed tests. Preserve an existing environment record during update. Never store credentials or a complete environment dump here.

| Field | Actual value |
| --- | --- |
| Operating system | Not inspected; Linux is the reviewed backend's verification target |
| Python version / absolute executable | Not inspected; backend requires Python 3.11+ |
| Git version | Not inspected; must support worktree porcelain -z |
| Target branch / specification revision | Inspect locally |
| Target absolute path | Keep locally when disclosure would be inappropriate |
| Controller remote / upstream base / active commit | Record credential-free identities; exact local revision matters |
| Controller working tree | Inspect and preserve existing edits; new runs use a clean committed backend |
| Reviewed archive identity | Archive comment reports 122f86588f829387ea460a1e2a997a87ce325c53; verify before assuming equivalence |
| Backend repairs / patch backup | Link coding_pipeline_changes.md and recoverable patch/bundle identities |
| Codex selected by CWI | Actual frozen path/version/digest, not only the first codex on PATH |
| Requested model | Astra 6.1 — retained user requirement |
| Exact supported model ID / provider | UNRESOLVED; do not invent a slug or substitute a model |
| Resolution/access evidence | Actual local catalog/account evidence or explicit human-approved correction |
| Effort policy | Explicit supported low/medium/high/xhigh; hard ceiling xhigh |
| Selected effort for next request | Choose by workload before launch; recorded per-run, frozen on resume |
| Actual invocation evidence | Retained configuration/argv and available effective-model telemetry; note limitations |
| Authentication / billing mode | Approved Codex login or existing CODEX_HOME; establish subscription allowance vs API billing |
| Stable launch environment | Names and non-secret values only; preserve private values/paths locally |
| Product dependencies | Proposed stdlib foundation; prepare later dependencies between runs |
| Backend verification | Actual local results; prior snapshot tests are separate evidence |
| Permission for CWI outside outer sandbox | Not established by this template |
| Operating grant and usage limits | Actual authorization record; no new purchases implied |
| Live scientific-provider allowance | Not established by this template |

The backend hashes the inherited environment for resume, before minimizing the child-agent environment. Even an extra exported variable can prevent continuation. The runbook's small explicit environment is the proposed mitigation; deliberately include any necessary fixed certificate/proxy settings and preserve them unchanged.

CWI isolates its child configuration. Set its model/effort explicitly at start, not only in the outer Codex session or a normal profile. Adapt effort between runs; never change a frozen pair on resume. See [MODEL_POLICY.md](MODEL_POLICY.md) for the unresolved requested-name check and official references.

Record changes only at a safe boundary. Codex updates can invalidate the frozen executable digest. Backend source changes require [BACKEND_MAINTENANCE.md](BACKEND_MAINTENANCE.md); they are not made safe merely because the Codex binary is unchanged. Preserve original run identities, regression evidence, and patch provenance.
