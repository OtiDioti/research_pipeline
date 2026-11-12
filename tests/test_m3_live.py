"""Opt-in bounded M3 science: real Codex roles, production coordination/isolation."""
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.parse import quote

from tests import use_checkout

use_checkout()
from research_pipeline import codex, isolation, verification, workspace


QUESTIONS = """# Near-boundary approximation and independent challenge
Investigate I(a) = integral from 0 to 2*pi of 1/(a-cos(theta)) dtheta, a>1.
Derive the leading near-boundary approximation and its next correction separately,
assess a candidate ONE PERCENT validity regime for the leading approximation,
and distinguish approximation error, discretization error and floating-point uncertainty.
Treat broad applicability as a hypothesis, never assert an unsupported bound as fact.

This is a SMALL bounded demonstration. Prioritize the dependent calculation, safe
handoff, integration and independent challenge over optional surveys, plots or extra
precision programs. Keep notes and packets concise and self-contained. One useful
convergence analysis and one numerical sensitivity/roundoff check suffice for the
dependent task; disclose any remaining uncertainty. Do not spend the session filling
the time with increasingly expensive grids. Keep handoffs current from the first
calculation; when saving is requested, acknowledge the existing useful work promptly.
Combine the checkpoint --check with each scientific shell command where practical,
except for the PRIMARY's standalone parent.py --advance call described below.
After the reserved successor calculation and its compact uncertainty assessment,
deliver RESULT.md promptly so primary can integrate and start independent checking.

PRIMARY: delegate exactly ONE dependent quadrature/convergence study, with a scientific
benefit: you need independently computed numerical evidence while you derive the
analytical approximation and its correction. Use the primary helper --delegate. The
assignment must carry the following staged calculation/interface requirements.

DELEGATED RESEARCHER (only): author standard-library compute.py in YOUR assigned
workspace, accepting --a (parameter list), --n (grid list), --output (JSON path).
Save {"rows": [{"a": ..., "n": ..., "estimate": ...}, ...]} with actual periodic
trapezoidal sums, never an analytical formula substituted for numerical quadrature.
Before automatic rollover calculate a=1.01, n=16,32,64,128,256,512,1024 in baseline.json.
Preserve its bytes and compute.py unchanged on continuation. Continue useful convergence/error/sensitivity
analysis, keeping an intelligible handoff saved EARLY. Reserve a=1.001 for your
AUTOMATIC SUCCESSOR: its concrete Next action must first use the saved baseline and
error analysis to predict how convergence and numerical uncertainty should change
at a=1.001. Save that independent prediction in a short Markdown note BEFORE running
the reserved calculation; do not change the baseline or repeat its computation.
Then use saved compute.py to calculate
n=16,32,64,128,256,512,1024,2048,4096 in successor.json and extend the uncertainty
assessment. Do not do this reserved calculation in the first context. Do not finish
before the requested automatic handoff while meaningful numerical analysis remains.
Check the checkpoint helper after commands; acknowledge promptly when asked. The
fresh successor continues this same task, writes RESULT.md with links to code/data
and limitations, and finishes. Do not repeat the saved baseline on continuation.

PRIMARY: while that task runs and rolls over, continue substantive analytical and
computational work. Author work/parent.py accepting --a (parameter list) and --output, save work/parent.json
as {"rows": [{"a": ..., "approximation": ..., "reference": ..., "relative_error": ...}]}
for an expanding parameter study of YOUR derived approximation. Use distinct a>1
parameters and actual calculations; relative_error is an absolute fraction, not a
percentage, against your accurately derived reference. Save work/PARENT.md with the evolving
error argument. Extend this study during the child handoff and successor calculation,
so the saved rows and derivation show useful parent progress across the transition.
No sleep/heartbeat/poll loop as a substitute for science. Consult sources and report
access honestly. Save required plan, literature, status, report and handoff drafts.
Stage the parent study in small useful expansions, retaining new parameters for the
observed child saving/continuation interval; do not exhaust all extensions beforehand.
Use concurrent task status printed by --check (or the full --tasks summary).
Give YOUR parent.py an --advance mode early: read status, then immediately
execute a reserved parent expansion if saving_reason=rollover or the child's
activation_id has changed. This mode must use the SAME calculation function as
your --a/--output mode and propagate calculation failures. Invoke it as a
STANDALONE exec_command containing ONLY `python3 /project/work/parent.py --advance`.
No checkpoint chain, code authoring, cd, redirection, or subsequent command in that
same exec_command: its native exit status must belong to the calculation itself.
Use separate exec_command calls for checkpoint checks and note writing. This mode
queries status and calculates within ONE process invocation; do not spend another
model turn composing a report before reacting.
No waiting/poll loop: interleave these calls with short useful scientific work. As
rollover_in_seconds approaches zero, avoid long note-writing batches. Save the initial
child activation ID so a missed brief saving notice can still be recognized from its
successor. Update PARENT.md with the actual observations after the calculation.
Do this before reading the child's published handoff. Keep another expansion for its
changed activation_id if useful. The child's signal does not request your own handoff.
Once the child delivers, prioritize integration and verification over optional analyses.

After the child delivers, integrate its numerical findings and uncertainties into
the parent approximation analysis. Request exactly ONE separate independent verifier
using --verify, with scientific parent primary. The packet's Claim and scope must
include TWO distinct subjects: your derived near-boundary validity regime, and the
exploratory hypothesis that the leading approximation's one-percent accuracy extends
across the parameter study, including a=1.2. Submit the latter as a hypothesis to test,
never an established bound, even if your own calculations already argue against it.
Supply assumptions, sources and reproducible artifacts. Ask for independent reasoning
and independently authored checks of both subjects; do not restrict the examination
to confirming your narrowed theorem or exclude broader applicability from its scope.
Do not manufacture a false claim or prescribe the verdict. The packet must EXPLICITLY
link every local Markdown dependency recursively (including code/data linked from
notes), within the existing packet limits. A short self-contained claim note can
avoid irrelevant links.
Never supply conversations. Include these verification interface requirements:

VERIFIER (only): independently author check.py in YOUR workspace, accepting --output
and writing {"rows": [{"a": ..., "reference": ..., "approximation": ...,
"relative_error": ...}]} including a=1.2 and near-boundary cases. Use your own
reconstruction, preferably another method; relative_error is an absolute fraction,
not a percentage. Execute it and explain whether the stress
observations challenge the proposed approximation/regime or an unsupported extension.
Address BOTH the scoped near-boundary result and the submitted broader applicability
hypothesis. If your evidence rejects that hypothesis, record a substantive objection
to that extension, distinguishing it from any theorem you confirm. An objection need
not allege that the researcher asserted a false theorem: an independently refuted
exploratory hypothesis also needs a documented response and scope decision. Do not
invent disagreement if the evidence supports both subjects; report your actual verdict.
Write substantive CHECK.md linking the independent check code/data and frozen evidence.
In BOTH CHECK.md and REEXAMINATION.md include a ## Numerical observations section
directly linking ALL consequential independent JSON observation tables for that round.
These explicitly identified tables must use the row interface above. Link ancillary
integrity/provenance records and check code elsewhere; put only the numerical table
links in that section. Ancillary records cannot replace numerical observations.
A substantive objection should identify the scientific issue, numerical observations,
and a justified targeted test if useful. Finish this examination rather than waiting.
On re-examination preserve ALL initial reports and linked code/data/notes; use NEW
paths for any revised checks. Respond independently to the accepted response/version,
perform a justified targeted test, saving NEW JSON with the same row interface and
the stress case a=1.2, and link its code/data in REEXAMINATION.md. You may rerun
unchanged check.py with a new output path or author a revised check. Finish. Remaining
opposing arguments are disputed after this finite exchange; do not force consensus.
Run each numerical check as a direct `python3 script.py --output data.json` command
from your workspace (extra parameter options are allowed), retaining code/data links.
Use a standalone call, or put the checkpoint && calculation chain last in its shell event.

PRIMARY: read the independent check. If challenged, write one scientific response
with correction, qualification, opposing argument or a justified targeted test; submit
--respond with --response. Include every local dependency explicitly. Read the final
check, preserve unresolved arguments, and finish. Do not create extra verifiers or
exchange rounds to obtain agreement. Synthesis must link the delegated RESULT.md,
CHECK.md, accepted frozen response packet and REEXAMINATION.md, and explain scope,
assumptions, uncertainty, objection, superseded conclusions and the final checked or
disputed outcome, including the a=1.2 numerical observation. Use relative canonical
Markdown links in outputs/REPORT.md. Do not finish while tasks are unfinished.
"""


