"""Read-only development validation of candidate layout, origin, and real tests."""

import argparse
import ctypes
import errno
import functools
import hashlib
import io
import json
import math
import platform
import re
try:
    import resource
except ImportError:
    resource = None
import selectors
import shutil
import signal
import struct
import tempfile
import threading
import time
import traceback
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


def _validate_root(root, stream, sequential, invocation):
    """Check layout and candidate origin, then discover within an already supervised invocation."""
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
        invocation.check()
        return 0 if _run_suite(root, stream, sequential, invocation) else 1
    except Exception as error:
        print(f"Operational validation error: {error}", file=stream)
        return 1


def main():
    """Validate the repository derived from this script's location, with no bypass options."""
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--sequential", action="store_true", help="run the complete discovered suite sequentially")
    arguments = parser.parse_args()
    return run_validation(Path(__file__).resolve().parents[2], sys.stdout, sequential=arguments.sequential)


# These limits supplement, and never replace, the controller's external bounds.
OUTPUT_LIMIT = 16 * 1024 * 1024
INVOCATION_SECONDS = 2650
PROTOCOL_VERSION = 1
COUNT_NAMES = ('testsRun', 'successful', 'skipped', 'expected_failures',
               'failures', 'errors', 'unexpected_successes')


class ValidationError(Exception):
    """Report an integrity or operational failure without replaying uncertain work."""


class DiscoveryLoader(unittest.TestLoader):
    """Observe discovery hooks while leaving stock discovery and hook invocation intact."""

    def __init__(self):
        """Create fresh loader state and an ordered list of observed hook owners."""
        super().__init__()
        self.hooks = []

    def loadTestsFromModule(self, module, *args, **kwargs):
        """Record a hook once per stock invocation, then delegate without invoking it here."""
        if getattr(module, 'load_tests', None) is not None:
            self.hooks.append(module.__name__)
        return super().loadTestsFromModule(module, *args, **kwargs)


def inventory_digest(ids):
    """Hash ordered IDs using the documented ASCII-escaped compact UTF-8 JSON encoding."""
    return hashlib.sha256(json.dumps(ids, ensure_ascii=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def _module_cleanup_fallback_reason():
    """Return a serial reason unless live stock CPython module cleanup state is empty.

    Read the private shared stack without invoking callbacks or unknown objects'
    truth/iteration methods. Other implementations and representations cannot
    establish independence and therefore require intact suite execution.
    """
    unavailable = 'unavailable or unrecognized unittest module cleanup state'
    if sys.implementation.name != 'cpython':
        return unavailable + ': requires stock CPython'
    cleanups = getattr(unittest.case, '_module_cleanups', None)
    if type(cleanups) is not list:
        return unavailable + ': expected an exact built-in list'
    if cleanups:
        return 'pending process-global unittest module cleanups'
    return None


def plan_suite(suite, root, hooks=()):
    """Inventory discovered objects once and return leaves, contiguous units and serial reasons.

    Custom containers are inspected only through a stable stock-backed list and
    stock iteration. Their execution remains intact; opaque inventories fail closed.
    Live process-global module cleanups require intact execution after discovery.
    """
    leaves, seen_objects, seen_ids, active, reasons = [], set(), set(), set(), []
    if hooks:
        reasons.append('discovery hooks: ' + ', '.join(hooks))

    def visit(node):
        """Walk stable containers, rejecting cycles, aliases and inconsistent counts."""
        identity = id(node)
        if identity in active:
            raise ValidationError('Inventory cycle')
        if identity in seen_objects:
            raise ValidationError('Repeated inventory object occurrence')
        seen_objects.add(identity)
        active.add(identity)
        before = len(leaves)
        if isinstance(node, unittest.TestSuite):
            if (type(getattr(node, '_tests', None)) is not list or
                    type(node).__iter__ is not unittest.TestSuite.__iter__ or
                    '__iter__' in vars(node)):
                raise ValidationError('Unsupported opaque suite inventory: ' + type(node).__name__)
            if type(node) is not unittest.TestSuite or any(
                    name in vars(node) for name in dir(unittest.TestSuite)
                    if callable(getattr(unittest.TestSuite, name, None))):
                reasons.append('custom suite: ' + type(node).__name__)
            children = tuple(node._tests)
            for child in children:
                visit(child)
            if tuple(map(id, node._tests)) != tuple(map(id, children)):
                raise ValidationError('Unstable suite inventory')
        elif isinstance(node, unittest.TestCase):
            test_id = node.id()
            if type(test_id) is not str or not test_id:
                raise ValidationError('Unsupported test ID')
            if test_id in seen_ids:
                raise ValidationError('Duplicate test ID: ' + test_id)
            seen_ids.add(test_id)
            cls = type(node)
            owner = cls.__module__
            if type(owner) is not str or not owner:
                raise ValidationError('Ambiguous fixture owner: ' + test_id)
            machinery = ('run', '__call__', '_callSetUp', '_callTestMethod', '_callTearDown',
                         '_callCleanup', 'doCleanups', 'subTest')
            if isinstance(node, unittest.FunctionTestCase) or any(
                    getattr(cls, name) is not getattr(unittest.TestCase, name) or name in vars(node)
                    for name in machinery):
                reasons.append('custom case execution: ' + test_id)
            leaves.append(dict(ordinal=len(leaves), id=test_id, owner=owner,
                               class_name=unittest.util.strclass(cls), cls=cls, test=node))
        else:
            raise ValidationError('Unsupported inventory leaf: ' + type(node).__name__)
        count = node.countTestCases()
        if type(count) is not int or count != len(leaves) - before:
            raise ValidationError('Inconsistent countTestCases: ' + type(node).__name__)
        active.remove(identity)

    visit(suite)
    declarations = []
    tests = (root / 'implementation').resolve()
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if isinstance(filename, str) and Path(filename).resolve().is_relative_to(tests):
            declarations.append((module.__name__, vars(module)))
    for leaf in leaves:
        for cls in leaf['cls'].__mro__:
            declarations.append((unittest.util.strclass(cls), vars(cls)))
    for name, namespace in declarations:
        declaration = namespace.get('VALIDATION_SERIAL', False)
        if type(declaration) is not bool:
            raise ValidationError('Malformed VALIDATION_SERIAL on ' + name + ': expected bool')
        if declaration:
            reasons.append('VALIDATION_SERIAL: ' + name)
    units, owners = [], set()
    for leaf in leaves:
        if not units or units[-1][0]['owner'] != leaf['owner']:
            if leaf['owner'] in owners:
                reasons.append('repeated fixture owner: ' + leaf['owner'])
            owners.add(leaf['owner'])
            units.append([])
        units[-1].append(leaf)
    # A class identity cannot straddle modules; ambiguous textual scope names cannot
    # safely explain unittest's _ErrorHolder callbacks either.
    classes = {}
    for leaf in leaves:
        previous = classes.setdefault(leaf['class_name'], leaf['cls'])
        if previous is not leaf['cls']:
            raise ValidationError('Ambiguous class fixture identity: ' + leaf['class_name'])
    # Import/hook registrations share one opaque LIFO stack, with no module owner
    # mapping. Only intact traversal preserves cross-module cleanup transitions.
    cleanup_reason = _module_cleanup_fallback_reason()
    if cleanup_reason is not None:
        reasons.append(cleanup_reason)
    return leaves, units, list(dict.fromkeys(reasons))


def parse_cpu_set(value):
    """Parse a nonempty Linux CPU range list, rejecting malformed or excessive ranges."""
    cpus = set()
    if not value.strip():
        raise ValueError('empty CPU set')
    for part in value.strip().split(','):
        if not re.fullmatch(r'\d+(?:-\d+)?', part):
            raise ValueError('malformed CPU range: ' + part)
        ends = [int(item) for item in part.split('-')]
        first, last = ends[0], ends[-1]
        if first > last or last > 1048575:
            raise ValueError('invalid CPU range: ' + part)
        cpus.update(range(first, last + 1))
    return cpus


def quota_bound(quota, period):
    """Return a conservative integral CPU bound; -1/max denote unlimited quotas."""
    if not re.fullmatch(r'[1-9]\d*', period):
        raise ValueError('invalid quota period')
    if quota in ('max', '-1'):
        return None
    if not re.fullmatch(r'[1-9]\d*', quota):
        raise ValueError('invalid CPU quota')
    return max(1, int(quota) // int(period))


def mount_unescape(value):
    """Decode Linux mountinfo's octal escapes without interpreting ordinary backslashes."""
    return re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)), value)


