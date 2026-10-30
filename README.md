# Theoretical research pipeline

An evidence-oriented workbench for theoretical scientific research. The product requirements are in [project_description.md](project_description.md). This repository contains the **software that implements that workbench**; it is not itself a live scientific investigation.

**Current maturity:** a testable Python foundation and the requested synthetic harmonic/quartic development example are accepted and integrated. The suite passes 28 tests. Research execution and expert scientific evaluation remain unimplemented; development is held at the required M0 scientific decision gate. See [the mock walkthrough](docs/synthetic-oscillator.md), [M0 decision packet](development/decisions/M0-contract-and-scientific-review.md), and [current evidence/status](STATUS.md).

## Start here

| Question | Read |
| --- | --- |
| What should the product do? | [Project description](project_description.md) |
| What is happening, and what is the next action? | [STATUS.md](STATUS.md) |
| What is the implementation sequence? | [ROADMAP.md](ROADMAP.md) |
| How is development controlled? | [DEVELOPMENT.md](DEVELOPMENT.md) |
| What is deferred, blocked, or deliberately paused? | [BACKLOG.md](BACKLOG.md) |
| Why were important choices made? | [DECISIONS.md](DECISIONS.md) |
| What has actually been integrated? | [CHANGELOG.md](CHANGELOG.md) |
| What must Codex do? | [AGENTS.md](AGENTS.md) and [startup/activation/continuation prompts](development/CODEX_START.md) |
| How does it continue across development steps? | [Continuous policy](development/AUTONOMY.md) and [actual authorization](development/AUTHORIZATION.md) |
| Which model and effort does development use? | [Model policy](development/MODEL_POLICY.md) |
| What happens if the coding backend breaks? | [Maintenance procedure](development/BACKEND_MAINTENANCE.md) and [change audit](coding_pipeline_changes.md) |
| How do I apply this update to work already started? | [Update guide](development/UPDATE_GUIDE.md) |
| How do I prepare and run the coding pipeline? | [Runbook](development/RUNBOOK.md) |
| How does a repository with no tests get started? | [Bootstrap procedure](development/BOOTSTRAP.md) |
| What was checked in the supplied coding pipeline? | [Repository review](development/PIPELINE_REVIEW.md) |

## Development model

A top-level Codex session acts as the **development coordinator**. It maintains plans, prepares bounded change requests, invokes the local coding pipeline, inspects its evidence, and updates development records. Product code, tests, executable scripts, build configuration, and runtime prompts are implemented through that pipeline, not directly by the coordinator. Necessary focused repairs of the separate coding backend are the documented exception, with regression evidence and a complete audit.

The recommended workflow holds the first accepted result for human review, then uses one continuous grant to proceed across requests and phases without repeated routine prompts. A separately selected preauthorization can remove the first review pause. Durable checkpoints support later sessions, but this kit installs no automatic restart supervisor.

The local clone must be named `coding_pipeline/`, even if its remote repository has a different name. It remains an untracked, locally excluded development dependency, not a Git submodule and not a mandatory runtime tool of the research product.

The pipeline's delegated Writer is allowed to implement the prescribed change directly in its private worktree. It must not launch another coding-pipeline run.

## Directory conventions

Regular files at this repository's root are Markdown. Product implementation and configuration belong under [implementation/](implementation/README.md). Development requests, phase plans, reviews, and evidence summaries belong under [development/](development/README.md). Local transient information belongs under [local/](local/README.md).

Git's own `.git` administration is an exception: it is normally a directory here and a Git-created pointer file in linked worktrees.

## Important status distinction

`implemented` is not `accepted`; `accepted` is not `integrated`.

Only a completed coding-pipeline run with the required final acceptance evidence can establish coding-pipeline acceptance. The accepted commit must then be deliberately integrated. A checked box, successful inspection command, agent message, or branch name is not a substitute.

This starter kit does not replace or reproduce your existing `project_description.md`. Preserve that file and reconcile the proposed roadmap against its exact contents before implementation.
