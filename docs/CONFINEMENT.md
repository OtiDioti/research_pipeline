# Confinement

`agent_sessions` (`confine.py`), the package shared with coding_pipeline and
project_manager. Every agent session and every job runs inside one bubblewrap
(`bwrap`) boundary. The CLIs' own sandboxes are switched off; this one mechanism
serves every CLI.

## Agent sessions

- The whole filesystem is readable, except `.research/`, which appears empty.
- Everything is read-only except the write scope below.
- `/tmp` and `/dev/shm` are private to the session. **Projects must therefore not live under `/tmp`.**
- The session has its own process namespace and ends with the controller: anything
  it started in the background ends with it. Long computations go through jobs.
- The network is on.

| Role | Writable |
|---|---|
| Every agent | Its folder `agents/<id>/`, `sources/`, `tools/`, and its CLI's state folder |
| Primary | Also STATUS.md, REPORT.md and the root FOLDER_CONTENT.md (STATUS.md and REPORT.md stay read-only while its proposal is reviewed) |
| Reviewer | Also `reviews/` |

The CLI state folders are those of Codex (`$CODEX_HOME` or `~/.codex`) and Claude
Code (`$CLAUDE_CONFIG_DIR`, or `~/.claude`, `~/.claude.json` and `~/.cache/claude`).

**Masked files.** Files of the human's own CLI setup appear as empty, read-only
files, and folders as empty folders: the Codex `config.toml`, `AGENTS.md`,
`AGENTS.override.md` and `rules/`. The empty file shown in their place is
`~/.cache/agent-sessions/empty`, emptied at
every use.

## Jobs

- Everything is as the controller sees it, including devices (e.g. GPUs) and the shared `/tmp`.
- Except: `starting_evidence/` is read-only, and `.research/` appears empty.
- Each job has its own process namespace, and outlives the controller.

## Consequences worth knowing

- **Single-file binds.** STATUS.md, REPORT.md and the root FOLDER_CONTENT.md are
  writable as single files inside a read-only folder. Editing them in place works.
  Tools that write a temporary file and rename it over the original fail, and so
  does deleting them: `sed -i`, many editors, atomic writers, `rm`.
- **Mount points must exist.** bwrap only mounts paths that already exist. The
  controller creates the write scope before a session starts. A missing masked
  file has nothing to hide.
- **Reads are not restricted.** Agents and jobs can read the rest of the machine
  (the home folder, CLI logins), and the network is on.
- **Jobs can write elsewhere.** A job can write anywhere in the project other than
  `starting_evidence/`, including other agents' folders and `.git`.
