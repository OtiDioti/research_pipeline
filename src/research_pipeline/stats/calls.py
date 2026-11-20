"""What one recorded tool call did to files: the paths it read, ran, wrote, listed or searched.

Deterministic rule tables, no model: a shell command is split into simple commands
(``&&``, ``||``, ``;``, ``|``, new lines; heredoc bodies dropped), each classified by
its verb (``cat`` reads its files, ``python x.py`` runs ``x.py``, a redirection
writes its target, ``cd`` moves the working folder for what follows). Claude Code's
file tools and the research tools (``spawn``, ``run_job``, ``accept``, …) are read from
their arguments. A call recorded only as its one-line summary (older runs, before
the activity log kept whole calls) is parsed from that text; a summary cut short is
marked, so that the numbers it feeds are known to be approximate.
"""

from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass, field

#: The working folder of a path relative to the project's root (e.g. ``git show REV:path``).
ROOT = "//project"
#: Verbs that read every file argument (options aside).
READERS = frozenset(
    [
        "cat",
        "head",
        "tail",
        "less",
        "more",
        "nl",
        "wc",
        "file",
        "stat",
        "strings",
        "xxd",
        "od",
        "md5sum",
        "sha256sum",
        "sha1sum",
        "sort",
        "uniq",
        "cut",
        "column",
        "tac",
        "fold",
        "fmt",
        "pdftotext",
        "pdfinfo",
        "diff",
        "cmp",
        "comm",
        "diff3",
        "bat",
        "jq",
        "yq",
        "csvlook",
        "pdftoppm",
        "pdfimages",
        "pdflatex",
        "latexmk",
        "xelatex",
        "lualatex",
        "bibtex",
        "biber",
        "pandoc",
        "inkscape",
        "montage",
        "convert",
        "magick",
        "identify",
        "tar",
        "unzip",
        "zcat",
        "gunzip",
        "ruff",
        "pyright",
        "mypy",
        "black",
        "isort",
        "flake8",
        "shellcheck",
    ]
)
#: Verbs whose first argument (options aside) is a program or pattern, not a file.
PATTERNED = frozenset(["sed", "awk", "grep", "rg", "egrep", "fgrep", "ag", "jq"])
#: Verbs that search a folder (listing or matching names).
SEARCHERS = frozenset(["grep", "rg", "egrep", "fgrep", "ag"])
LISTERS = frozenset(["ls", "tree", "find", "fd", "du"])
#: Interpreters: their first file argument is a program they run.
INTERPRETERS = frozenset(
    [
        "python",
        "python3",
        "julia",
        "bash",
        "sh",
        "zsh",
        "Rscript",
        "node",
        "ruby",
        "perl",
        "gnuplot",
        "octave",
        "matlab",
        "sage",
        "pytest",
    ]
)
#: Verbs that only prefix another command.
PREFIXES = frozenset(["sudo", "env", "nice", "nohup", "time", "timeout", "stdbuf", "xargs", "exec", "builtin"])
#: Shell keywords before a command ('do cat x', 'then python y'): the command follows.
LEADERS = frozenset(["do", "then", "else", "elif", "if", "while", "until", "!", "{", "time"])
#: Shell keywords that start no command of their own ('for f in …', 'done', 'fi').
CONTROL = frozenset(["for", "case", "select", "in", "done", "fi", "esac", "}", "function"])
#: Verbs with no file effect worth counting.
_SHELL_INERT = (
    "echo printf true false sleep pwd date which type whoami hostname uname export set unset source . alias "
    "test [ [[ read wait kill ps top clear history exit return shift trap ulimit umask hash command free nproc "
    "df uptime lscpu nvidia-smi kpsewhich curl wget ping ssh-keygen basename dirname realpath readlink seq "
    "expr bc let declare local tput stty yes"
)
#: Lines of a Python program that reached the shell's text (e.g. an inline program cut short).
_PYTHON_LINES = "from import with def class print"
INERT = frozenset(_SHELL_INERT.split() + _PYTHON_LINES.split())
#: Package managers: only what they run counts ('uv run python x.py'); installing is not a file access.
MANAGERS = frozenset(["uv", "poetry", "conda", "pixi", "pip", "pip3", "npm", "npx"])
#: Options of a manager's 'run' that take a value.
_VALUED = frozenset(
    ["--project", "--directory", "--with", "--python", "-p", "--env-file", "--group", "--extra", "--package"]
)
#: Verbs that write their file arguments.
WRITERS = frozenset(["touch", "mkdir", "rm", "rmdir", "chmod", "truncate"])
_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_OPERATORS = frozenset({"&&", "||", ";", "|", "&", ";;", "(", ")", "|&"})
_REDIRECTS = {">": "write", ">>": "write", "<": "read", "&>": "write", ">&": None, "<<<": None, "<&": None}