def cgroup_constraints(cgroup_text, mount_text, read_text):
    """Resolve exposed v1/v2 ancestors, returning quota bounds, cpus and limitations.

    read_text accepts an absolute path and raises ordinary filesystem exceptions;
    this makes hierarchy interpretation testable without changing host controls.
    Hidden ancestors and unreadable/ambiguous active limits are unknown, not unlimited.
    """
    bounds, masks, limitations, observations = [], [], [], []
    memberships, mounts = [], []
    try:
        for line in cgroup_text.splitlines():
            hierarchy, controllers, path = line.split(':', 2)
            if not path.startswith('/') or '..' in Path(path).parts:
                raise ValueError('invalid cgroup membership')
            memberships.append((controllers.split(',') if controllers else [], path))
        for line in mount_text.splitlines():
            left, right = line.split(' - ', 1)
            fields, detail = left.split(), right.split()
            if detail[0] in ('cgroup', 'cgroup2'):
                mounts.append((detail[0], mount_unescape(fields[3]),
                               mount_unescape(fields[4]), detail[2].split(',')))
    except (ValueError, IndexError) as error:
        return [], [], ['unresolved cgroup hierarchy: ' + str(error)], []

    def optional(path):
        """Distinguish a genuinely absent controller file from inaccessible evidence."""
        try:
            return read_text(str(path)).strip()
        except FileNotFoundError:
            return None

    for controllers, membership in memberships:
        relevant = ['cpu', 'cpuset'] if not controllers else [c for c in controllers if c in ('cpu', 'cpuset')]
        for controller in relevant:
            candidates = [m for m in mounts if (m[0] == 'cgroup2' if not controllers else
                          m[0] == 'cgroup' and controller in m[3]) and
                          Path(membership).is_relative_to(m[1])]
            if len(candidates) != 1:
                limitations.append('unresolved/ambiguous ' + controller + ' cgroup mount')
                continue
            kind, mount_root, mountpoint, _ = candidates[0]
            if mount_root != '/':
                limitations.append('hidden ' + controller + ' ancestry above ' + mount_root)
            base = Path(mountpoint)
            current = base / Path(membership).relative_to(mount_root)
            ancestors = []
            while True:
                ancestors.append(current)
                if current == base:
                    break
                current = current.parent
            # Root-to-leaf delegation establishes whether missing v2 files are
            # legitimate, including cpu listed but never enabled at the root.
            active_controller = kind == 'cgroup'
            try:
                for path in reversed(ancestors):
                    if kind == 'cgroup2':
                        available = optional(path / 'cgroup.controllers')
                        delegated = optional(path / 'cgroup.subtree_control')
                        if available is None or delegated is None:
                            raise ValueError('missing v2 controller/delegation evidence at ' + str(path))
                    if controller == 'cpu':
                        if kind == 'cgroup2':
                            quota = optional(path / 'cpu.max')
                            if quota is not None:
                                parts = quota.split()
                                if len(parts) != 2:
                                    raise ValueError('malformed cpu.max at ' + str(path))
                                bound = quota_bound(*parts)
                            elif active_controller:
                                raise ValueError('missing active cpu.max at ' + str(path))
                            else:
                                bound = None
                        else:
                            quota = optional(path / 'cpu.cfs_quota_us')
                            period = optional(path / 'cpu.cfs_period_us')
                            if quota is None or period is None:
                                raise ValueError('missing active v1 quota at ' + str(path))
                            bound = quota_bound(quota, period)
                        if bound is not None:
                            bounds.append((str(path), bound))
                    else:
                        filename = 'cpuset.cpus.effective' if kind == 'cgroup2' else 'cpuset.cpus'
                        value = optional(path / filename)
                        if value:
                            masks.append(parse_cpu_set(value))
                        elif value is None and active_controller:
                            raise ValueError('missing active cpuset at ' + str(path))
                        elif value == '' and kind == 'cgroup2':
                            raise ValueError('empty effective cpuset at ' + str(path))
                    if kind == 'cgroup2':
                        observations.append(f'{path}: {controller} delegated={controller in delegated.split()}')
                        active_controller = controller in delegated.split()
            except (OSError, ValueError) as error:
                limitations.append(controller + ' constraint unknown: ' + str(error))
    if not memberships:
        limitations.append('missing cgroup membership')
    return bounds, masks, limitations, observations


def sample_resources():
    """Sample effective CPUs without mutating affinity; unknown constraints force A=1."""
    bounds, limitations, observations = [], [], []
    allowed = None
    affinity_available = False
    for name in ('process_cpu_count', 'cpu_count'):
        function = getattr(os, name, None)
        if function is not None:
            try:
                value = function()
                if type(value) is int and value > 0:
                    bounds.append((name, value))
                else:
                    limitations.append(name + ' unavailable')
            except OSError as error:
                limitations.append(name + ': ' + str(error))
    if hasattr(os, 'sched_getaffinity') and hasattr(os, 'sched_setaffinity'):
        try:
            allowed = set(os.sched_getaffinity(0))
            if not allowed:
                raise ValueError('empty affinity')
            bounds.append(('affinity', len(allowed)))
            affinity_available = True
        except (OSError, ValueError) as error:
            limitations.append('affinity unavailable: ' + str(error))
            allowed = None
    else:
        limitations.append('affinity unavailable')
    try:
        quotas, masks, unknown, observations = cgroup_constraints(
            Path('/proc/self/cgroup').read_text(), Path('/proc/self/mountinfo').read_text(),
            lambda path: Path(path).read_text())
        bounds.extend(quotas)
        for mask in masks:
            allowed = allowed & mask if allowed is not None else None
            bounds.append(('cpuset', len(mask)))
        if allowed is not None:
            bounds.append(('allowed intersection', len(allowed)))
        limitations.extend(unknown)
    except (OSError, ValueError) as error:
        unknown = ['cgroup constraints unknown: ' + str(error)]
        limitations.extend(unknown)
    effective = max(1, min((value for _, value in bounds), default=1))
    if allowed == set():
        limitations.append('empty allowed CPU intersection')
    if unknown or allowed == set():
        effective = 1
    # Knowing a cpuset does not prove that setting affinity is available.
    affinity = affinity_available and allowed is not None
    return dict(A=effective, allowed=sorted(allowed) if affinity else None,
                bounds=bounds, limitations=limitations, observations=observations)


