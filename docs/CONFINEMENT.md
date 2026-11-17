# Confinement

`agent_toolkit` (`confine.py`), the package shared with coding_pipeline and
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
`~/.cache/agent-toolkit/empty`, emptied at
every use.

**Root-owned SSH configuration.** Inside the boundary, files owned by root appear
owned by "nobody", and ssh refuses such files among its configuration. The files of
`/etc/ssh/ssh_config.d` are therefore shown as copies owned by you, with the same
content, kept in `~/.cache/agent-toolkit/owned/` and refreshed at every start.
Jobs get the same copies.

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

## SSH and remote machines

Agents and jobs can use ssh, scp, rsync and git over SSH as you do: your keys,
your ssh-agent and `~/.ssh/config` are visible, and the network is on. What to
know before letting them use a machine such as a computing cluster:

- **Host keys.** `~/.ssh` is read-only, so a machine's host key must already be in
  `~/.ssh/known_hosts`: connect to it once yourself first.
- **No prompts.** Only logins that need no typing work: keys, through your
  ssh-agent or an unencrypted key. Passwords, key passphrases and one-time codes
  cannot be answered.
- **No secrets in the project.** Describe the machine (host, user name, rules) in
  a file in `starting_evidence/` and point to it from `AGENTS.md`, but never write
  passwords there: agents' context goes to the CLI's provider, and the project is
  committed to git.
- **Long computations.** Submit them to the machine's own scheduler (e.g. `sbatch`)
  and check on them with short commands; transfers and waits longer than a minute
  go through `run_job`.
- **No confinement there.** On the remote machine agents act with your account
  and its permissions; your rules file is guidance only.