@dataclass
class Access:
    """One file access: ``op`` is 'read', 'run', 'write', 'list' or 'search'; ``path`` as written in the call."""

    op: str
    path: str
    cwd: str | None = (
        None  # the folder it is relative to, as the call says (None: the agent's own; ROOT: the project's)
    )


@dataclass
class Call:
    """A tool call as the stats see it."""

    kind: str  # 'shell', 'read', 'edit', 'web', 'research' (the controller's tools), 'other'
    name: str  # the tool's name (e.g. 'shell', 'Read', 'spawn')
    accesses: list[Access] = field(default_factory=list)
    arguments: dict = field(default_factory=dict)  # a research tool's arguments
    cut: bool = False  # recorded only in part: what it touched may be missing
    unparsed: int = 0  # simple commands whose verb no table knows


def call(entry: dict) -> Call:
    """The call of an activity log's ``tool`` entry: from its whole recorded call, else from its summary."""
    recorded = entry.get("call")
    if isinstance(recorded, dict):
        return _whole(str(recorded.get("name", "")), recorded.get("input") or {}, bool(recorded.get("cut")))
    return _summary(str(entry.get("text", "")))


def _whole(name: str, given, cut: bool) -> Call:
    arguments = given if isinstance(given, dict) else {}
    if name in ("shell", "Bash"):
        found = shell(str(arguments.get("command", "")), arguments.get("cwd"))
        found.name, found.cut = name, found.cut or cut
        return found
    if name in ("Read", "NotebookRead"):
        path = arguments.get("file_path") or arguments.get("notebook_path") or ""
        return Call("read", name, [Access("read", str(path))] if path else [], cut=cut)
    if name in ("Write", "Edit", "MultiEdit", "NotebookEdit", "edit"):
        paths = arguments.get("paths") or [arguments.get("file_path") or arguments.get("notebook_path") or ""]
        return Call("edit", name, [Access("write", str(path)) for path in paths if path], cut=cut)
    if name in ("Grep", "Glob", "LS"):
        path = arguments.get("path") or "."
        return Call("read", name, [Access("list" if name != "Grep" else "search", str(path))], cut=cut)
    if name in ("web_search", "WebSearch", "WebFetch"):
        return Call("web", name, cut=cut)
    research = name.removeprefix("mcp__research__")
    if research in RESEARCH_TOOLS:
        found = Call("research", research, arguments=arguments, cut=cut)
        if research == "run_job":
            found.accesses = shell(str(arguments.get("command", "")), arguments.get("cwd") or None).accesses
        elif research == "spawn" and arguments.get("task"):
            found.accesses = [Access("read", str(arguments["task"]))]
        return found
    return Call("other", name, cut=cut)


#: The controller's tools (research_pipeline.tools), as the stats name them.
RESEARCH_TOOLS = frozenset(
    [
        "spawn",
        "agents",
        "message",
        "accept",
        "reject",
        "cancel",
        "run_job",
        "job_status",
        "job_cancel",
        "submit_result",
        "complete",
        "stop",
        "verdict",
        "write_page",
        "shelved",
    ]
)


def _summary(text: str) -> Call:
    """A call recorded only as its summary (see :mod:`agent_toolkit.activity`): parse what it still says."""
    if text.startswith("$ "):
        command, _, _ = text[2:].rpartition("  → exit ")
        command = command or text[2:]
        found = shell(command, None)
        found.cut = found.cut or len(f"$ {command}") >= 300
        return found
    if text.startswith("edit "):
        paths = [path.strip() for path in text[5:].split(", ") if path.strip()]
        return Call("edit", "edit", [Access("write", path) for path in paths], cut=len(text) >= 305)
    if text.startswith("web search: "):
        return Call("web", "web_search")
    match = re.match(r"^([A-Za-z_][\w-]*)\((.*)\)$", text, re.S)
    if not match:
        return Call("other", text.split(" ", 1)[0][:40])
    name, body = match.groups()
    try:
        arguments = json.loads(body)
    except ValueError:
        arguments = _partial(body)  # cut at 200 characters
        found = _whole(name, arguments, True)
        return found
    return _whole(name, arguments, False)


