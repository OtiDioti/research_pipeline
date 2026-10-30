"""Read-only development validation of candidate layout, origin, and real tests."""

import argparse
import importlib
import os
from pathlib import Path
import subprocess
import sys
import unittest


def check_root_layout(root, stream):
    """Report invalid root entries/documents to stream and return whether layout is valid."""
    valid = True
    for entry in sorted(root.iterdir()):
        reason = None
        if entry.is_symlink():
            reason = "root symlinks are forbidden"
        elif entry.is_dir():
            continue
        elif entry.is_file() and entry.name == ".git":
            # Linked worktrees need this exception; Git owns administration semantics.
            try:
                pointer = entry.read_text(encoding="utf-8").strip()
                if not pointer.startswith("gitdir: ") or len(pointer.splitlines()) != 1:
                    raise ValueError("expected a single gitdir: <path> pointer")
                target = pointer[len("gitdir: "):].strip()
                if not target or not (root / target).is_dir():
                    raise ValueError("missing Git target directory")
                resolved = subprocess.run(
                    ["git", "rev-parse", "--resolve-git-dir", str(entry)],
                    capture_output=True, text=True, check=False,
                )
                if resolved.returncode:
                    raise ValueError(resolved.stderr.strip() or "Git rejected pointer")
            except (OSError, UnicodeError, ValueError) as error:
                reason = f"invalid Git pointer: {error}"
        elif entry.is_file() and entry.suffix == ".md":
            continue
        else:
            reason = "expected a directory or regular Markdown file"
        if reason:
            print(f"Layout failure: {entry}: {reason}", file=stream)
            valid = False

    for name in ("project_description.md", "README.md", "AGENTS.md"):
        document = root / name
        try:
            if document.is_symlink() or not document.is_file():
                raise ValueError("missing or not a non-symlink regular document")
            if not document.read_text(encoding="utf-8").strip():
                raise ValueError("empty document")
        except (OSError, UnicodeError, ValueError) as error:
            print(f"Layout failure: {document}: {error}", file=stream)
            valid = False
    return valid


class CoverageResult(unittest.TextTestResult):
    """Count actual successful cases without crediting skips or expected failures."""

    def __init__(self, stream, descriptions, verbosity):
        """Initialize unittest reporting and the positive-coverage counter."""
        super().__init__(stream, descriptions, verbosity)
        self.successful_cases = 0

    def addSuccess(self, test):
        """Credit a completed successful case, including only fully passing subtests."""
        # Subtest failures do not call addSuccess; subtraction would miscount them.
        self.successful_cases += 1
        super().addSuccess(test)


def run_suite(root, stream):
    """Discover candidate tests and report counts; return true only for real passing coverage."""
    implementation = root / "implementation"
    tests = implementation / "tests"
    if not tests.is_dir() or not (tests / "__init__.py").is_file():
        print(f"Missing test suite or __init__.py: {tests}; tests did not run.", file=stream)
        return False
    loader = unittest.TestLoader()
    try:
        suite = loader.discover(str(tests), pattern="test_*.py", top_level_dir=str(implementation))
    except Exception as error:
        print(f"Discovery failure: {error}; tests did not run.", file=stream)
        return False
    discovered = suite.countTestCases()
    for error in loader.errors:
        print(f"Discovery error: {error}", file=stream)
    result = unittest.TextTestRunner(
        stream=stream, verbosity=2, resultclass=CoverageResult,
    ).run(suite)
    print(
        f"Counts: discovered={discovered} testsRun={result.testsRun} "
        f"successful={result.successful_cases} skipped={len(result.skipped)} "
        f"expected_failures={len(result.expectedFailures)} failures={len(result.failures)} "
        f"errors={len(result.errors)} unexpected_successes={len(result.unexpectedSuccesses)}",
        file=stream,
    )
    return bool(discovered and not loader.errors and result.wasSuccessful() and result.successful_cases)


def run_validation(root, stream):
    """Validate an explicit candidate root for development/tests, returning a process status."""
    sys.dont_write_bytecode = True
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        root = Path(root).resolve()
        try:
            revision = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
                capture_output=True, text=True, check=False,
                # A nested source export must not inherit an enclosing repository's HEAD.
                env={**os.environ, "GIT_CEILING_DIRECTORIES": str(root.parent)},
            )
            if revision.returncode:
                print(f"Source revision: unavailable ({revision.stderr.strip()})", file=stream)
            else:
                print(f"Source revision: {revision.stdout.strip()}", file=stream)
        except OSError as error:
            print(f"Source revision: unavailable ({error})", file=stream)
        if not check_root_layout(root, stream):
            print("Layout failed; tests did not run.", file=stream)
            return 1
        src = (root / "implementation" / "src").resolve()
        sys.path[:0] = [str(src), str(root / "implementation")]
        try:
            package = importlib.import_module("research_pipeline")
            origin = Path(package.__file__).resolve()
            if not origin.is_relative_to(src):
                raise ValueError(f"package origin {origin} is outside candidate {src}")
        except Exception as error:
            print(f"Import-origin failure: {error}; tests did not run.", file=stream)
            return 1
        print(f"Package origin: {origin}", file=stream)
        return 0 if run_suite(root, stream) else 1
    except Exception as error:
        print(f"Operational validation error: {error}", file=stream)
        return 1


def main():
    """Validate the repository derived from this script's location, with no bypass options."""
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.parse_args()
    return run_validation(Path(__file__).resolve().parents[2], sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