def concurrency_budget(available, remaining):
    """Return the required CPU allocation C for effective A and remaining independent T."""
    return min(remaining // 2, max(0, available - 2))


def result_counts(result):
    """Return stock unittest counters, keeping successful cases separate from event totals."""
    return dict(testsRun=result.testsRun, successful=result.successful_cases,
                skipped=len(result.skipped), expected_failures=len(result.expectedFailures),
                failures=len(result.failures), errors=len(result.errors),
                unexpected_successes=len(result.unexpectedSuccesses))


class CoverageResult(unittest.TextTestResult):
    """Retain unittest reporting and stream a leaf/subtest/fixture event ledger."""

    def __init__(self, stream, descriptions, verbosity, *, leaves=(), send=None):
        """Bind inherited discovered object identities to ordinals and an optional frame sink."""
        super().__init__(stream, descriptions, verbosity)
        self.successful_cases = 0
        self.leaves = {id(leaf['test']): leaf for leaf in leaves}
        self.send = send
        self.sequence = 0
        self.started = []
        self.completed = []

    def record(self, kind, test, detail='', subtest=None):
        """Emit exact result text, identifying genuine leaves separately from fixture holders."""
        if self.send is None:
            return
        phase, scope = '', ''
        if isinstance(test, unittest.case._SubTest):
            subtest, test = test, test.test_case
        leaf = self.leaves.get(id(test))
        if leaf is None:
            if type(test) is not unittest.suite._ErrorHolder:
                raise ValidationError('Unaccounted executed object: ' + test.id())
            match = re.fullmatch(r'(setUpModule|tearDownModule|setUpClass|tearDownClass) \((.*)\)', test.id())
            if not match:
                raise ValidationError('Unrecognized fixture holder: ' + test.id())
            phase, scope = match.groups()
            ordinal, test_id = None, test.id()
        else:
            ordinal, test_id = leaf['ordinal'], leaf['id']
        if subtest is not None:
            kind = 'subtest_' + kind
        frame = dict(type='event', seq=self.sequence, kind=kind, ordinal=ordinal,
                     id=test_id, phase=phase, scope=scope,
                     subtest=subtest.id() if subtest is not None else '', detail=detail)
        self.send(frame)
        self.sequence += 1
        if kind == 'start':
            self.started.append(ordinal)
        elif kind == 'stop':
            self.completed.append(ordinal)

    def startTest(self, test):
        """Record a real startTest callback after stock testsRun accounting."""
        super().startTest(test)
        self.record('start', test)

    def stopTest(self, test):
        """Record a genuine stopTest callback without inventing fixture completions."""
        super().stopTest(test)
        self.record('stop', test)

    def addSuccess(self, test):
        """Credit only actual successful cases, never individual passing subtests."""
        self.successful_cases += 1
        super().addSuccess(test)
        self.record('success', test)

    def addFailure(self, test, err):
        """Keep unittest's formatted assertion traceback verbatim in the protocol."""
        super().addFailure(test, err)
        self.record('failure', test, self.failures[-1][1])

    def addError(self, test, err):
        """Retain each error, including multiple cleanup errors on one leaf or fixture."""
        super().addError(test, err)
        self.record('error', test, self.errors[-1][1])

    def addSkip(self, test, reason):
        """Distinguish leaf, fixture and subtest skips with the original reason."""
        super().addSkip(test, reason)
        self.record('skip', test, reason)

    def addExpectedFailure(self, test, err):
        """Preserve an expected-failure traceback without positive coverage credit."""
        super().addExpectedFailure(test, err)
        self.record('expected_failure', test, self.expectedFailures[-1][1])

    def addUnexpectedSuccess(self, test):
        """Retain unittest's failing unexpected-success outcome."""
        super().addUnexpectedSuccess(test)
        self.record('unexpected_success', test)

    def addSubTest(self, test, subtest, err):
        """Record successful observations and exact failing/erroring subtest diagnostics."""
        super().addSubTest(test, subtest, err)
        if err is None:
            self.record('success', test, subtest=subtest)
        elif issubclass(err[0], test.failureException):
            self.record('failure', test, self.failures[-1][1], subtest)
        else:
            self.record('error', test, self.errors[-1][1], subtest)


def strict_object(pairs):
    """Decode a JSON object while rejecting duplicate keys at every nesting level."""
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValidationError('Duplicate JSON key: ' + key)
        value[key] = item
    return value


def reject_constant(value):
    """Reject JSON NaN/Infinity rather than accepting non-finite protocol numbers."""
    raise ValidationError('Non-finite JSON value: ' + value)


def require_fields(frame, fields):
    """Enforce exact frame field names and primitive types, including bool/int distinctions."""
    if type(frame) is not dict or set(frame) != set(fields):
        raise ValidationError('Invalid protocol fields')
    for name, kind in fields.items():
        kinds = kind if isinstance(kind, tuple) else (kind,)
        if type(frame[name]) not in kinds:
            raise ValidationError('Invalid protocol type: ' + name)


class EventLedger:
    """Validate one assigned unit's protocol and independently reconstruct its accounting."""

    def __init__(self, ordinal, pid, leaves, mask, ordered=True):
        """Initialize expected identities and transitions without trusting worker totals."""
        self.ordinal, self.pid, self.leaves, self.mask = ordinal, pid, leaves, mask
        self.ordered = ordered
        self.by_ordinal = {leaf['ordinal']: leaf for leaf in leaves}
        self.ids = [leaf['id'] for leaf in leaves]
        self.digest = inventory_digest(self.ids)
        self.hello = None
        self.end = None
        self.events = []
        self.started, self.completed = [], []
        self.active = None
        self.outcomes = {}
        self.fixture_dispositions = {}
        self.last_setup = None
        self.counts = dict.fromkeys(COUNT_NAMES, 0)

    def accept(self, frame):
        """Validate a hello, monotonically sequenced event, or one final cross-checked end."""
        if self.end is not None:
            raise ValidationError('Trailing frame after end')
        if self.hello is None:
            require_fields(frame, dict(type=str, version=int, unit=int, pid=int, digest=str,
                                       affinity=list))
            affinity = frame['affinity']
            if (frame['type'] != 'hello' or frame['version'] != PROTOCOL_VERSION or
                    frame['unit'] != self.ordinal or frame['pid'] != self.pid or
                    frame['digest'] != self.digest or
                    any(type(cpu) is not int or cpu < 0 for cpu in affinity) or
                    affinity != sorted(set(affinity)) or
                    self.mask is not None and affinity != self.mask):
                raise ValidationError('Invalid worker hello/identity/affinity')
            self.hello = frame
            return
        if frame.get('type') == 'end':
            require_fields(frame, dict(type=str, counters=dict, started=list, completed=list,
                                       execution_seconds=float))
            require_fields(frame['counters'], dict.fromkeys(COUNT_NAMES, int))
            if (self.active is not None or frame['counters'] != self.counts or
                    any(type(value) is not int for value in frame['started'] + frame['completed']) or
                    frame['started'] != self.started or frame['completed'] != self.completed or
                    not math.isfinite(frame['execution_seconds']) or frame['execution_seconds'] < 0):
                raise ValidationError('Inconsistent end frame/counters or missing stopTest')
            self.end = frame
            return
        require_fields(frame, dict(type=str, seq=int, kind=str, ordinal=(int, type(None)),
                                   id=str, phase=str, scope=str, subtest=str, detail=str))
        if frame['type'] != 'event' or frame['seq'] != len(self.events):
            raise ValidationError('Invalid event sequence')
        ordinal, kind = frame['ordinal'], frame['kind']
        if ordinal is None:
            self._fixture(frame)
        else:
            if type(ordinal) is not int or ordinal not in self.by_ordinal:
                raise ValidationError('Unknown event ordinal')
            leaf = self.by_ordinal[ordinal]
            if frame['id'] != leaf['id'] or frame['phase'] or frame['scope']:
                raise ValidationError('Inconsistent event ID/owner')
            if kind == 'start':
                if self.active is not None or ordinal in self.started or ordinal in self.fixture_dispositions:
                    raise ValidationError('Duplicate or impossible startTest')
                if self.ordered and self.started and ordinal <= self.started[-1]:
                    raise ValidationError('Reordered stock test execution')
                self.active = ordinal
                self.last_setup = None
                self.started.append(ordinal)
                self.outcomes[ordinal] = []
                self.counts['testsRun'] += 1
            elif self.active != ordinal:
                raise ValidationError('Callback outside active leaf: ' + kind)
            elif kind == 'stop':
                if not self.outcomes[ordinal] or all(
                        item == 'subtest_success' for item in self.outcomes[ordinal]):
                    raise ValidationError('stopTest without outcome')
                self.completed.append(ordinal)
                self.active = None
            else:
                self._outcome(frame)
            if kind in ('start', 'stop') and (frame['detail'] or frame['subtest']):
                raise ValidationError('Invalid start/stop fields')
        self.events.append(frame)

    def _outcome(self, frame):
        """Count callback categories without requiring their sum to equal testsRun."""
        kind, ordinal = frame['kind'], frame['ordinal']
        counters = dict(success='successful', failure='failures', error='errors', skip='skipped',
                        expected_failure='expected_failures', unexpected_success='unexpected_successes',
                        subtest_failure='failures', subtest_error='errors', subtest_skip='skipped')
        if kind not in counters and kind != 'subtest_success':
            raise ValidationError('Unknown outcome kind: ' + kind)
        if bool(frame['subtest']) != kind.startswith('subtest_'):
            raise ValidationError('Invalid subtest identity')
        prior = self.outcomes[ordinal]
        terminal = {'success', 'expected_failure', 'unexpected_success'}
        if any(item in terminal for item in prior):
            raise ValidationError('Callback after terminal outcome')
        if kind in terminal and prior and not all(item == 'subtest_success' for item in prior):
            raise ValidationError('Incompatible terminal outcome')
        if kind in ('success', 'unexpected_success', 'subtest_success') and frame['detail']:
            raise ValidationError('Unexpected outcome detail')
        if kind in counters:
            self.counts[counters[kind]] += 1
        prior.append(kind)

    def _fixture(self, frame):
        """Record fixture outcomes, inferring unstarted scopes only for stock traversal.

        unittest labels cleanup failures during failed setup with the setup phase;
        multiple such events are retained and any error dominates a fixture skip.
        Custom execution supplies no trustworthy extent, so its leaves stay not-run.
        """
        phase, scope, kind = frame['phase'], frame['scope'], frame['kind']
        if (kind not in ('error', 'skip') or frame['subtest'] or
                phase not in ('setUpModule', 'tearDownModule', 'setUpClass', 'tearDownClass') or
                frame['id'] != f'{phase} ({scope})' or self.active is not None):
            raise ValidationError('Invalid fixture event')
        key = 'owner' if phase.endswith('Module') else 'class_name'
        candidates = [leaf for leaf in self.leaves if leaf[key] == scope]
        if not candidates:
            raise ValidationError('Unknown fixture scope: ' + scope)
        self.counts['errors' if kind == 'error' else 'skipped'] += 1
        if not self.ordered:
            # A stock-backed inventory cannot prove which leaves a custom run
            # visited, even when it delegates a partial scope to a stock suite.
            self.last_setup = None
            return
        if phase.startswith('setUp'):
            frontier = self.started[-1] + 1 if self.started else 0
            repeated = self.last_setup is not None and self.last_setup[:2] == (phase, scope)
            unstarted = ([self.by_ordinal[index] for index in self.last_setup[2]] if repeated else
                         [leaf for leaf in candidates if leaf['ordinal'] not in self.started
                          and leaf['ordinal'] not in self.fixture_dispositions
                          and leaf['ordinal'] >= frontier])
            if unstarted:
                first = self.leaves.index(unstarted[0])
                block = []
                for leaf in self.leaves[first:]:
                    if leaf[key] != scope:
                        break
                    block.append(leaf)
                unstarted = block
            # Recurrent scopes have multiple fixture invocations. Without an
            # unambiguous contiguous pending scope, missing leaves stay not-run.
            if unstarted:
                positions = [self.leaves.index(leaf) for leaf in unstarted]
                if positions == list(range(positions[0], positions[-1] + 1)):
                    self.last_setup = (phase, scope, [leaf['ordinal'] for leaf in unstarted])
                    for leaf in unstarted:
                        ordinal = leaf['ordinal']
                        value = self.fixture_dispositions.setdefault(ordinal, dict(kind='fixture-skipped', events=[]))
                        value['events'].append(self.fixture_reference(frame))
                        if kind == 'error':
                            value['kind'] = 'fixture-blocked'
        else:
            self.last_setup = None

    def fixture_reference(self, frame):
        """Identify a fixture event independently of unit boundaries and unrelated callbacks."""
        occurrence = sum(event['ordinal'] is None and event['phase'] == frame['phase'] and
                         event['scope'] == frame['scope'] and event['seq'] < frame['seq']
                         for event in self.events)
        return f"{frame['phase']} ({frame['scope']})#{occurrence}"

    def dispositions(self):
        """Return each discovery leaf's completion or justified fixture disposition in order."""
        dispositions = []
        for leaf in self.leaves:
            ordinal = leaf['ordinal']
            if ordinal in self.completed:
                value = dict(kind='completed', events=self.outcomes[ordinal])
            else:
                value = self.fixture_dispositions.get(ordinal, dict(kind='not-run', events=[]))
            dispositions.append(dict(ordinal=ordinal, id=leaf['id'], **value))
        return dispositions

    def finish(self):
        """Require a complete transport and exhaustive leaf accounting at EOF."""
        if self.hello is None or self.end is None:
            raise ValidationError('Missing worker hello/end report')
        missing = [item['id'] for item in self.dispositions() if item['kind'] == 'not-run']
        if missing:
            raise ValidationError('Unexplained not-run leaves: ' + json.dumps(missing))


class FrameReader:
    """Incrementally parse bounded length-prefixed JSON without blocking reads or pickle."""

    def __init__(self, ledger):
        """Bind one unit ledger and initialize an empty partial-frame buffer."""
        self.ledger = ledger
        self.buffer = bytearray()
        self.length = None

    def feed(self, data, remaining):
        """Consume bytes and reject announced lengths exceeding the global remaining budget."""
        self.buffer.extend(data)
        while True:
            if self.length is None:
                if len(self.buffer) < 4:
                    return
                self.length = struct.unpack('!I', self.buffer[:4])[0]
                del self.buffer[:4]
                if self.length == 0 or self.length > remaining + len(self.buffer):
                    raise ValidationError('Oversized/invalid protocol frame length')
            if len(self.buffer) < self.length:
                return
            raw = bytes(self.buffer[:self.length])
            del self.buffer[:self.length]
            self.length = None
            try:
                frame = json.loads(raw.decode('utf-8'), object_pairs_hook=strict_object,
                                   parse_constant=reject_constant)
            except (ValueError, UnicodeError) as error:
                raise ValidationError('Malformed protocol JSON: ' + str(error)) from error
            if type(frame) is not dict:
                raise ValidationError('Protocol frame is not an object')
            self.ledger.accept(frame)

    def finish(self):
        """Reject partial frames and missing reports when the private protocol pipe closes."""
        if self.buffer or self.length is not None:
            raise ValidationError('Truncated protocol frame')
        self.ledger.finish()


def send_frame(descriptor, frame):
    """Write one versioned JSON frame to the private non-exec-inheritable protocol pipe."""
    data = json.dumps(frame, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(data) > OUTPUT_LIMIT:
        raise ValidationError('Worker protocol frame exceeds 16 MiB')
    packet = memoryview(struct.pack('!I', len(data)) + data)
    while packet:
        written = os.write(descriptor, packet)
        packet = packet[written:]


def process_table():
    """Read Linux process parentage and start ticks, including thread-created children."""
    table = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
            table[int(entry.name)] = (int(fields[1]), int(fields[19]), fields[0])
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            # Unrelated protected processes are not descendants of this UID.
            continue
    return table


def descendant_identities(table, parent):
    """Return stable identities transitively owned by parent in a proc snapshot."""
    parents, identities = {parent}, {}
    while True:
        added = {pid for pid, (ppid, _, _) in table.items() if ppid in parents and pid not in parents}
        if not added:
            return identities
        parents.update(added)
        identities.update({pid: table[pid][1] for pid in added})


def require_fork_context():
    """Reject unsafe fork callers or missing facilities before installing scoped state."""
    if not sys.platform.startswith('linux') or not hasattr(os, 'fork') or not hasattr(os, 'wait4'):
        raise ValidationError('Unsupported platform: Linux fork/wait4/proc/prctl required')
    if not all(hasattr(signal, name) for name in
               ('pthread_sigmask', 'sigpending', 'sigtimedwait', 'SIG_BLOCK', 'SIG_SETMASK')):
        raise ValidationError('Unsupported platform: signal mask/pending-wait facilities required')
    if threading.current_thread() is not threading.main_thread() or threading.active_count() != 1:
        raise ValidationError('Unsupported fork context: main thread with no other live threads required')
    # Python's thread registry does not necessarily know native extension threads.
    if len(list(Path('/proc/self/task').iterdir())) != 1:
        raise ValidationError('Unsupported fork context: native threads are live')
    children = descendant_identities(process_table(), os.getpid())
    if children:
        raise ValidationError('Unsupported fork context: pre-existing children ' + repr(children))


def prctl(option, argument):
    """Call Linux prctl through stdlib ctypes and surface lifecycle setup failures."""
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(option, argument, 0, 0, 0) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


class ReportStream:
    """Bound coordinator-rendered output, reserving space for an explicit incomplete-report failure."""

    def __init__(self, invocation, stream):
        """Wrap the caller's text stream without taking ownership of its descriptor."""
        self.invocation, self.stream = invocation, stream

    def write(self, text):
        """Charge UTF-8 rendered bytes before writing; overflow always invalidates validation."""
        size = len(text.encode('utf-8', errors='replace'))
        if self.invocation.rendered + size > self.invocation.limits['stdout'] - 1024:
            raise ValidationError('Rendered stdout limit exceeded; report incomplete')
        self.invocation.rendered += size
        return self.stream.write(text)

    def flush(self):
        """Flush the supplied stream before forks and at ordinary caller boundaries."""
        self.stream.flush()

    def failure(self, message):
        """Use the reserved bounded margin for a failure, never claim a truncated report complete."""
        data = (message + '\n').encode('utf-8', errors='replace')
        remaining = max(0, self.invocation.limits['stdout'] - self.invocation.rendered)
        if len(data) > remaining:
            data = b'Report incomplete: diagnostic/output limit exceeded.\n'[:remaining]
        self.invocation.rendered += len(data)
        self.stream.write(data.decode('utf-8', errors='replace'))


class Invocation:
    """Own scoped signals, subreaping, descendant identities and shared invocation budgets."""

    def __init__(self, deadline, *, output_limit=OUTPUT_LIMIT, protocol_limit=OUTPUT_LIMIT):
        """Set an absolute monotonic deadline; smaller private bounds support tiny regressions."""
        self.deadline = deadline
        self.limits = dict(stdout=output_limit, stderr=output_limit, protocol=protocol_limit)
        self.bytes = dict.fromkeys(self.limits, 0)
        self.rendered = 0
        self.owned = {}
        self.workers = []
        self.signals = {}
        self.old_subreaper = None
        self.old_signal_mask = None
        self.cleaning = False
        self.cancelled = None
        self.cleanup_errors = []
        self.cleaned = False

    def __enter__(self):
        """Verify ownership before installing subreaping and scoped interruption handlers."""
        require_fork_context()
        previous = ctypes.c_int()
        prctl(37, ctypes.byref(previous))  # PR_GET_CHILD_SUBREAPER
        self.old_subreaper = previous.value
        prctl(36, 1)  # PR_SET_CHILD_SUBREAPER
        try:
            for signum in (signal.SIGINT, signal.SIGTERM):
                self.signals[signum] = signal.getsignal(signum)
                signal.signal(signum, self.interrupt)
        except BaseException:
            self.restore()
            raise
        return self

    def interrupt(self, signum, frame):
        """Enter the common cleanup path on cancellation, without interrupting cleanup itself."""
        self.cancelled = signum
        if not self.cleaning:
            raise ValidationError('Validation interrupted by ' + signal.Signals(signum).name)

    def check(self):
        """Check cancellation and the invocation deadline between bounded operations."""
        if self.cancelled:
            raise ValidationError('Validation interrupted by ' + signal.Signals(self.cancelled).name)
        if time.monotonic() >= self.deadline:
            raise ValidationError('Validation deadline exceeded (2650-second invocation bound)')

    def observe(self):
        """Track transitive descendants and stable identities without consuming wait statuses."""
        table = process_table()
        found = descendant_identities(table, os.getpid())
        for pid, start in found.items():
            if pid in self.owned and self.owned[pid] != start:
                raise ValidationError('Owned PID identity changed: ' + str(pid))
            self.owned[pid] = start
        return table

    def charge(self, channel, size, unit):
        """Apply global read-byte bounds before retaining worker output or protocol bytes."""
        self.bytes[channel] += size
        if self.bytes[channel] > self.limits[channel]:
            raise ValidationError(f'Output limit: unit={unit} channel={channel} '
                                  f'bytes={self.bytes[channel]} limit={self.limits[channel]}')

    def emit(self, stream, text):
        """Bound final rendered text as well as raw streams, including JSON expansion."""
        if isinstance(stream, ReportStream):
            stream.write(text)
            return
        size = len(text.encode('utf-8', errors='replace'))
        if self.rendered + size > self.limits['stdout']:
            raise ValidationError('Rendered stdout limit exceeded; report incomplete')
        self.rendered += size
        stream.write(text)

    def signal_owned(self, pid, start, signum):
        """Signal only a still-matching identity, using a pidfd when Linux exposes it."""
        descriptor = None
        try:
            if hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal'):
                try:
                    descriptor = os.pidfd_open(pid)
                except OSError as error:
                    if error.errno not in (errno.ENOSYS, errno.EINVAL, errno.EPERM):
                        raise
            entry = process_table().get(pid)
            if entry is None or entry[1] != start:
                return
            if descriptor is not None:
                signal.pidfd_send_signal(descriptor, signum)
            else:
                os.kill(pid, signum)
        except ProcessLookupError:
            pass
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def cleanup(self):
        """Terminate, rediscover adopted descendants, escalate within five seconds and reap.

        Ordinary supervision waits only on known direct workers. Once aborting, all
        owned children may be reaped; no controller or pre-existing child is owned.
        Signals latch cancellation while cleanup runs so they cannot abandon owned
        processes or directories. Protection is cleared even if cleanup raises.
        """
        if self.cleaned:
            return
        self.cleaning = True
        try:
            self.cleaned = True
            started = time.monotonic()
            term_sent, kill_sent = set(), set()
            while True:
                try:
                    table = self.observe()
                    live = {pid: start for pid, start in self.owned.items()
                            if pid in table and table[pid][1] == start}
                    if not live:
                        break
                    killing = time.monotonic() - started >= 5
                    for pid, start in live.items():
                        identity = (pid, start)
                        sent = kill_sent if killing else term_sent
                        if identity not in sent:
                            self.signal_owned(pid, start, signal.SIGKILL if killing else signal.SIGTERM)
                            sent.add(identity)
                        if table[pid][0] == os.getpid():
                            try:
                                reaped, status, usage = os.wait4(pid, os.WNOHANG)
                                if reaped:
                                    for worker in self.workers:
                                        if worker.get('pid') == pid and worker['status'] is None:
                                            worker['status'], worker['usage'] = status, usage
                            except ChildProcessError:
                                pass
                    if time.monotonic() - started >= 7:
                        self.cleanup_errors.append('Unresolved owned identities: ' + repr(live))
                        break
                    time.sleep(0.02)
                except Exception as error:
                    self.cleanup_errors.append('Process cleanup failure: ' + str(error))
                    break
            for worker in self.workers:
                for descriptor in tuple(worker['fds']):
                    channel = worker.get('channels', {}).get(descriptor)
                    if channel in ('stdout', 'stderr'):
                        try:
                            while True:
                                data = os.read(descriptor, 65536)
                                if not data:
                                    break
                                self.charge(channel, len(data), worker['ordinal'])
                                worker[channel].extend(data)
                        except BlockingIOError:
                            pass
                        except (OSError, ValidationError) as error:
                            self.cleanup_errors.append('Output cleanup failure: ' + str(error))
                    try:
                        os.close(descriptor)
                    except OSError as error:
                        self.cleanup_errors.append('Pipe cleanup failure: ' + str(error))
                    worker['fds'].discard(descriptor)
                # Never remove a private directory while an owned process may still use it.
                if not any(message.startswith(('Unresolved', 'Process cleanup')) for message in self.cleanup_errors):
                    try:
                        shutil.rmtree(worker['temporary'])
                    except OSError as error:
                        self.cleanup_errors.append('Temporary cleanup failure: ' + str(error))
        finally:
            self.cleaning = False

    def restore(self):
        """Hand scoped state back with INT/TERM blocked, then restore the exact caller mask.

        Pending signals unblocked by the caller become cancellation. Caller-blocked
        signals stay pending. All restoration failures, including BaseExceptions,
        are deferred to cleanup diagnostics so no action abandons another obligation
        or replaces an earlier execution error. Failed obligations remain saved.
        """
        if self.old_subreaper is None and not self.signals and self.old_signal_mask is None:
            return
        pair = {signal.SIGINT, signal.SIGTERM}
        previous_mask = None
        self.cleaning = True
        try:
            # Block both together: a reinstated caller handler ignores cleaning.
            try:
                blocked_mask = signal.pthread_sigmask(signal.SIG_BLOCK, pair)
                if self.old_signal_mask is None:
                    self.old_signal_mask = blocked_mask
                previous_mask = self.old_signal_mask
            except BaseException as error:
                self.cleanup_errors.append(f'Signal blocking failure: {type(error).__name__}: {error}')
                return
            if self.old_subreaper is not None:
                try:
                    prctl(36, self.old_subreaper)
                except BaseException as error:
                    self.cleanup_errors.append(f'Subreaper restoration failure: {type(error).__name__}: {error}')
                else:
                    self.old_subreaper = None
            for signum, handler in tuple(self.signals.items()):
                try:
                    signal.signal(signum, handler)
                except BaseException as error:
                    self.cleanup_errors.append(f'Signal restoration failure: {type(error).__name__}: {error}')
                else:
                    del self.signals[signum]
            try:
                # Never consume caller-owned pending signals. A fixed snapshot and
                # one zero-timeout wait per standard signal bound repeated delivery.
                pending = (signal.sigpending() & pair) - previous_mask
                for signum in sorted(pending):
                    try:
                        received = signal.sigtimedwait({signum}, 0)
                        if received is not None:
                            self.interrupt(received.si_signo, None)
                    except BaseException as error:
                        self.cleanup_errors.append(f'Pending signal failure: {type(error).__name__}: {error}')
            except BaseException as error:
                self.cleanup_errors.append(f'Pending signal inspection failure: {type(error).__name__}: {error}')
        finally:
            self.cleaning = False
            # Unmask last: caller handlers may now run or raise, after every other
            # restoration was attempted and latch-only protection was cleared.
            if previous_mask is not None:
                try:
                    signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
                except BaseException as error:
                    self.cleanup_errors.append(f'Signal mask restoration failure: {type(error).__name__}: {error}')
                else:
                    self.old_signal_mask = None

    def __exit__(self, kind, error, tb):
        """Clean all owned resources on success, failure or cancellation without suppressing errors."""
        try:
            self.cleanup()
        finally:
            self.restore()
        return False


def private_temporary(root):
    """Create a short owner-private execution directory outside the candidate source tree."""
    base = Path(tempfile.gettempdir()).resolve()
    if base.is_relative_to(root.resolve()):
        raise ValidationError('Temporary base is inside protected candidate source: ' + str(base))
    # mkdtemp creates mode 0700 (further restricted by the caller's umask).
    return tempfile.mkdtemp(prefix='v-', dir=base)


def child_execute(suite, leaves, ordinal, mask, temporary, descriptors, close_fds, parent, deadline):
    """Execute inherited objects once, capturing descriptor output and emitting a private ledger."""
    stdout_fd, stderr_fd, protocol_fd = descriptors
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, signal.SIG_DFL)
        for descriptor in close_fds:
            if descriptor not in descriptors:
                os.close(descriptor)
        os.dup2(stdout_fd, 1)
        os.dup2(stderr_fd, 2)
        os.close(stdout_fd)
        os.close(stderr_fd)
        # Replace Python wrappers as well as fd 1/2; os.write and exec descendants
        # therefore use the same two bounded channels.
        sys.stdout = io.TextIOWrapper(os.fdopen(os.dup(1), 'wb', buffering=0), encoding='utf-8',
                                      errors='backslashreplace', write_through=True)
        sys.stderr = io.TextIOWrapper(os.fdopen(os.dup(2), 'wb', buffering=0), encoding='utf-8',
                                      errors='backslashreplace', write_through=True)
        sys.__stdout__, sys.__stderr__ = sys.stdout, sys.stderr
        # Keep the inherited CWI process group. A parent-death signal protects this
        # direct worker; arbitrary grandchildren still rely on CWI group supervision.
        prctl(1, signal.SIGKILL)  # PR_SET_PDEATHSIG
        if os.getppid() != parent:
            os._exit(125)
        for name in ('TMPDIR', 'TEMP', 'TMP'):
            os.environ[name] = temporary
        tempfile.tempdir = temporary
        if mask is not None:
            os.sched_setaffinity(0, mask)
            if sorted(os.sched_getaffinity(0)) != mask:
                raise ValidationError('Worker affinity verification failed')
        try:
            actual = sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else []
        except OSError:
            if mask is not None:
                raise
            actual = []
        if time.monotonic() >= deadline:
            raise ValidationError('Worker inherited expired invocation deadline')
        send = functools.partial(send_frame, protocol_fd)
        send(dict(type='hello', version=PROTOCOL_VERSION, unit=ordinal, pid=os.getpid(),
                  digest=inventory_digest([leaf['id'] for leaf in leaves]), affinity=actual))
        began = time.monotonic()
        result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2,
            resultclass=functools.partial(CoverageResult, leaves=leaves, send=send)).run(suite)
        send(dict(type='end', counters=result_counts(result), started=result.started,
                  completed=result.completed, execution_seconds=float(time.monotonic() - began)))
        sys.stdout.flush()
        sys.stderr.flush()
        os.close(protocol_fd)
        os._exit(0)
    except BaseException:
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        os._exit(126)