def _partial(body: str) -> dict:
    """The string fields still complete in a JSON object cut short."""
    return {key: value for key, value in re.findall(r'"(\w+)":\s*"((?:[^"\\]|\\.)*)"', body)}


# Shell commands ------------------------------------------------------------------------------


def shell(command: str, cwd: str | None) -> Call:
    """The accesses of a shell command line, run in ``cwd`` (None: the agent's folder)."""
    script = _inner(command)
    found = Call("shell", "shell")
    script = _without_heredocs(script)
    try:
        lexer = shlex.shlex(script.replace("\n", " ; "), posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:  # unbalanced quotes: a command cut short
        tokens, found.cut = script.replace("\n", " ; ").split(), True
    here = cwd
    for words in _simple(tokens):
        here = _classify(words, here, found)
    return found


def _inner(command: str) -> str:
    """The script of ``/bin/bash -lc '...'`` (as Codex records it), else the command itself."""
    try:
        words = shlex.split(command)
    except ValueError:
        return command
    if len(words) == 3 and words[0].rsplit("/", 1)[-1] in ("bash", "sh", "zsh") and words[1] in ("-lc", "-c"):
        return words[2]
    return command


def _without_heredocs(script: str) -> str:
    """``script`` with every heredoc's body removed (its lines are data, not commands)."""
    lines, kept, ending = script.split("\n"), [], None
    for line in lines:
        if ending is not None:
            if line.strip() == ending:
                ending = None
            continue
        kept.append(line)
        match = _HEREDOC.search(line)
        if match:
            ending = match.group(2)
    return "\n".join(kept)


def _simple(tokens: list[str]) -> list[list[str]]:
    """Split tokens into simple commands at the shell's operators (redirections stay with their command)."""
    commands, current = [], []
    for token in tokens:
        if token in _OPERATORS:
            if current:
                commands.append(current)
            current = []
        else:
            current.append(token)
    if current:
        commands.append(current)
    return commands


def _classify(words: list[str], cwd: str | None, found: Call) -> str | None:
    """Add one simple command's accesses to ``found``; return the working folder after it."""
    words = list(words)
    redirect_ops, rest = [], []
    index = 0
    while index < len(words):  # redirections first: '> file', '2>/dev/null', '>>out'
        word = words[index]
        if word.startswith("<<"):  # a heredoc or here-string: its marker or text is no file
            index += 1 if word.rstrip("<-") else 2
            continue
        match = re.match(r"^(\d*)(>>|>|<|&>)(.*)$", word)
        if match and match.group(2) in _REDIRECTS:
            target = match.group(3) or (words[index + 1] if index + 1 < len(words) else "")
            index += 1 if match.group(3) else 2
            if target and not target.startswith("&") and target != "/dev/null":
                redirect_ops.append(Access(_REDIRECTS[match.group(2)] or "write", target, cwd))
            continue
        rest.append(word)
        index += 1
    found.accesses += redirect_ops
    while rest and (_ASSIGNMENT.match(rest[0]) or rest[0] in PREFIXES):
        prefix = rest.pop(0)
        if prefix == "timeout" and rest and re.match(r"^[\d.]+[smhd]?$", rest[0]):
            rest.pop(0)
        while prefix in ("timeout", "env", "nice", "stdbuf") and rest and rest[0].startswith("-"):
            rest.pop(0)
    while rest and rest[0] in LEADERS:
        rest.pop(0)
    if not rest or rest[0] in CONTROL:
        return cwd
    verb, arguments = rest[0], rest[1:]
    base = verb.rsplit("/", 1)[-1]
    files = [word for word in arguments if not word.startswith("-")]
    if base == "cd":
        target = files[0] if files else None
        if target in (None, "-", "~"):
            return cwd
        return target if target.startswith("/") or not cwd else f"{cwd.rstrip('/')}/{target}"
    if base in INERT:
        return cwd
    if base == "git":
        return _git(arguments, cwd, found)
    if base in MANAGERS:
        if "run" not in arguments and base not in ("npx",):
            return cwd
        following = arguments[arguments.index("run") + 1 :] if "run" in arguments else list(arguments)
        while following and following[0].startswith("-"):
            option = following.pop(0)
            if option in _VALUED and following:
                following.pop(0)
        return _classify(following, cwd, found) if following else cwd
    if base in PATTERNED:
        explicit = any(word in ("-e", "-f", "--regexp", "--file") or word.startswith("--regexp=") for word in arguments)
        paths = files if explicit else files[1:]
        if base == "sed" and any(word == "-i" or word.startswith("-i") for word in arguments):
            found.accesses += [Access("write", path, cwd) for path in paths]
            return cwd
        if base in SEARCHERS:
            found.accesses += [Access("search", path, cwd) for path in paths or ["."]]
        else:
            found.accesses += [Access("read", path, cwd) for path in paths]
        return cwd
    if base in READERS:
        found.accesses += [Access("read", path, cwd) for path in files]
        return cwd
    if base in LISTERS:
        paths = [word for word in arguments if not word.startswith("-")]
        if base == "find":
            paths = list(_until_option(arguments))
        found.accesses += [Access("list", path, cwd) for path in paths or ["."]]
        return cwd
    if base in WRITERS:
        found.accesses += [Access("write", path, cwd) for path in files]
        return cwd
    if base in ("cp", "rsync", "ln", "install"):
        if len(files) >= 2:
            found.accesses += [Access("read", path, cwd) for path in files[:-1]]
            found.accesses.append(Access("write", files[-1], cwd))
        return cwd
    if base == "mv":
        found.accesses += [Access("write", path, cwd) for path in files]
        return cwd
    if base == "tee":
        found.accesses += [Access("write", path, cwd) for path in files]
        return cwd
    if base == "make":
        found.accesses.append(Access("run", ".", cwd))
        return cwd
    if base in INTERPRETERS or re.match(r"^python\d", base) or base == "pytest":
        _interpreted(base, arguments, cwd, found)
        return cwd
    if "/" in verb:  # ./script, tool/bin/run, .venv/bin/x: a program of the project
        if "/.venv/" in f"/{verb}" or "/bin/" in verb:
            program = arguments[0] if arguments and re.search(r"\.(py|jl|R|sh|js)$", arguments[0]) else None
            if base.startswith(("python", "julia", "pytest")) and program:
                found.accesses.append(Access("run", program, cwd))
            elif base.startswith(("python", "julia")):
                _interpreted(base, arguments, cwd, found)
            return cwd
        found.accesses.append(Access("run", verb, cwd))
        return cwd
    found.unparsed += 1
    return cwd


def _interpreted(base: str, arguments: list[str], cwd: str | None, found: Call) -> None:
    """``python x.py``, ``python -m pkg``, ``julia x.jl``, ``pytest tests/``: what runs."""
    skip_next = {"-c", "-e", "--eval", "-W", "-X", "--project", "-O"}
    index = 0
    while index < len(arguments):
        word = arguments[index]
        if word in ("-c", "-e", "--eval", "-"):
            return  # an inline program: nothing of the project runs by name
        if word == "-m":
            return
        if word in skip_next:
            index += 2
            continue
        if word.startswith("-"):
            index += 1
            continue
        found.accesses.append(Access("run", word, cwd))
        if base != "pytest":
            return
        index += 1


def _until_option(arguments: list[str]):
    for word in arguments:
        if word.startswith(("-", "(", "!")):
            return
        yield word


def _git(arguments: list[str], cwd: str | None, found: Call) -> str | None:
    """``git show REV:path`` and ``git log/diff -- path`` read; other git commands are inert here."""
    if not arguments:
        return cwd
    if arguments[0] == "show":
        for word in arguments[1:]:
            if ":" in word and not word.startswith("-"):
                found.accesses.append(Access("read", word.split(":", 1)[1], ROOT))
    elif arguments[0] in ("log", "diff") and "--" in arguments:
        found.accesses += [Access("read", path, cwd) for path in arguments[arguments.index("--") + 1 :]]
    return cwd