def parent_overlap(progress, milestones):
    """Require new science between observed saving and successor calculation."""
    start = milestones["saving"]["elapsed"]
    end = milestones["continued_calculation"]["elapsed"]
    observations = [p for p in progress if start <= p["elapsed"] <= end]
    if len(observations) < 2:
        raise AssertionError("Missing substantive parent progress during child transition")
    before, after = observations[0], observations[-1]
    native = before["native_session_id"]
    if not native or any(p["native_session_id"] != native for p in observations):
        raise AssertionError("Parent native session changed during transition")
    prior_rows = {r["a"]: r for r in before["rows"]}
    current_rows = {r["a"]: r for r in after["rows"]}
    if not current_rows.keys() - prior_rows.keys():
        raise AssertionError("Parent did not extend its parameter study during child rollover")
    if any(current_rows.get(a) != row for a, row in prior_rows.items()):
        raise AssertionError("Parent changed prior numerical observations during transition")
    prior_commands = len(before["commands"])
    if after["commands"][:prior_commands] != before["commands"]:
        raise AssertionError("Parent execution history changed during transition")
    # The standalone calculation's native status belongs to that invocation. Compound
    # shells can hide an earlier failure behind a successful later statement;
    # do not infer execution by parsing their source or documentation.
    if not any(primary_calculation(command)
               for command in after["commands"][prior_commands:]):
        raise AssertionError("No new parent calculation event during transition")
    return before, after