def launch_worker(invocation, root, suite, leaves, ordinal, mask, ordered):
    """Fork one inherited suite, transferring exactly three write ends to the child."""
    invocation.check()
    temporary = private_temporary(root)
    worker = dict(ordinal=ordinal, leaves=leaves, temporary=temporary, fds=set(),
                  stdout=bytearray(), stderr=bytearray(), status=None, usage=None, quiescent=False,
                  fork_time=time.monotonic(), ready_time=None)
    invocation.workers.append(worker)
    pipes = []
    try:
        for _ in range(3):
            pair = os.pipe2(os.O_CLOEXEC)
            pipes.append(pair)
            worker['fds'].update(pair)
        for stream in (sys.stdout, sys.stderr):
            stream.flush()
        parent = os.getpid()
        inherited = set().union(*(item['fds'] for item in invocation.workers))
        pid = os.fork()
        if pid == 0:
            child_execute(suite, leaves, ordinal, mask, temporary,
                          [write for _, write in pipes], inherited, parent, invocation.deadline)
        worker['pid'] = pid
        table = invocation.observe()
        if pid not in table:
            raise ValidationError('Worker vanished before identity observation')
        worker['identity'] = table[pid][1]
        ledger = EventLedger(ordinal, pid, leaves, mask, ordered)
        worker['ledger'], worker['reader'] = ledger, FrameReader(ledger)
        worker['channels'] = {}
        for (read, write), channel in zip(pipes, ('stdout', 'stderr', 'protocol')):
            os.close(write)
            worker['fds'].remove(write)
            os.set_blocking(read, False)
            worker['channels'][read] = channel
        return worker
    except BaseException:
        # Invocation cleanup owns even partially launched workers and all pipe ends.
        raise


