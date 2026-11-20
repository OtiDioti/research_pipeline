# Jobs

`jobs.py`. Long computations that agents start with `run_job`. A job runs outside
the agent's session, so it survives handoffs, quota pauses, a shutdown and a crash
of the controller. Agents should use a job for anything longer than a minute.

## Starting

`run_job(command, timeout_seconds, cwd)`:
- The timeout is required: any positive number of seconds.
- `cwd` defaults to the agent's folder and must be a folder in the project (not `.research/`).
- The job is refused while the investigation isn't running, and for the primary while its proposal is under review.
- It runs in its own confinement ([CONFINEMENT.md](CONFINEMENT.md)):
  `starting_evidence/`, `library/` and the folders of shelved agents
  ([LIBRARY.md](LIBRARY.md)) are read-only, `.research/` is hidden, everything else
  is as the controller sees it, and it has its own process namespace.
- The timeout is enforced inside the job itself (coreutils `timeout`, then a kill
  10 s later), so it holds even while the controller is down.

## Files

In the phase's `agents/<owner>/jobs/<job-id>/`, indexed by the controller in the jobs folder's `FOLDER_CONTENT.md`:

| File | Content |
|---|---|
| `command.txt` | The working folder, timeout and command |
| `stdout.log`, `stderr.log` | The output |
| `exit_code` | Written by the job's wrapper when the command ends, even while the controller is down |

## Statuses

| Status | Meaning |
|---|---|
| `running` | Still running |
| `finished` | Exit code 0 |
| `failed` | Any other exit code |
| `timeout` | Stopped at its timeout |
| `cancelled` | Stopped by `job_cancel`, a cancelled owner, a human pause or the end of the investigation |
| `lost` | Ended without an exit code, e.g. killed from outside |

When a job ends, its owner is told, with the last 30 lines of each log; an owner
resting without a session is woken by it, and a paused one gets it when it continues. `job_status` shows the
same at any time.

## What stops a job

| Event | Jobs |
|---|---|
| Handoff, quota hold, agent failure | Keep running |
| Shutdown (Ctrl+Q), forced exit (Ctrl+C), crash | Keep running; the next `run` reattaches them and reads their exit codes |
| Human pause (Ctrl+P) | Stopped; the owner is told to rerun it if still needed |
| `job_cancel`, cancelling the owner, COMPLETE or STOP | Stopped |

Stopping sends SIGTERM to every process of the job, waits up to 5 s, then sends
SIGKILL. A job is recognised after a restart by its process id and start time, so
a reused process id is never mistaken for it.

An agent can't submit a result or propose COMPLETE or STOP while its own jobs are running.
