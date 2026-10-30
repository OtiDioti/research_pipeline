# Research workbench foundation

This directory contains the `theoretical-research-pipeline` distribution and its
`research_pipeline` import package. It provides package identity, CLI help/version,
and development validation. It implements no research execution, models,
scientific verification, or vault generation. It does not complete M0 or the D01
scientific-contract gate. Implementation is submitted for review; controller
acceptance and integration are separate events.

Use Python 3.11+; Linux is the initially verified development platform. The product
has no third-party runtime dependencies. Git is required for development validation
of repository administration and source revision. Setuptools (>=61) is build tooling
only, declared through `setuptools.build_meta`; it is not imported by the product.
Frozen validation requires no installation or downloads.

Run these exact commands from the repository root:

```bash
PYTHONPATH="$PWD/implementation/src" python3 -B -m research_pipeline --help
PYTHONPATH="$PWD/implementation/src" python3 -B -m research_pipeline --version
PYTHONPATH="$PWD/implementation/src:$PWD/implementation" python3 -B -m unittest discover -s implementation/tests -t implementation -v
python3 -B implementation/scripts/validate.py
```

No arguments also prints help. Unknown commands, options, and abbreviated options
produce a usage error (status 2). There is no research command or console-script
interface. Explicit candidate-source paths avoid relying on an editable install
from another checkout.

Direct unittest discovery provides useful development feedback. The validator also
checks root layout, required documents, candidate import origin, clean nonempty
discovery, and at least one executed successful case. Skipped and expected-failure
cases do not satisfy that last requirement. Failures, errors, unexpected successes,
and missing/empty suites fail validation. Diagnostics retain tracebacks and report
counts and the actual source HEAD; source exports without a revision explicitly
report it as unavailable with a reason. Revision output describes source context,
not acceptance.

The validator derives the repository root from its own location, accepts no root
or bypass options, and disables bytecode writes. Tests launch isolated subprocesses
and use disposable fixtures, including Git administration fixtures without commits.
They check that fixture bytes and directory contents remain unchanged. Import-effect
guards demonstrate observed behavior, not a security sandbox.

Root directories and regular `.md` files are allowed; root symlinks are forbidden.
Git's legitimate `.git` pointer file is an exception checked using Git's read-only
resolver. `project_description.md`, `README.md`, and `AGENTS.md` must be non-symlink,
nonempty UTF-8 regular files. Validation never rewrites those documents.

See [foundation architecture](../docs/architecture.md) for module boundaries and
future scientific-runtime limits.