def supervise_wave(invocation, workers):
    """Drain all wave pipes and reap known workers before any later admission."""
    with selectors.DefaultSelector() as selector:
        for worker in workers:
            for descriptor, channel in worker['channels'].items():
                selector.register(descriptor, selectors.EVENT_READ, (worker, channel))
        while selector.get_map() or any(worker['status'] is None for worker in workers):
            invocation.check()
            table = invocation.observe()
            direct = {worker['pid'] for worker in workers if worker['status'] is None}
            adopted = [pid for pid, start in invocation.owned.items()
                       if pid in table and table[pid][1] == start and table[pid][0] == os.getpid() and pid not in direct]
            if adopted:
                raise ValidationError('Surviving/adopted test descendants: ' + repr(adopted))
            for worker in workers:
                if worker['status'] is None:
                    pid, status, usage = os.wait4(worker['pid'], os.WNOHANG)
                    if pid:
                        worker['status'], worker['usage'] = status, usage
                        if status != 0:
                            raise ValidationError(f"Worker {worker['ordinal']} exited abnormally: status={status}")
                        # A worker may exit between the proc snapshot and wait4. The
                        # next snapshot must detect orphans before waiting for pipe EOF.
            for key, _ in selector.select(timeout=min(0.05, max(0, invocation.deadline - time.monotonic()))):
                worker, channel = key.data
                try:
                    data = os.read(key.fd, 65536)
                except BlockingIOError:
                    continue
                if data:
                    invocation.charge(channel, len(data), worker['ordinal'])
                    if channel == 'protocol':
                        worker['reader'].feed(data, invocation.limits['protocol'] - invocation.bytes['protocol'])
                        if worker['ledger'].hello is not None and worker['ready_time'] is None:
                            worker['ready_time'] = time.monotonic()
                    else:
                        worker[channel].extend(data)
                else:
                    selector.unregister(key.fd)
                    os.close(key.fd)
                    worker['fds'].remove(key.fd)
                    if channel == 'protocol':
                        worker['reader'].finish()
        # Recheck after all exits, even if no orphan retains a pipe.
        table = invocation.observe()
        live = {pid: start for pid, start in invocation.owned.items()
                if pid in table and table[pid][1] == start}
        if live:
            raise ValidationError('Surviving test descendants after wave: ' + repr(live))
        for worker in workers:
            worker['quiescent'] = True


