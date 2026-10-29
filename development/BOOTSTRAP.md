# First implementation run: a bounded bootstrap

## Why this is necessary

The target starts with only Markdown. CWI's automatic admission cannot infer an existing suite or a supported test-free runner from that. The proposed nested `implementation/pyproject.toml` also requires explicit validation once it exists.

Do **not** add product source manually to trick discovery, ask the outer Codex agent to write a test harness outside CWI, or use `--check true`. The first foundation must itself be implemented through CWI.

Use one narrowly scoped run with a **frozen, inline bootstrap check**. Its sole exception admits the exact pre-existing Markdown-only commit. Every different candidate must contain the testable foundation and execute non-skipped tests. The check exists as an operator-reviewed command; it is not a runtime feature of the product.

## Preconditions

D00 has reconciled the real specification and approved the first request. The documentation and request are committed. The target is clean and no other run is active. The source contains only tracked Markdown files at this initial baseline. Dependencies, exclusions, authentication, and the stable `cwi` helper in [RUNBOOK.md](RUNBOOK.md) are prepared.

If there is already product source, this is not the correct bootstrap path: inspect the existing implementation and use its appropriate passing baseline checks.

## Construct the exact command

Run this from the target root **after the final prelaunch commit**. Do not commit another change between capturing `BASE_COMMIT` and launching the run.

```bash
BASE_COMMIT="$(git rev-parse HEAD)"
BOOTSTRAP_CHECK="$(python3 - "$BASE_COMMIT" <<'PY'
import shlex
import sys

program = r"""
from pathlib import Path
import importlib
import subprocess
import sys
import unittest

root = Path.cwd().resolve()
base = sys.argv[1]
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()

def require(condition, message):
    if not condition:
        raise SystemExit(message)

def check_root():
    # A linked worktree legitimately has a Git-created .git pointer file.
    forbidden = [p.name for p in root.iterdir()
                 if p.name != '.git'
                 and (p.is_file() or p.is_symlink())
                 and (p.suffix != '.md' or p.is_symlink())]
    require(not forbidden, 'Non-Markdown/symlink root entries: ' + repr(forbidden))
    for name in ('project_description.md', 'README.md', 'AGENTS.md'):
        path = root / name
        require(path.is_file() and not path.is_symlink() and bool(path.read_text(encoding='utf-8').strip()),
                'Missing or empty required document: ' + name)

check_root()
if head == base:
    tracked = subprocess.check_output(['git', 'ls-files', '-z']).decode('utf-8').split('\0')
    require(all(not p or Path(p).suffix == '.md' for p in tracked),
            'The exact bootstrap base must contain only tracked Markdown files')
    print('BOOTSTRAP BASELINE ONLY: exact documentation source; no product tests exist.')
else:
    implementation = root / 'implementation'
    src = implementation / 'src'
    tests = implementation / 'tests'
    for relative in ('pyproject.toml', 'src/research_pipeline/__init__.py',
                     'tests/__init__.py', 'scripts/validate.py'):
        require((implementation / relative).is_file(), 'Missing foundation: ' + relative)
    # Prevent an installed package in the original checkout from masking broken candidate code.
    sys.path[:0] = [str(src), str(implementation)]
    package = importlib.import_module('research_pipeline')
    require(Path(package.__file__).resolve().is_relative_to(src.resolve()),
            'Product import did not come from this candidate worktree')
    suite = unittest.defaultTestLoader.discover(str(tests), pattern='test_*.py',
                                               top_level_dir=str(implementation))
    require(suite.countTestCases() > 0, 'Candidate contains no discovered tests')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = (result.testsRun - len(result.skipped) - len(result.expectedFailures)
              - len(result.failures) - len(result.errors) - len(result.unexpectedSuccesses))
    require(result.wasSuccessful() and passed > 0,
            'Candidate needs passing, executed, non-skipped tests')
    # Exercise the persistent validator that will be used after bootstrap.
    subprocess.run([sys.executable, '-B', str(implementation / 'scripts/validate.py')],
                   check=True)
    print('BOOTSTRAP CANDIDATE:', head, 'executed=', result.testsRun, 'passed=', passed)
check_root()
"""
# CWI parses this string with shlex and launches argv directly, without a shell.
print(shlex.join([sys.executable, '-B', '-c', program, sys.argv[1]]))
PY
)"
```

The Python validation program embedded above is shown normally here for review:

```python
from pathlib import Path
import importlib
import subprocess
import sys
import unittest

root = Path.cwd().resolve()
base = sys.argv[1]
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()

def require(condition, message):
    if not condition:
        raise SystemExit(message)

def check_root():
    # A linked worktree legitimately has a Git-created .git pointer file.
    forbidden = [p.name for p in root.iterdir()
                 if p.name != '.git'
                 and (p.is_file() or p.is_symlink())
                 and (p.suffix != '.md' or p.is_symlink())]
    require(not forbidden, 'Non-Markdown/symlink root entries: ' + repr(forbidden))
    for name in ('project_description.md', 'README.md', 'AGENTS.md'):
        path = root / name
        require(path.is_file() and not path.is_symlink() and bool(path.read_text(encoding='utf-8').strip()),
                'Missing or empty required document: ' + name)

check_root()
if head == base:
    tracked = subprocess.check_output(['git', 'ls-files', '-z']).decode('utf-8').split('\0')
    require(all(not p or Path(p).suffix == '.md' for p in tracked),
            'The exact bootstrap base must contain only tracked Markdown files')
    print('BOOTSTRAP BASELINE ONLY: exact documentation source; no product tests exist.')
else:
    implementation = root / 'implementation'
    src = implementation / 'src'
    tests = implementation / 'tests'
    for relative in ('pyproject.toml', 'src/research_pipeline/__init__.py',
                     'tests/__init__.py', 'scripts/validate.py'):
        require((implementation / relative).is_file(), 'Missing foundation: ' + relative)
    # Prevent an installed package in the original checkout from masking broken candidate code.
    sys.path[:0] = [str(src), str(implementation)]
    package = importlib.import_module('research_pipeline')
    require(Path(package.__file__).resolve().is_relative_to(src.resolve()),
            'Product import did not come from this candidate worktree')
    suite = unittest.defaultTestLoader.discover(str(tests), pattern='test_*.py',
                                               top_level_dir=str(implementation))
    require(suite.countTestCases() > 0, 'Candidate contains no discovered tests')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = (result.testsRun - len(result.skipped) - len(result.expectedFailures)
              - len(result.failures) - len(result.errors) - len(result.unexpectedSuccesses))
    require(result.wasSuccessful() and passed > 0,
            'Candidate needs passing, executed, non-skipped tests')
    # Exercise the persistent validator that will be used after bootstrap.
    subprocess.run([sys.executable, '-B', str(implementation / 'scripts/validate.py')],
                   check=True)
    print('BOOTSTRAP CANDIDATE:', head, 'executed=', result.testsRun, 'passed=', passed)
check_root()
```

No source file is written by this command. The implementation and permanent validator are left to CWI. CWI freezes the command in its normal validation profile and executes it against the isolated baseline and subsequent exact candidate commits.

The program rejects a missing suite, skipped-only results, imports from a different source checkout, missing foundation files, and forbidden root files. It does not assess whether tests are scientifically or behaviorally adequate; that remains an explicit acceptance criterion and review responsibility.

## Launch scope

Use [REQ-D01-001](requests/REQ-D01-001.md), `--max-milestones 1`, and the bootstrap check, with no automatic merge. The single-milestone limit matters: partial foundation commits that cannot satisfy the complete bootstrap check must not become separately accepted milestones.

The full launch command is in [RUNBOOK.md](RUNBOOK.md).

## Completion restrictions

The exact documentation baseline deliberately passes admission without product tests. CWI can also represent no-op candidates, so the first request explicitly prohibits a no-op, and the coordinator must additionally require `accepted_head != base_commit` before declaring D01 complete. This limitation is explicit rather than pretending the backend exposes a baseline/candidate flag that it does not have.

Do not broaden the exception to `if tests are missing: success` or retain it for later runs. After acceptance and integration, use the permanent validator in a new frozen profile.

## Permanent validator contract

D01 creates `implementation/scripts/validate.py`. It must:

- Resolve the repository and `implementation/src` from its own location, not depend on an editable installation of the original checkout.
- Enforce the Markdown-only root rule while correctly handling `.git` administration and ignoring only designated directories as directories.
- Discover product tests in `implementation/tests` and reject zero execution, skipped-only suites, unexpected successes, failures, and errors. Expected failures do not count as successful executed coverage.
- Report the source revision and actual test result summary without fabricating execution.
- Avoid writing or reformatting source, metadata, or status files. Use temporary locations or already-ignored output paths for generated artifacts.
- Be covered by focused tests for its failure paths; avoid recursively invoking its whole test suite from those tests.

Relevant root-development link/structure checks can be included without making planned nonexistent files mandatory. The existing product description must remain unchanged.

The initial gate is verified as an operator-side command in this kit's review evidence. It is not a claim that the future product validator or local CWI installation already exists or passes.
