"""Small file-based tool convention; execution is namespace-local, never a host CLI.

Validation is evidence about declared checks and intended use, not an endorsement
of scientific correctness. This module also runs standalone in the research service.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
import uuid


class ToolError(ValueError):
    pass


RECORD = "VALIDATION.md"
MARKER = "<!-- research-tool-record -->\n"
END = "\n<!-- /research-tool-record -->"
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}")


def relative(value):
    if not isinstance(value, str) or not value or "\0" in value:
        raise ToolError("Expected a nonempty relative path")
    path = Path(value)
    if path.is_absolute() or not path.parts or any(p.startswith(".") for p in path.parts):
        raise ToolError(f"Unsafe or private relative path: {value}")
    return path


def safe(root, rel, *, file=False):
    path = Path(root) / relative(str(rel))
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ToolError(f"Symlinked tool path: {path}")
    if path.exists():
        mode = path.stat().st_mode
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ToolError(f"Special tool path: {path}")
    if file and not path.is_file():
        raise ToolError(f"Missing ordinary tool file: {path}")
    return path


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if before.st_size > 64 * 1024 * 1024:
            raise ToolError(f"Tool file exceeds the runtime's 64 MiB per-file limit: {path}")
        for block in iter(lambda: stream.read(65536), b""):
            h.update(block)
        after = os.fstat(stream.fileno())
    signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if signature(before) != signature(after) or signature(after) != signature(path.stat()):
        raise ToolError(f"Tool file changed while reading: {path}")
    return h.hexdigest()


def read_json(path):
    if path.stat().st_size > 256 * 1024:
        raise ToolError(f"Description/record exceeds 256 KiB: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def nonempty(value):
    return isinstance(value, str) and bool(value.strip()) and "\0" not in value


def argv_valid(value):
    return isinstance(value, list) and bool(value) and all(nonempty(v) for v in value)


def load_description(path):
    path = Path(path)
    safe(path.parent, path.name, file=True)
    value = read_json(path)
    fields = {"version", "name", "origin", "purpose", "files", "invocation",
              "dependencies", "checks", "limitations"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ToolError(f"{path}: expected version-1 tool fields: {', '.join(sorted(fields))}")
    if type(value["version"]) is not int or value["version"] != 1:
        raise ToolError(f"{path}: unsupported tool description version")
    if not isinstance(value["name"], str) or not NAME.fullmatch(value["name"]):
        raise ToolError("Tool name must be a short identifier")
    if value["origin"] not in ("user", "agent"):
        raise ToolError("Tool origin must be 'user' or 'agent'")
    if not all(nonempty(value[k]) for k in ("purpose", "limitations")):
        raise ToolError("Tool purpose and limitations must be nonempty")
    if not argv_valid(value["invocation"]):
        raise ToolError("Tool invocation must be a nonempty argv array")
    if not isinstance(value["dependencies"], list) or not all(nonempty(v) for v in value["dependencies"]):
        raise ToolError("Tool dependencies must be an explicit list (possibly empty)")
    checks = value["checks"]
    if not isinstance(checks, list) or not checks:
        raise ToolError("Tool checks must be a nonempty list")
    for check in checks:
        if (not isinstance(check, dict) or set(check) != {"description", "argv"}
                or not nonempty(check["description"]) or not argv_valid(check["argv"])):
            raise ToolError("Each check requires a description and a nonempty argv array")
    files = value["files"]
    if not isinstance(files, list) or not files or not all(isinstance(f, str) for f in files):
        raise ToolError("Tool files must list required local runtime/check files")
    if len(set(files)) != len(files):
        raise ToolError("Tool files contain duplicates")
    for name in files:
        rel = relative(name)
        if rel.parts[0] in (path.name, RECORD, "SOURCE.json", "runs", "FOLDER_CONTENT.md"):
            raise ToolError(f"Reserved tool payload name: {name}")
        safe(path.parent, name, file=True)
    return value


def identities(path, description):
    hashes = {name: digest(safe(path.parent, name, file=True))
              for name in (path.name, *description["files"])}
    if load_description(path) != description:
        raise ToolError("Tool description changed while loading; retry after reviewing the new version")
    return hashes



def own_path(context, rel, *, file=False):
    rel = relative(str(rel))
    if (not rel.is_relative_to(context["workspace"])
            or any(rel.is_relative_to(p) for p in context["excluded"])):
        raise ToolError(f"Tool operation requires the caller's own working copy: {rel}")
    return safe(Path(context["project"]), rel, file=file)


def local_source(context, rel):
    """Scientific inputs may be copied, including protected human/frozen inputs."""
    path = relative(str(rel))
    if path.parts[0] not in ("starting_evidence", "sources", "work", "outputs"):
        raise ToolError(f"Not a local scientific input location: {rel}")
    return safe(Path(context["project"]), path, file=True)


def note_path(context, rel, *, read=False):
    own_path(context, rel)
    if Path(rel).suffix != ".md":
        raise ToolError("Assessment/record must be Markdown")
    draft = safe(Path(context["drafts"]), rel)
    return draft if not read or draft.exists() else own_path(context, rel, file=True)


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def save_note(context, rel, record, title, explanation=""):
    text = (f"# {title}\n\n{explanation}\n\n"
            f"{MARKER}```json\n{json.dumps(record, indent=2, ensure_ascii=True)}\n```{END}\n")
    atomic_text(note_path(context, rel), text)


def read_record(path):
    if path.stat().st_size > 256 * 1024:
        raise ToolError("Validation record exceeds 256 KiB")
    text = path.read_text(encoding="utf-8")
    if len(text) > 256 * 1024:
        raise ToolError("Validation record exceeds 256 KiB")
    try:
        block = text.split(MARKER, 1)[1].split(END, 1)[0]
        record = json.loads(block.removeprefix("```json\n").removesuffix("\n```"))
    except (IndexError, ValueError) as exc:
        raise ToolError("Missing or invalid structured validation record") from exc
    if not isinstance(record, dict):
        raise ToolError("Tool record must be a JSON object; review the record and revalidate")
    if type(record.get("version")) is not int or record["version"] != 1:
        raise ToolError("Unsupported or missing tool record version; revalidate")
    if not nonempty(record.get("activation")):
        raise ToolError("Tool record activation must be a nonempty string; revalidate")
    if record.get("outcome") not in ("pending", "failed", "successful"):
        raise ToolError("Tool record outcome must be pending, failed or successful")
    if "assessment" in record:
        assessment = record["assessment"]
        if (not isinstance(assessment, dict)
                or not all(nonempty(assessment.get(k)) for k in ("path", "sha256"))):
            raise ToolError("Validation record assessment requires an object with path and sha256 strings")
    if "checks" in record:
        if not isinstance(record["checks"], list):
            raise ToolError("Validation record checks must be a list of check objects; revalidate")
        for number, check in enumerate(record["checks"], 1):
            if (not isinstance(check, dict) or not argv_valid(check.get("argv"))
                    or not nonempty(check.get("description"))
                    or check.get("outcome") not in ("pending", "failed", "successful")
                    or (check.get("returncode") is not None and type(check["returncode"]) is not int)):
                raise ToolError(f"Validation record check {number} requires an object with "
                                "description, argv, outcome and integer/null returncode; revalidate")
    return record


def check_ready(context):
    if time.monotonic() >= context["deadline"]:
        raise ToolError("Admitted job deadline exhausted; no new tool work authorized")



def execute(context, argv, cwd):
    """Descendant of one admitted job; never obtains a new slot or deadline."""
    try:
        job = read_json(Path("/run/research-job.json"))
    except (OSError, ValueError) as exc:
        raise ToolError("Tool checks/runs require an admitted scientific job") from exc
    if (not job.get("job_id") or job.get("activation") != context["activation"]
            or context["deadline"] > job["deadline"]):
        raise ToolError("Tool execution does not match the immutable admitted job deadline/owner")
    check_ready(context)
    result = {"argv": argv, "cwd": str(cwd), "outcome": "failed",
              "returncode": None, "stdout": "", "stderr": "",
              "stdout_clipped": False, "stderr_clipped": False, "output_drain_incomplete": False}
    process = None
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    try:
        process = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        with selectors.DefaultSelector() as selector:
            for stream, name in ((process.stdout, "stdout"), (process.stderr, "stderr")):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            drain_deadline = None
            while selector.get_map() or process.poll() is None:
                check_ready(context)
                now = time.monotonic()
                if process.poll() is not None:
                    # A detached descendant can retain these descriptors after the
                    # foreground process exits. Drain briefly, then close our pipes;
                    # the job PID namespace supervisor owns complete teardown.
                    drain_deadline = drain_deadline or min(context["deadline"], now + .2)
                    if now >= drain_deadline:
                        result["output_drain_incomplete"] = bool(selector.get_map())
                        for key in selector.get_map().values():
                            result[key.data + "_clipped"] = True
                        break
                deadline = drain_deadline or context["deadline"]
                for key, _ in selector.select(min(.1, max(0, deadline - now))):
                    block = os.read(key.fileobj.fileno(), 65536)
                    if not block:
                        selector.unregister(key.fileobj)
                    else:
                        available = max(0, 8192 - len(buffers[key.data]))
                        buffers[key.data].extend(block[:available])
                        result[key.data + "_clipped"] |= len(block) > available
            result["returncode"] = process.wait(timeout=0)
            result["outcome"] = "successful" if result["returncode"] == 0 else "failed"
    except (OSError, ToolError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if process:
            # Foreground completion never intentionally leaves its process group.
            # Detached descendants remain inside this job's PID namespace.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            process.stdout.close()
            process.stderr.close()
        for name, data in buffers.items():
            result[name] = data.decode("utf-8", errors="replace")
    return result


def source_identity(context, path):
    rel = path.relative_to(context["project"]).as_posix()
    source = safe(path.parent, "SOURCE.json")
    staged = read_json(source) if source.exists() else None
    if staged and staged.get("outcome") != "staged":
        raise ToolError("Staging did not complete; review the preserved SOURCE.json failure")
    return {"local_path": rel, "origin": load_description(path)["origin"], "staged_from": staged}


def registration(context, path, description, *, current=True):
    rel = path.relative_to(context["project"]).with_name(RECORD).as_posix()
    record = read_record(note_path(context, rel, read=True))
    if record.get("outcome") != "successful":
        raise ToolError("Tool has no successful validation; run register with an assessment")
    if record.get("hashes") != identities(path, description):
        raise ToolError("Tool files changed since validation; revalidate")
    if current and record.get("activation") != context["activation"]:
        raise ToolError("Fresh activation/environment requires local revalidation")
    assessment = record["assessment"]
    assessment_path = note_path(context, assessment["path"], read=True)
    if not assessment_path.read_text().strip() or digest(assessment_path) != assessment["sha256"]:
        raise ToolError("Assessment changed since validation; revalidate")
    checks = record.get("checks", [])
    if (len(checks) != len(description["checks"])
            or any(c.get("outcome") != "successful" or c.get("returncode") != 0
                   or c.get("argv") != declared["argv"]
                   for c, declared in zip(checks, description["checks"]))):
        raise ToolError("Validation lacks successful declared check observations")
    return record


def register(context, relative_description, assessment, runner=execute):
    check_ready(context)
    path = own_path(context, relative_description, file=True)
    record_rel = path.relative_to(context["project"]).with_name(RECORD).as_posix()
    record = {"version": 1, "outcome": "pending", "activation": context["activation"],
              "task": context["task"], "description": str(relative_description), "checks": [],
              "cwd": str(path.parent), "deadline_monotonic": context["deadline"],
              "environment": {"python": sys.version, "executable": sys.executable,
                              "PATH": os.environ.get("PATH", "")}}
    explanation = ("Checks apply only to the researcher's declared intended use. They do not "
                   "establish scientific correctness, independent verification or general applicability. "
                   "A fresh activation or changed environment requires revalidation.")
    # Invalidate an earlier success even if parsing or assessment now fails.
    save_note(context, record_rel, record, "Tool validation: pending", explanation)
    try:
        description = load_description(path)
        record["hashes"] = identities(path, description)
        record["source"] = source_identity(context, path)
        assessment_path = note_path(context, assessment, read=True)
        text = assessment_path.read_text(encoding="utf-8")
        if not text.strip():
            raise ToolError("Researcher-authored intended-use assessment must be nonempty")
        record["assessment"] = {"path": str(assessment), "sha256": digest(assessment_path),
                                "intended_scope": text[:4000], "scope_clipped": len(text) > 4000}
        save_note(context, record_rel, record, "Tool validation: pending", explanation)
        for check in description["checks"]:
            check_ready(context)
            observation = runner(context, check["argv"], path.parent)
            record["checks"].append({**observation, "description": check["description"]})
            if observation["outcome"] != "successful" or observation["returncode"] != 0:
                raise ToolError("Declared check failed; inspect VALIDATION.md and preserve useful partial work")
            if identities(path, description) != record["hashes"]:
                raise ToolError("Tool files changed during checks; review and revalidate")
        check_ready(context)
        if digest(note_path(context, assessment, read=True)) != record["assessment"]["sha256"]:
            raise ToolError("Intended-use assessment changed during checks")
        record["outcome"] = "successful"
    except BaseException as exc:
        record.update(outcome="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        save_note(context, record_rel, record, f"Tool validation: {record['outcome']}", explanation)
    return {"validation": record_rel, **record}


def run(context, relative_description, arguments, runner=execute):
    check_ready(context)
    path = own_path(context, relative_description, file=True)
    description = load_description(path)
    validation = registration(context, path, description)
    receipt_rel = (path.parent.relative_to(context["project"]) / "runs" /
                   f"run-{uuid.uuid4().hex}.md").as_posix()
    receipt = {"version": 1, "outcome": "pending", "activation": context["activation"],
               "task": context["task"], "hashes": validation["hashes"],
               "source": validation["source"], "validation": str(path.parent / RECORD),
               "argv": [*description["invocation"], *arguments], "cwd": str(path.parent)}
    explanation = ("Execution observations are not independent scientific verification. "
                   "Retain partial outputs on failure; link scientifically relevant outputs in the report.")
    save_note(context, receipt_rel, receipt, "Tool invocation: pending", explanation)
    try:
        receipt.update(runner(context, receipt["argv"], path.parent))
        if identities(path, description) != validation["hashes"]:
            receipt.update(outcome="failed", error="Tool files changed during invocation; revalidate")
    except BaseException as exc:
        receipt.update(outcome="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        links = []
        for arg in arguments:
            candidate = Path(arg)
            if not candidate.is_absolute():
                candidate = path.parent / candidate
            if candidate.is_relative_to(context["project"]) and candidate.is_file():
                links.append(f"- [Output/input]({os.path.relpath(candidate, path.parent / 'runs')})")
        save_note(context, receipt_rel, receipt, f"Tool invocation: {receipt['outcome']}",
                  explanation + "\n\n" + "\n".join(links))
    return {"receipt": receipt_rel, **receipt}


def stage(context, catalog, relative_description, name, source=None):
    check_ready(context)
    if not NAME.fullmatch(name):
        raise ToolError("Destination name must be a short identifier")
    if source is not None:
        if source not in catalog:
            raise ToolError(f"Reference alias is not authorized: {source}")
        entry = catalog[source]
        if not entry["available"]:
            raise ToolError(entry["reason"])
        original = safe(Path(entry["path"]), relative_description, file=True)
        identity = {"alias": source, "root": entry["root"], "path": relative_description}
    else:
        original = local_source(context, relative_description)
        identity = {"alias": None, "root": context["project"], "path": relative_description}
    description = load_description(original)
    hashes = identities(original, description)
    target_rel = str(Path(context["workspace"]) / "tools" / name)
    target = own_path(context, target_rel)
    draft_target = safe(Path(context["drafts"]), target_rel)
    if target.exists() or draft_target.exists():
        raise ToolError(f"Destination already exists; choose a new name: {target_rel}")
    target.mkdir(parents=True)
    provenance = {**identity, "origin": description["origin"], "hashes": hashes,
                  "outcome": "pending"}
    atomic_text(target / "SOURCE.json", json.dumps(provenance, indent=2) + "\n")
    try:
        for item in (original.name, *description["files"]):
            check_ready(context)
            src = safe(original.parent, item, file=True)
            dest = safe(target, item)
            # Markdown still enters the normal scoped publication path.
            if dest.suffix == ".md":
                dest = note_path(context, str(Path(target_rel) / item))
            dest.parent.mkdir(parents=True, exist_ok=True)
            with src.open("rb") as inp, dest.open("xb") as out:
                for block in iter(lambda: inp.read(65536), b""):
                    check_ready(context)
                    out.write(block)
            dest.chmod(src.stat().st_mode & 0o777)
            if digest(dest) != hashes[item]:
                raise ToolError("Source changed during staging; retained partial working copy is ineligible")
        if identities(original, description) != hashes:
            raise ToolError("Source changed during staging; review the retained partial working copy")
        provenance["outcome"] = "staged"
    except BaseException as exc:
        provenance.update(outcome="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        atomic_text(target / "SOURCE.json", json.dumps(provenance, indent=2) + "\n")
    return {"description": f"{target_rel}/{original.name}", "source": provenance,
            "status": "unvalidated; local checks and assessment required"}


def discover(context, catalog, source=None, candidates=False):
    entries, errors = [], []
    if source is not None and source not in catalog:
        raise ToolError(f"Reference alias is not authorized: {source}")
    roots = [(alias, Path(item["path"]), item) for alias, item in catalog.items()
             if source is None or source == alias]
    if source is None:
        roots = [(None, Path(context["project"]) / name, None)
                 for name in ("starting_evidence", "sources", "work", "outputs")] + roots
    for alias, root, item in roots:
        if item and not item["available"]:
            errors.append(f"{alias}: {item['reason']}")
            continue
        if not item and not root.exists():
            continue
        if root.is_symlink():
            errors.append(f"Symlinked discovery root: {root}")
            continue
        for base, dirs, names in os.walk(root, followlinks=False, onerror=lambda exc: errors.append(str(exc))):
            check_ready(context)
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and
                             not (Path(base) / d).is_symlink())
            if "tool.json" not in names:
                continue
            path = Path(base) / "tool.json"
            relative_path = path.relative_to(root if alias else context["project"]).as_posix()
            entry = {"source": alias, "path": relative_path, "root": item["root"] if item else context["project"],
                     "eligible": False}
            try:
                if alias is None:
                    own_path(context, str(path.relative_to(context["project"])), file=True)
                description = load_description(path)
                entry.update(name=description["name"], origin=description["origin"],
                             purpose=description["purpose"], dependencies=description["dependencies"],
                             limitations=description["limitations"])
                if alias is None:
                    record = registration(context, path, description)
                else:
                    # Source validation is evidence from its original environment.
                    record = read_record(safe(path.parent, RECORD, file=True))
                    assessment = record["assessment"]
                    if (record.get("outcome") != "successful"
                            or record.get("hashes") != identities(path, description)
                            or len(record.get("checks", [])) != len(description["checks"])
                            or any(c.get("outcome") != "successful" or c.get("returncode") != 0
                                   or c.get("argv") != declared["argv"]
                                   for c, declared in zip(record["checks"], description["checks"]))
                            or digest(safe(root, assessment["path"], file=True)) != assessment["sha256"]):
                        raise ToolError("Missing, failed or stale source validation")
                entry.update(eligible=True, validation_activation=record["activation"],
                             qualification="Source-environment check evidence; imported copies require local validation"
                             if alias else "Current activation checks; scientific applicability still requires assessment")
            except (OSError, ValueError, KeyError, TypeError) as exc:
                entry["reason"] = str(exc)
            if candidates or entry["eligible"]:
                entries.append(entry)
    return {"tools": entries, "errors": errors, "incomplete": bool(errors)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    listing = sub.add_parser("list")
    listing.add_argument("--source")
    listing.add_argument("--candidates", action="store_true")
    staging = sub.add_parser("stage")
    origin = staging.add_mutually_exclusive_group(required=True)
    origin.add_argument("--source")
    origin.add_argument("--local", action="store_true")
    staging.add_argument("description")
    staging.add_argument("--name", required=True)
    registering = sub.add_parser("register")
    registering.add_argument("description")
    registering.add_argument("--assessment", required=True)
    running = sub.add_parser("run")
    running.add_argument("description")
    running.add_argument("arguments", nargs=argparse.REMAINDER)
    raw = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(raw)
    try:
        context = read_json(Path("/run/research-tools.json"))
        catalog = read_json(Path("/run/research-references.json"))
        if args.action == "list":
            result = discover(context, catalog, args.source, args.candidates)
        elif args.action == "stage":
            result = stage(context, catalog, args.description, args.name, args.source)
        elif args.action == "register":
            result = register(context, args.description, args.assessment)
        else:
            if len(raw) > 2 and raw[2] != "--":
                raise ToolError("Additional scientific arguments must follow --")
            result = run(context, args.description, args.arguments)
        print(json.dumps(result, indent=2))
        return 0 if result.get("outcome", "successful") == "successful" else 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