def report_workers(invocation, stream, leaves):
    """Consolidate retained output and full inventories in assigned discovery order."""
    counts = dict.fromkeys(COUNT_NAMES, 0)
    started, completed, dispositions, fixtures = [], [], [], []
    for worker in invocation.workers:
        ordinal = worker['ordinal']
        for channel in ('stdout', 'stderr'):
            data = worker[channel]
            if data:
                invocation.emit(stream, f'Unit {ordinal} {channel}:\n')
                invocation.emit(stream, data.decode('utf-8', errors='backslashreplace'))
                if not data.endswith(b'\n'):
                    invocation.emit(stream, '\n')
        ledger = worker.get('ledger')
        if ledger is None:
            continue
        for key, value in ledger.counts.items():
            counts[key] += value
        execution_started = [ledger.by_ordinal[index]['id'] for index in ledger.started]
        execution_completed = [ledger.by_ordinal[index]['id'] for index in ledger.completed]
        started.extend(execution_started)
        completed.extend(execution_completed)
        invocation.emit(stream, 'Execution order: ' + json.dumps(dict(
            unit=ordinal, started=execution_started, completed=execution_completed), sort_keys=True) + '\n')
        dispositions.extend(ledger.dispositions())
        fixtures.extend(dict(unit=ordinal, **frame) for frame in ledger.events if frame['ordinal'] is None)
        for event in ledger.events:
            invocation.emit(stream, 'Result event: ' + json.dumps(dict(unit=ordinal, **event), sort_keys=True) + '\n')
        ready = worker['ready_time']
        measurement = dict(unit=ordinal, digest=ledger.digest,
                           fork_to_ready_seconds=None if ready is None else ready - worker['fork_time'],
                           execution_seconds=ledger.end['execution_seconds'] if ledger.end else None,
                           affinity=ledger.hello['affinity'] if ledger.hello else None)
        usage = worker['usage']
        if usage:
            measurement.update(user_seconds=usage.ru_utime, system_seconds=usage.ru_stime,
                               max_rss_kib=usage.ru_maxrss)
        invocation.emit(stream, 'Unit measurement: ' + json.dumps(measurement, sort_keys=True) + '\n')
    reported = {item['ordinal'] for item in dispositions}
    dispositions.extend(dict(ordinal=leaf['ordinal'], id=leaf['id'], kind='not-run', events=[])
                        for leaf in leaves if leaf['ordinal'] not in reported)
    dispositions.sort(key=lambda item: item['ordinal'])
    discovered = [leaf['id'] for leaf in leaves]
    accounted = [item['id'] for item in dispositions if item['kind'] != 'not-run']
    # Final inventories use discovery order for independent mode comparison;
    # actual callback order remains in unit execution records and the event ledger.
    started_set, completed_set = set(started), set(completed)
    started = [leaf['id'] for leaf in leaves if leaf['id'] in started_set]
    completed = [leaf['id'] for leaf in leaves if leaf['id'] in completed_set]
    for name, ids in (('discovered', discovered), ('started', started), ('completed', completed), ('accounted', accounted)):
        invocation.emit(stream, f'Inventory {name}: sha256={inventory_digest(ids)} ids=' +
                        json.dumps(ids, ensure_ascii=True, separators=(',', ':')) + '\n')
    for disposition in dispositions:
        invocation.emit(stream, 'Disposition: ' + json.dumps(disposition, sort_keys=True) + '\n')
    for event in fixtures:
        ledger = invocation.workers[event['unit']]['ledger']
        reference = ledger.fixture_reference(event)
        affected = [item['id'] for item in dispositions if item['kind'].startswith('fixture-') and
                    item['ordinal'] in invocation.workers[event['unit']]['ledger'].by_ordinal and
                    reference in item['events']]
        invocation.emit(stream, 'Fixture event: ' + json.dumps(dict(event, reference=reference, affected_ids=affected), sort_keys=True) + '\n')
    summary = {kind: sum(item['kind'] == kind for item in dispositions)
               for kind in ('fixture-skipped', 'fixture-blocked', 'not-run')}
    invocation.emit(stream, f'Fixture accounting: events={len(fixtures)} fixture-skipped={summary["fixture-skipped"]} '
                    f'fixture-blocked={summary["fixture-blocked"]} unexplained-not-run={summary["not-run"]}\n')
    invocation.emit(stream, f'Counts: discovered={len(leaves)} ' +
                    ' '.join(f'{name}={counts[name]}' for name in COUNT_NAMES) + '\n')
    return bool(leaves and counts['successful'] and not summary['not-run'] and
                not any(counts[name] for name in ('failures', 'errors', 'unexpected_successes')))


