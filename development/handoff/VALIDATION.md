# Handoff verification

The packaging checks below concern development recovery. They do not accept L5,
re-run scientific investigations or turn historical failed gates into passes.

## Completed checks

- Copied frozen requests, configuration, reviews, test outputs and acceptance
  records retain their original bytes. CONTENTS.json records original paths and
  SHA-256 hashes, including hashes for all 202 checkpoint archive members and
  all 470 interrupted final-006 archive members.
- Four restoration checks use real temporary Git clones: successful recovery
  with unchanged source and valid pipeline ownership; refusal to overwrite an
  existing run; refusal of the wrong pipeline revision; preservation of an
  uncommitted target. They failed before the restorer existed and passed after
  implementation.
- A separate clean temporary project clone, under a path containing spaces,
  used the recorded pipeline/controller/preparer Git revisions. The real
  project-manager preparation refreshed the temporary controller's prompts.
  The real pipeline accepted the restored worktree ownership and returned the
  saved interrupted/final state through discover, status and report.
- L5 stayed at 2e3e7b3e95714e9aa08d84b1d11f7bea01707105 and remained unmerged.
  The clean-clone target's main source was unchanged by restoration.
- Routine product discovery completed successfully: 308 tests, eight skipped,
  no failures. All native/live gates were disabled. This checked the accepted
  main implementation with the candidate handoff files present.
- A merge simulation in a separate temporary clone confirmed that these handoff
  changes leave L5 mergeable without content conflicts. The actual L5 branch
  was neither changed nor merged.
- An independent read-only review found no Critical or Important issues.
  Publication housekeeping was to finish this validation record, update the
  packaging checklist, and generate/verify SHA256SUMS.

## Checks to repeat when packaging changes

```sh
python -m unittest discover -s development/handoff/tests -v
cd development/handoff
sha256sum --check SHA256SUMS
```

The restoration tests require the pinned pipeline clone at coding_pipeline/ and
the published L5 Git objects. They create their own disposable clones and do not
resume a run. Routine product discovery is a separate check; keep all historical
live/native gates and the L5 native switch disabled for that offline check.

## Limits

These checks used the existing Python environment and available dependencies.
They did not download dependencies into a fresh machine, provision Linux user
services/cgroups, copy authentication, probe real weekly quota or start native
model inference. The new host must independently satisfy those prerequisites.
Only later required enabled final/combined pipeline verification can accept L5.

SHA256SUMS and CONTENTS.json detect changed files against this capture. They do
not authenticate the Git repository or establish a scientific result.