def primary_calculation(command):
    """Require standalone execution of the same program we reproduce in isolation."""
    try:
        args = shlex.split(command)
        if args and Path(args[0]).name in ("bash", "sh"):
            if len(args) != 3 or args[1] not in ("-c", "-lc"):
                return False
            command = args[2]
            args = shlex.split(command)
    except ValueError:
        return False
    # Exact argv recognition needs no shell grammar. Additional statements,
    # redirection, expansion, authoring and unrelated Python programs fail.
    return (len(args) == 3
            and args[0] in ("python", "python3", "/usr/bin/python", "/usr/bin/python3")
            and args[1] in ("parent.py", "./parent.py", "/project/work/parent.py")
            and args[2] == "--advance")


def successful_commands(events, needle=""):
    return [e["item"]["command"] for e in events
            if e.get("type") == "item.completed"
            and e.get("item", {}).get("type") == "command_execution"
            and e["item"].get("exit_code") == 0
            and needle in e["item"].get("command", "")]


def record_parent_progress(progress, *, elapsed, native_session_id, child_activation,
                           data, derivation, events):
    """Keep immutable timed snapshots of numerical and successful-call changes."""
    try:
        rows = json.loads(data)["rows"]
    except ValueError:
        return  # The calculation may currently be writing the output file.
    signature = hashlib.sha256(data).hexdigest()
    commands = successful_commands(events)
    if rows and (not progress or progress[-1]["sha256"] != signature
                 or progress[-1]["commands"] != commands):
        progress.append({"elapsed": elapsed, "native_session_id": native_session_id,
                         "child_activation": child_activation, "sha256": signature,
                         "rows": rows, "derivation": derivation[:3500], "commands": commands})


def reproduction_driver(invocations):
    """Run each saved program from its original task workspace inside isolation."""
    return "import subprocess; " + "; ".join(
        f"subprocess.run({item['argv']!r}, cwd={item['cwd']!r}, check=True, timeout=25)"
        for item in invocations)


def numerical_evidence(project, independent, artifacts, report, text):
    """Select explicit numerical roles from an accepted report's artifact links."""
    try:
        section = verification.sections(text, ("Numerical observations",))["Numerical observations"]
    except workspace.InputError as exc:
        raise AssertionError("Missing independent numerical evidence section") from exc
    selected = {}
    for target in verification.LINK.findall(section):
        rel = verification.link_path(project, report, target)
        if (rel is None or not rel.startswith(independent + "/") or "/inputs/" in rel
                or not rel.endswith(".json") or rel not in artifacts):
            raise AssertionError(f"Invalid independent numerical evidence link: {target}")
        selected[rel] = artifacts[rel]
    if not selected:
        raise AssertionError("Missing independent numerical observation tables")
    return selected