def execute_suite(root, stream, suite, leaves, units, reasons, invocation, sequential):
    """Execute and report the discovered suite, failing on cleanup or finalization faults.

    Late cancellation/deadline failures preserve worker evidence and any earlier
    execution failure; completed callbacks remain truthful even on a failed run.
    """
    # Unsafe/dependent layouts have only one eligible exclusive unit. Explicit
    # sequential mode still reports the ordinary independence formula for comparison.
    pending = [leaves] if reasons and leaves else list(units)
    wave = 0
    if sequential:
        reasons = ['explicit --sequential', *reasons]
    failure = None
    try:
        while pending:
            invocation.check()
            sample = sample_resources()
            available, remaining = sample['A'], len(pending)
            allocation = concurrency_budget(available, remaining)
            fallback = list(reasons)
            if sample['allowed'] is None:
                fallback.append('affinity unavailable')
            if allocation == 0:
                fallback.append('C=0')
            wave += 1
            mask = sample['allowed'][:allocation] if not fallback else None
            admitted = 1 if fallback else min(len(pending), 2 * allocation)
            invocation.emit(stream, f'Wave {wave}: A={available} T={remaining} C={allocation} '
                            f'concurrency={admitted} mask={mask} fallback={json.dumps(fallback)}\n')
            invocation.emit(stream, 'Resources: ' + json.dumps(sample, sort_keys=True) + '\n')
            stream.flush()
            workers = []
            if fallback:
                remaining_leaves = [leaf for unit in pending for leaf in unit]
                # The untouched original suite is essential for hooks/custom behavior.
                execution = suite if wave == 1 else unittest.TestSuite(
                    leaf['test'] for leaf in remaining_leaves)
                workers.append(launch_worker(invocation, root, execution, remaining_leaves,
                                             len(invocation.workers), None, not any(
                                                 reason.startswith(('custom suite:', 'custom case execution:'))
                                                 for reason in reasons)))
                pending.clear()
            else:
                for unit in pending[:admitted]:
                    workers.append(launch_worker(invocation, root, unittest.TestSuite(leaf['test'] for leaf in unit),
                                                 unit, len(invocation.workers), mask, True))
                del pending[:admitted]
            supervise_wave(invocation, workers)
    except BaseException as error:
        failure = f'{type(error).__name__}: {error}'
    finally:
        invocation.cleanup()
    finalization_failure = None
    try:
        invocation.check()
    except ValidationError as error:
        finalization_failure = str(error)
    if failure:
        stream.failure('Execution failure: ' + failure)
        uncertain = [leaf['id'] for worker in invocation.workers for leaf in worker['leaves']
                     if not worker['quiescent'] or worker.get('status') != 0 or
                     not worker.get('ledger') or not worker['ledger'].end]
        invocation.emit(stream, 'Uncertain-effect IDs: ' + json.dumps(uncertain) + '\n')
    if finalization_failure:
        stream.failure('Finalization failure: ' + finalization_failure)
    for worker in invocation.workers:
        if worker['status'] is not None and worker['status'] != 0:
            stream.failure(f"Worker {worker['ordinal']} exited abnormally: status={worker['status']}")
    for error in invocation.cleanup_errors:
        stream.failure('Cleanup failure: ' + error)
    passing = report_workers(invocation, stream, leaves)
    try:
        invocation.check()
    except ValidationError as error:
        finalization_failure = str(error)
        stream.failure('Finalization failure: ' + finalization_failure)
    return passing and failure is None and finalization_failure is None and not invocation.cleanup_errors