def independent_observations(project, independent, artifacts, read):
    """Validate explicitly selected tables; ancillary JSON has no numerical role.

    Accepted reports, all linked artifacts and frozen inputs are separately checked
    by verification.check_unchanged. Optional audit assertions are not endorsements.
    """
    observations, seen = {}, {}
    for rel, digest in artifacts.items():
        if (not rel.startswith(independent + "/") or "/inputs/" in rel
                or not rel.endswith(".json")):
            raise AssertionError(f"Invalid independent numerical evidence: {rel}")
        if workspace.file_digest(workspace.safe_path(project, rel)) != digest:
            raise AssertionError(f"Accepted independent numerical evidence changed: {rel}")
        try:
            data = json.loads(read(rel))
        except json.JSONDecodeError as exc:
            raise AssertionError(f"Malformed independent numerical table: {rel}") from exc
        if not isinstance(data, dict) or "rows" not in data:
            raise AssertionError(f"Missing independent observation rows: {rel}")
        rows = data["rows"]
        if not isinstance(rows, list) or not rows:
            raise AssertionError(f"Missing independent observations: {rel}")
        parameters = set()
        for row in rows:
            fields = ("a", "reference", "approximation", "relative_error")
            if (not isinstance(row, dict) or any(
                    type(row.get(k)) not in (int, float) or not math.isfinite(row[k])
                    for k in fields)):
                raise AssertionError(f"Malformed independent observation: {rel}")
            a = row["a"]
            if a <= 1 or a in parameters:
                raise AssertionError(f"Invalid or duplicate independent parameter: {rel}")
            parameters.add(a)
            reference = 2 * math.pi / math.sqrt((a - 1) * (a + 1))
            approximation = 2 * math.pi / math.sqrt(2 * (a - 1))
            error = abs(row["approximation"] / row["reference"] - 1) if row["reference"] > 0 else math.inf
            if (not math.isclose(row["reference"], reference, rel_tol=1e-8)
                    or not math.isclose(row["approximation"], approximation, rel_tol=1e-8)
                    or not math.isclose(row["relative_error"], error, rel_tol=1e-8, abs_tol=1e-8)):
                raise AssertionError(f"Inconsistent independent observation: {rel}: {a}")
            if a in seen and any(not math.isclose(row[k], seen[a][k], rel_tol=1e-8, abs_tol=1e-10)
                                 for k in fields[1:]):
                raise AssertionError(f"Conflicting independent observations: {a}")
            seen[a] = row
        observations[rel] = rows
    if not any(1 < a < 1.0402 for a in seen):
        raise AssertionError("Independent near-boundary observations absent")
    stress = [r for a, r in seen.items() if math.isclose(a, 1.2, rel_tol=0, abs_tol=1e-12)]
    if not stress or any(r["relative_error"] <= .01 for r in stress):
        raise AssertionError("Independent stress observation/challenge absent")
    return observations