def _run_suite(root, stream, sequential, invocation):
    """Discover exactly once, plan actual objects and execute them under the caller's lifecycle."""
    implementation = root / 'implementation'
    tests = implementation / 'tests'
    if not tests.is_dir() or not (tests / '__init__.py').is_file():
        print(f'Missing test suite or __init__.py: {tests}; tests did not run.', file=stream)
        return False
    began = time.monotonic()
    loader = DiscoveryLoader()
    try:
        suite = loader.discover(str(tests), pattern='test_*.py', top_level_dir=str(implementation))
    except Exception as error:
        print(f'Discovery failure: {error}; tests did not run.', file=stream)
        traceback.print_exc(file=stream)
        return False
    invocation.check()
    for error in loader.errors:
        print(f'Discovery error: {error}', file=stream)
    # Hooks are never replayed. Any thread/child they leave behind prevents a safe fork.
    invocation.observe()
    require_fork_context()
    leaves, units, reasons = plan_suite(suite, root, loader.hooks)
    print(f'Discovery/planning measurement: seconds={time.monotonic() - began:.6f}', file=stream)
    passed = execute_suite(root, stream, suite, leaves, units, reasons, invocation, sequential)
    return passed and not loader.errors


def run_suite(root, stream, *, sequential=False):
    """Run exhaustive discovery and supervised execution; return true only for positive coverage.

    Call from a fresh single-threaded Linux process with no existing children.
    Explicit sequential mode preserves the original discovered suite intact.
    Cleanup, report flushing and scoped restoration must finish without cancellation
    or deadline expiry before a true result is returned; the caller owns stream.
    """
    sys.dont_write_bytecode = True
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    invocation = Invocation(time.monotonic() + INVOCATION_SECONDS)
    stream = ReportStream(invocation, stream)
    passed = False
    try:
        with invocation:
            try:
                passed = _run_suite(Path(root).resolve(), stream, sequential, invocation)
            finally:
                invocation.cleanup()
            stream.flush()
            invocation.check()
    except BaseException as error:
        passed = False
        stream.failure(f'Operational validation error: {error}')
    try:
        # Cleanup/restoration defer signals; check even after an earlier exception
        # so a second fault during restoration is reported beside the primary one.
        invocation.check()
    except ValidationError as error:
        passed = False
        stream.failure(f'Finalization failure: {error}')
    for error in invocation.cleanup_errors:
        stream.failure(f'Cleanup failure: {error}')
    return passed and not invocation.cleanup_errors


def run_validation(root, stream, *, sequential=False):
    """Validate an explicit candidate root, returning an integer status with scoped supervision.

    The 2650-second deadline includes layout, discovery, cleanup, reporting, flushing
    and scoped restoration. The caller retains ownership of the report stream.
    Use a fresh single-threaded Linux process without pre-existing children; imports
    of this module alone have no validation, signal or process side effects.
    """
    began = time.monotonic()
    usage_before = resource.getrusage(resource.RUSAGE_SELF) if resource is not None else None
    invocation = Invocation(began + INVOCATION_SECONDS)
    stream = ReportStream(invocation, stream)
    status = 1
    try:
        with invocation:
            try:
                print(f'Python/platform: {sys.version.split()[0]} {platform.platform()}', file=stream)
                print('Bounds: invocation=2650s TERM-grace<=5s stdout=16MiB stderr=16MiB '
                      'protocol=16MiB rendered-stdout=16MiB', file=stream)
                status = _validate_root(root, stream, sequential, invocation)
            except BaseException as error:
                status = 1
                stream.failure(f'Operational validation error: {error}')
            finally:
                invocation.cleanup()
            usage_after = resource.getrusage(resource.RUSAGE_SELF) if resource is not None else None
            if usage_after is not None:
                print('Coordinator measurement: ' + json.dumps(dict(
                    user_seconds=usage_after.ru_utime - usage_before.ru_utime,
                    system_seconds=usage_after.ru_stime - usage_before.ru_stime,
                    max_rss_kib=usage_after.ru_maxrss), sort_keys=True), file=stream)
            print(f'Total wall measurement: seconds={time.monotonic() - began:.6f}', file=stream)
            stream.flush()
            invocation.check()
    except BaseException as error:
        status = 1
        stream.failure(f'Operational validation error: {error}')
    try:
        # A result remains provisional through restoration, even when an earlier
        # exception interrupted normal reporting or the pre-restoration check.
        invocation.check()
    except ValidationError as error:
        status = 1
        stream.failure(f'Finalization failure: {error}')
    for error in invocation.cleanup_errors:
        stream.failure(f'Cleanup failure: {error}')
    return 1 if invocation.cleanup_errors else status


if __name__ == '__main__':
    raise SystemExit(main())