def direct_python_commands(command):
    """Recover calls proven to run by a successful simple-command shell event.

    This is deliberately not a shell parser: control flow, expansion, pipelines,
    multiline quotes and other unsupported syntax invalidate the entire event.
    """
    if command.split() and Path(command.split()[0]).name in ("bash", "sh"):
        try:
            outer = shlex.split(command)
        except ValueError:
            return []
        if len(outer) != 3 or outer[1] not in ("-lc", "-c"):
            return []
        command = outer[2]
    # Bracketed/redacted paths are accepted for opaque utility arguments, never
    # for Python invocations whose exact arguments establish provenance.
    word = r"""(?:[\w./:=,+\[\]-]+|'[\w./:=,+\[\] -]*'|"[\w./:=,+\[\] -]*")"""
    simple = rf"{word}(?:[ \t]+{word})*"
    chain = re.compile(rf"{simple}(?:[ \t]*&&[ \t]*{simple})*")
    heredoc = re.compile(
        rf"(?P<prefix>(?:{simple}[ \t]*&&[ \t]*)*)"
        rf"(?P<writer>cat|(?:[\w./-]*/)?python3?[ \t]+-)[ \t]+"
        rf"(?:>[ \t]*{word}[ \t]+)?<<(?P<tabs>-?)[ \t]*"
        r"""(?P<quote>['"]?)(?P<end>[A-Za-z_][A-Za-z0-9_]*)(?P=quote)""")
    lines = iter(command.split("\n"))
    programs = ("python", "python3", "cat", "mkdir", "sha256sum")
    calls = []
    final_conditional = []
    for line in lines:
        line = line.strip(" \t")
        if not line or line.startswith("#"):
            continue
        # Only the final statement's status is known. A later statement (even
        # an opaque heredoc writer) can mask a failed earlier && prerequisite.
        final_conditional = []
        header = heredoc.fullmatch(line)
        statement = line
        if header:
            # Strip only the opaque writer redirection/body. Its executable
            # prefix goes through exactly the same validation as every chain.
            statement = header["prefix"] + header["writer"]
            for body in lines:
                if (body.lstrip("\t") if header["tabs"] else body) == header["end"]:
                    break
            else:
                return []
        if not chain.fullmatch(statement):
            return []
        # Full matching above excludes quoted operators and incomplete commands
        # before splitting; heredoc contents never reach this branch.
        parts = statement.split("&&")
        for position, part in enumerate(parts):
            args = shlex.split(part)
            program = Path(args[0]).name
            if program not in programs:
                return []
            if program in ("python", "python3"):
                if header and position == len(parts) - 1 and args[1:] == ["-"]:
                    continue  # Opaque stdin authoring; never a recorded calculation.
                if (len(args) < 2 or not args[1].endswith(".py")
                        or any("[" in arg or "]" in arg for arg in args)):
                    return []
                if header:
                    continue  # Writer headers never supply calculation calls.
                if position == 0:
                    calls.append(args)  # Unconditional in this supported grammar.
                else:
                    final_conditional.append(args)
    # A successful final && chain ran every member; earlier chains may skip
    # conditional members, so those cannot establish execution provenance.
    return calls + final_conditional


def observation_invocations(project, independent, artifacts, observations, commands):
    """Recover direct Python CLI calls, never replay an agent's shell program."""
    calls = {rel: [] for rel in observations}
    for command in commands:
        for args in direct_python_commands(command):
            if len(args) < 4 or args.count("--output") != 1:
                continue
            output_index = args.index("--output") + 1
            if output_index >= len(args):
                continue
            anchor = independent + "/ASSIGNMENT.md"
            script = verification.link_path(project, anchor, args[1])
            output = verification.link_path(project, anchor, args[output_index])
            if output not in calls:
                continue
            if script not in artifacts or not script.startswith(independent + "/") or "/inputs/" in script:
                raise AssertionError(f"Unlinked independent program for {output}")
            argv = ["/usr/bin/python3", "/project/" + script, *args[2:]]
            # Index stays the same after normalizing interpreter/script.
            candidate = {"argv": argv, "output_index": output_index,
                         "cwd": "/project/" + independent}
            if candidate not in calls[output]:
                calls[output].append(candidate)
    result = {}
    for rel, candidates in calls.items():
        if len(candidates) != 1:
            raise AssertionError(f"Missing or ambiguous executed independent calculation: {rel}")
        result[rel] = candidates[0]
    return result


def check_synthesis(project, report, result, record):
    """Check linked outcomes; scientific prose need not use a fixed vocabulary."""
    for rel in (result, record["initial_check"], record["response"]["packet"], record["final_check"]):
        if not any(verification.link_path(project, "outputs/REPORT.md", target) == rel
                   for target in verification.LINK.findall(report)):
            raise AssertionError(f"Synthesis missing {rel}")
    if record["disposition"] not in report.lower():
        raise AssertionError(f"Synthesis missing {record['disposition']}")
    if not re.search(r"1\.2\b", report):
        raise AssertionError("Synthesis must address the observed stress case a=1.2")


@unittest.skipUnless(os.environ.get("RESEARCH_PIPELINE_M3_LIVE") == "1", "historical paid gate disabled")
class LiveM3Acceptance(unittest.TestCase):
    def test_legacy_gate_is_explicitly_rejected(self):
        self.fail("The timed M3 harness is superseded. Do not repeat accepted science; use tests.test_v0_l1_native for L1 and the future V0-L6 integrated lifecycle harness.")
