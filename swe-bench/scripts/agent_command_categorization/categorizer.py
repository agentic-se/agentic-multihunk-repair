"""
Command Categorizer (SWE-bench port)

Categorizes shell commands executed by AI agents inside the SWE-bench
Docker evaluation containers. Adapted from the original Defects4J
categorizer at ``birch/oak/agent_command_categorization/categorizer.py``.

The SWE-bench evaluation environment differs from Defects4J in three
important ways and the bucket design reflects that:

* The repaired projects are Python (not Java/Maven). ``defects4j``,
  ``mvn``, ``gradle``, ``ant`` and ``java`` rarely (if ever) appear.
* Every container starts at ``/testbed`` with the project's conda env
  already activated. Testing happens through ``pytest`` (or
  ``python -m pytest``/``unittest``) and ad-hoc ``python`` invocations.
* Two helper scripts are injected into every container by
  ``swe_bench_utils.container_setup``: ``./run_failing_tests.sh`` and
  ``./run_all_tests.sh``. Those play the role of the old Defects4J
  ``run_bug_exposing_tests.sh`` / ``run_all_tests_trace.sh`` scripts.

The seven SWE-bench buckets returned by :func:`categorize_command`:

==========================  ====================================================
Bucket                      What lands here
==========================  ====================================================
``test``                    Anything that runs the test suite — pytest /
                             ``python -m pytest`` / ``python -m unittest`` /
                             ``nosetests`` / ``tox`` / ``coverage``, the SWE-bench
                             helper wrappers ``./run_failing_tests.sh`` and
                             ``./run_all_tests.sh``, and the project-shipped
                             runners ``runtests.py`` (Django), ``bin/test``
                             (sympy), ``./manage.py test`` (Django alt).
``python_exec``             ``python``/``python3`` invocations that are *not*
                             test runs (e.g. running a repro script, ``-c`` one
                             liners). Also ``ipython`` / ``py``.
``git_all``                 Anything starting with ``git`` (``diff``, ``log``,
                             ``status``, ``checkout``, ``apply`` etc.).
``package_install``         ``pip``/``pip3``/``conda``/``mamba`` install/remove
                             operations. Rare under ``/testbed`` but possible.
``file_operations``         ``rm``, ``mkdir``, ``cp``, ``mv``, ``ls``, ``chmod``
                             ``touch``, ``ln`` — file-system bookkeeping.
``text_search``             ``grep``, ``egrep``, ``rg``, ``ag``, ``find``,
                             ``locate``, ``which`` — locating code.
``other``                   Everything else (``cat``, ``sed``, ``awk``, ``echo``,
                             ``cd``, etc.).
==========================  ====================================================

Returning exactly these seven strings is part of the module's contract;
the metric scripts use them verbatim as ``Bash_<bucket>`` column names.
"""

from __future__ import annotations

import shlex
from typing import List


_PYTEST_TOKENS = ("pytest", "py.test")
_UNITTEST_TOKENS = ("unittest",)


def _tokens(cmd_stripped: str) -> List[str]:
    """Best-effort shell tokenizer that never raises."""
    try:
        return shlex.split(cmd_stripped)
    except ValueError:
        return cmd_stripped.split()


# Python interpreter flags that consume the *next* token as their value.
# Without this set, a command like ``python -W ignore::DeprecationWarning -m
# pytest ...`` would be misclassified: the scanner would treat
# ``ignore::DeprecationWarning`` as the first positional argument (since it
# doesn't start with ``-``) and bail before seeing the ``-m pytest``.
_PYTHON_VALUE_TAKING_SHORT_FLAGS = {"-c", "-m", "-W", "-X", "-Q"}


def _is_python_test_invocation(tokens: List[str]) -> bool:
    """Detect ``python [opts] -m pytest|unittest|nose ...`` patterns.

    Correctly skips over the *values* of value-taking short flags such as
    ``-W <warning-filter>`` and ``-X <option>`` so that ``-m pytest`` is
    still found when those flags appear earlier in the command line.
    """
    if not tokens:
        return False
    base = tokens[0].rsplit("/", 1)[-1].lower()
    if base not in {"python", "python2", "python3", "py", "ipython"}:
        return False
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok == "-m" and i + 1 < len(tokens):
            mod = tokens[i + 1].lower()
            if mod in _PYTEST_TOKENS or mod in _UNITTEST_TOKENS or mod == "nose":
                return True
            return False
        if tok in _PYTHON_VALUE_TAKING_SHORT_FLAGS:
            # Flag consumes the next token (its value); skip both.
            i += 2
            continue
        if tok.startswith("-"):
            # Other flags (no value) — skip just this one.
            i += 1
            continue
        # First positional argument that isn't a value of a previous flag:
        # this is not a ``-m <module>`` invocation.
        return False
    return False


def _parse_first_command(command: str):
    """Tokenize the *first* command in a shell string.

    Splits on ``&&``/``||``/``;``/newline/pipe, strips leading env-var
    assignments (``FOO=bar python ...``), and returns a tuple

        (cmd_stripped, head, tokens, base_raw, base, rest_lower)

    where ``head`` is the first sub-command, ``base_raw`` is the raw
    first token (path preserved), ``base`` is the lowercased basename,
    and ``rest_lower`` is the lowercased tail of the token list.

    Returns ``None`` when the input is empty or yields no real tokens.
    """
    if not command:
        return None
    cmd_stripped = command.strip()
    if not cmd_stripped:
        return None

    head = cmd_stripped
    for delim in ("&&", "||", ";", "\n", "|"):
        if delim in head:
            head = head.split(delim, 1)[0].strip()
            if not head:
                return None

    tokens = _tokens(head)
    while tokens and "=" in tokens[0] and not tokens[0].startswith(("=", ">", "<")):
        key = tokens[0].split("=", 1)[0]
        if key.isidentifier():
            tokens = tokens[1:]
            continue
        break

    if not tokens:
        return None

    base_raw = tokens[0]
    base = base_raw.rsplit("/", 1)[-1].lower()
    rest_lower = " ".join(tokens[1:]).lower()
    return cmd_stripped, head, tokens, base_raw, base, rest_lower


def categorize_command(command: str) -> str:
    """Return one of the seven SWE-bench buckets for ``command``.

    The match is performed on the *first* command in the string (before
    any ``&&``/``||``/``;`` connector). That matches what
    ``group_command_line_operations_*`` already does upstream when it
    chooses which bucket a row belongs to.
    """
    parsed = _parse_first_command(command)
    if parsed is None:
        return "other"
    cmd_stripped, head, tokens, base_raw, base, rest_lower = parsed

    # ------------------------------------------------------------------
    # Testing (single umbrella bucket — Option B)
    #
    # Covers four flavors of "the agent ran tests":
    #   1. SWE-bench helper scripts injected by container_setup.py:
    #        ./run_failing_tests.sh, ./run_all_tests.sh
    #   2. Test frameworks invoked directly:
    #        pytest, py.test, nosetests, tox, coverage
    #   3. ``python -m pytest|unittest|nose ...`` invocations
    #   4. Project-shipped test runners:
    #        runtests.py (Django), bin/test (sympy),
    #        ``./manage.py test ...`` (Django alt)
    # ------------------------------------------------------------------
    if (
        "./run_failing_tests.sh" in cmd_stripped
        or "./run_all_tests.sh" in cmd_stripped
        or base_raw in ("./run_failing_tests.sh", "./run_all_tests.sh")
        or base in ("run_failing_tests.sh", "run_all_tests.sh")
    ):
        return "test"

    # Project-shipped test runners (basename match so any path resolves).
    if base in {"runtests.py", "test"} and base_raw.endswith(("runtests.py", "bin/test")):
        return "test"

    # ``./manage.py test ...`` (Django) — ``manage.py`` with a ``test`` subcommand.
    if base == "manage.py" and tokens[1:] and tokens[1].lower() == "test":
        return "test"

    # ------------------------------------------------------------------
    # Version control
    # ------------------------------------------------------------------
    if base == "git":
        return "git_all"

    # ------------------------------------------------------------------
    # Test frameworks
    # ------------------------------------------------------------------
    if base in _PYTEST_TOKENS or base == "nosetests":
        return "test"

    if base in {"python", "python2", "python3", "py", "ipython"}:
        if _is_python_test_invocation(tokens):
            return "test"
        # ``python <something>/runtests.py ...`` and
        # ``python ./manage.py test ...`` also count as test runs.
        for tok in tokens[1:]:
            if tok.startswith("-"):
                continue
            tok_base = tok.rsplit("/", 1)[-1].lower()
            if tok_base == "runtests.py" or tok.endswith("bin/test"):
                return "test"
            if tok_base == "manage.py":
                # consider the next non-flag token
                idx = tokens.index(tok) + 1
                while idx < len(tokens) and tokens[idx].startswith("-"):
                    idx += 1
                if idx < len(tokens) and tokens[idx].lower() == "test":
                    return "test"
            break
        return "python_exec"

    # ``tox``/``coverage`` are thin wrappers around pytest in practice.
    if base in {"tox", "coverage"}:
        return "test"

    # ------------------------------------------------------------------
    # Package install (pip/conda/mamba). Read-only ``pip list`` etc.
    # falls into ``other`` since the SWE-bench env is already provisioned.
    # ------------------------------------------------------------------
    if base in {"pip", "pip3", "pip2"}:
        if any(verb in rest_lower for verb in ("install", "uninstall", "download")):
            return "package_install"
        return "other"
    if base in {"conda", "mamba", "micromamba"}:
        if any(verb in rest_lower for verb in ("install", "create", "update", "remove", "uninstall")):
            return "package_install"
        return "other"

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------
    if base in {"rm", "rmdir", "mkdir", "cp", "mv", "ls", "chmod", "chown", "touch", "ln"}:
        return "file_operations"

    # ------------------------------------------------------------------
    # Text search
    # ------------------------------------------------------------------
    if base in {"grep", "egrep", "fgrep", "rg", "ag", "ack", "find", "locate", "which", "whereis"}:
        return "text_search"

    # ------------------------------------------------------------------
    # Default
    # ------------------------------------------------------------------
    return "other"


# ======================================================================
# Paper-aligned categorization (Table 14 / Figs 9-10)
# ======================================================================
#
# The TOSEM paper "Beyond Accuracy: Behavioral Dynamics of Agentic
# Multi-Hunk Repair" uses 16 functional categories defined in the
# Defects4J-side ``oak/agent_command_statistics/command_categorizer.py``.
# Table 14 reports the top 7 of those 16 ("WRITE, READ, TEST, BUILD,
# SEARCH_CONTENT, SEARCH_FILES, NAVIGATE"); the remaining 9 are still
# in the schema but do not make the top-7 by frequency in D4J data.
#
# :func:`categorize_action` returns one of these 17 strings (16 paper
# categories + ``OTHER`` for anything that doesn't fit) for a single
# tool call. Native Claude tools route by tool name; ``Bash`` calls are
# parsed and routed by the base command, with the same SWE-bench
# adjustments captured in :func:`categorize_command` (TEST wrappers,
# repo-shipped test runners, pip/conda → BUILD per Q5a).

#: All 16 paper categories plus an explicit ``OTHER`` fallback. Listed
#: in the same order as Defects4J's command_categorizer for stability.
PAPER_CATEGORIES = (
    "READ",
    "SEARCH_CONTENT",
    "SEARCH_FILES",
    "NAVIGATE",
    "WRITE",
    "TRANSFORM",
    "BUILD",
    "TEST",
    "VCS",
    "PATCH",
    "FILE_OPS",
    "UTIL",
    "SCRIPT",
    "WEB",
    "BENCHMARK_OTHER",
    "ARCHIVE",
    "OTHER",
)

#: Native tools → paper category. Covers all four agents (Claude,
#: Codex, Gemini-cli, Qwen Code) used in the HunkSWE evaluation.
#:
#: Claude uses PascalCase names. Gemini-cli, Qwen Code (and Gemini's
#: MCP variants) use snake_case names. Codex has no native tools (it
#: routes everything through shell exec). The mapping below merges all
#: of these into the single 17-bucket PAPER_CATEGORIES taxonomy used
#: by the original Defects4J `command_categorizer`, so cross-agent
#: counts are directly comparable.
_NATIVE_TOOL_CATEGORY = {
    # ---- Claude Code (PascalCase) ----
    "Read": "READ",
    "NotebookRead": "READ",
    "Edit": "WRITE",
    "Write": "WRITE",
    "NotebookEdit": "WRITE",
    "TodoWrite": "WRITE",
    "Grep": "SEARCH_CONTENT",
    "Glob": "SEARCH_FILES",
    "LS": "SEARCH_FILES",
    "WebSearch": "WEB",
    "WebFetch": "WEB",
    "Task": "UTIL",
    "ExitPlanMode": "UTIL",
    "BashOutput": "OTHER",
    "KillShell": "OTHER",
    "SlashCommand": "OTHER",
    "Skill": "OTHER",
    "AskUserQuestion": "OTHER",
    # ---- Gemini-cli (snake_case) ----
    "read_file": "READ",
    "read_many_files": "READ",
    "write_file": "WRITE",
    "replace": "WRITE",
    "glob": "SEARCH_FILES",
    "list_directory": "SEARCH_FILES",
    "search_file_content": "SEARCH_CONTENT",
    "google_web_search": "WEB",
    "web_fetch": "WEB",
    # ---- Qwen Code (snake_case, partial overlap with Gemini) ----
    "edit": "WRITE",
    "todo_write": "WRITE",
    "grep_search": "SEARCH_CONTENT",
    "get_code_snippet": "READ",
    "task_stop": "UTIL",
    "exit_plan_mode": "UTIL",
    "agent": "UTIL",
}

#: Bash base command → paper category. Mirrors Defects4J's
#: command_categorizer.CATEGORIES, restricted to non-special-cased base
#: names (git, python, pip, conda, the TEST wrappers and the repo-shipped
#: test runners are handled by dedicated branches in
#: :func:`_bash_to_paper_category` below).
_BASH_BASE_TO_PAPER = {
    # READ — content viewers
    "cat": "READ", "tac": "READ", "head": "READ", "tail": "READ",
    "nl": "READ", "less": "READ", "more": "READ", "bat": "READ",
    "strings": "READ", "hexdump": "READ", "od": "READ", "tee": "READ",
    # SEARCH_CONTENT — pattern search inside files
    "grep": "SEARCH_CONTENT", "egrep": "SEARCH_CONTENT",
    "fgrep": "SEARCH_CONTENT", "rg": "SEARCH_CONTENT",
    "ag": "SEARCH_CONTENT", "ack": "SEARCH_CONTENT",
    # SEARCH_FILES — file-system queries
    "ls": "SEARCH_FILES", "find": "SEARCH_FILES", "tree": "SEARCH_FILES",
    "which": "SEARCH_FILES", "whereis": "SEARCH_FILES", "locate": "SEARCH_FILES",
    # NAVIGATE — directory changes
    "cd": "NAVIGATE", "pwd": "NAVIGATE", "pushd": "NAVIGATE",
    "popd": "NAVIGATE", "dirs": "NAVIGATE",
    # WRITE — text/file modification (Q3a: sed/awk → WRITE per D4J)
    "sed": "WRITE", "awk": "WRITE",
    # TRANSFORM — pure data transformation
    "tr": "TRANSFORM", "cut": "TRANSFORM", "sort": "TRANSFORM",
    "uniq": "TRANSFORM", "column": "TRANSFORM", "paste": "TRANSFORM",
    "join": "TRANSFORM", "fmt": "TRANSFORM", "fold": "TRANSFORM",
    # BUILD — compilation / make-style (Python projects rarely use these)
    "make": "BUILD", "cmake": "BUILD", "gcc": "BUILD", "g++": "BUILD",
    "clang": "BUILD", "clang++": "BUILD",
    # TEST frameworks invoked directly (pytest etc.)
    "pytest": "TEST", "py.test": "TEST", "nosetests": "TEST",
    "tox": "TEST", "coverage": "TEST",
    # PATCH — patch application
    "patch": "PATCH", "apply_patch": "PATCH", "applypatch": "PATCH",
    "gnuapply": "PATCH",
    # FILE_OPS — Q2: rm/mkdir/cp/mv/chmod/touch/ln per D4J FILE_OPS
    "cp": "FILE_OPS", "mv": "FILE_OPS", "rm": "FILE_OPS",
    "mkdir": "FILE_OPS", "rmdir": "FILE_OPS", "touch": "FILE_OPS",
    "chmod": "FILE_OPS", "chown": "FILE_OPS", "ln": "FILE_OPS",
    "file": "FILE_OPS",
    # UTIL — shell utilities & control flow
    "echo": "UTIL", "printf": "UTIL", "true": "UTIL", "false": "UTIL",
    "xargs": "UTIL", "wc": "UTIL", "basename": "UTIL", "dirname": "UTIL",
    "date": "UTIL", "time": "UTIL", "sleep": "UTIL", "timeout": "UTIL",
    "env": "UTIL", "export": "UTIL", "set": "UTIL", "read": "UTIL",
    "seq": "UTIL", "md5sum": "UTIL", "sha256sum": "UTIL", "iconv": "UTIL",
    "[": "UTIL", "test": "UTIL", "[[": "UTIL",
    "if": "UTIL", "case": "UTIL", "for": "UTIL", "while": "UTIL",
    "do": "UTIL", "done": "UTIL", "then": "UTIL", "else": "UTIL",
    "fi": "UTIL", "break": "UTIL", "return": "UTIL", "exit": "UTIL",
    # SCRIPT — interpreter launches (python handled separately so we can
    # detect TEST sub-modes per Q1c).
    "perl": "SCRIPT", "ruby": "SCRIPT", "php": "SCRIPT",
    "bash": "SCRIPT", "sh": "SCRIPT", "zsh": "SCRIPT", "fish": "SCRIPT",
    "node": "SCRIPT", "jshell": "SCRIPT", "lua": "SCRIPT",
    # WEB — network fetches (web_fetch/google_web_search are native tools)
    "curl": "WEB", "wget": "WEB", "http": "WEB", "httpie": "WEB",
    # ARCHIVE
    "tar": "ARCHIVE", "zip": "ARCHIVE", "unzip": "ARCHIVE",
    "gzip": "ARCHIVE", "gunzip": "ARCHIVE", "bzip2": "ARCHIVE",
    "bunzip2": "ARCHIVE", "xz": "ARCHIVE", "unxz": "ARCHIVE",
    "7z": "ARCHIVE",
}


def _bash_to_paper_category(command: str) -> str:
    """Route a single Bash command to one of the 16 paper categories.

    Order of checks (most specific first):

    1. SWE-bench TEST wrappers (``./run_failing_tests.sh``, ``./run_all_tests.sh``)
       → ``TEST``.
    2. Repo-shipped test runners — ``runtests.py`` (Django),
       ``bin/test`` (sympy), ``./manage.py test`` (Django alt) → ``TEST``.
    3. ``git <subcommand>`` → ``VCS`` (Q4: per D4J one bucket for all git).
    4. ``python`` / ``python3`` / ``py`` / ``ipython``:
       - ``-m pytest|unittest|nose`` (with value-flag aware scan) → ``TEST``.
       - Running a known repo test runner (see #2) → ``TEST``.
       - Anything else → ``SCRIPT`` (Q1c: D4J-faithful, no name-based
         smart-split of agent-authored scripts).
    5. ``pip`` / ``pip3`` / ``conda`` / ``mamba`` with install/uninstall/
       create/update verbs → ``BUILD`` (Q5a: environment build-up).
       Read-only ``pip list`` etc. → ``UTIL``.
    6. Base command in ``_BASH_BASE_TO_PAPER`` → that category.
    7. Default → ``OTHER``.
    """
    parsed = _parse_first_command(command)
    if parsed is None:
        return "OTHER"
    cmd_stripped, head, tokens, base_raw, base, rest_lower = parsed

    # 1. SWE-bench helper TEST wrappers.
    if (
        "./run_failing_tests.sh" in cmd_stripped
        or "./run_all_tests.sh" in cmd_stripped
        or base_raw in ("./run_failing_tests.sh", "./run_all_tests.sh")
        or base in ("run_failing_tests.sh", "run_all_tests.sh")
    ):
        return "TEST"

    # 1b. Hunk4J / Defects4J helper TEST wrappers.
    if (
        "./run_bug_exposing_tests.sh" in cmd_stripped
        or "./run_all_tests_trace.sh" in cmd_stripped
        or base_raw in ("./run_bug_exposing_tests.sh", "./run_all_tests_trace.sh")
        or base in ("run_bug_exposing_tests.sh", "run_all_tests_trace.sh")
    ):
        return "TEST"

    # 1c. ``defects4j <subcommand>`` — Hunk4J-specific. Mirrors the
    # Defects4J categorizer's CATEGORIES table:
    #   defects4j compile → BUILD
    #   defects4j test    → TEST
    #   defects4j <other> → BENCHMARK_OTHER (unified bucket for harness
    #                       commands not in compile/test — same name
    #                       SWE-bench uses for its analogue)
    if base == "defects4j":
        sub = tokens[1].lower() if len(tokens) >= 2 else ""
        if sub == "compile":
            return "BUILD"
        if sub == "test":
            return "TEST"
        return "BENCHMARK_OTHER"

    # 1d. Maven / Gradle / Ant — Java build tools used by Hunk4J. ``mvn
    # test`` and ``gradle test`` are TEST; the install/compile/package
    # verbs are BUILD; anything else falls into BUILD as well (per the
    # Defects4J categorizer, which lumps these under BUILD).
    if base in {"mvn", "gradle", "gradlew", "ant"}:
        sub = tokens[1].lower() if len(tokens) >= 2 else ""
        if sub == "test" or "test" in rest_lower.split():
            # Distinguish ``mvn test`` (TEST) from ``mvn -Dtest=Foo install`` etc.
            if sub == "test":
                return "TEST"
        return "BUILD"

    # 1e. Java toolchain executables → BUILD.
    if base in {"javac", "javap", "jar", "java"}:
        return "BUILD"

    # 2. Repo-shipped test runners (basename-anchored, path-tolerant).
    if base in {"runtests.py", "test"} and base_raw.endswith(("runtests.py", "bin/test")):
        return "TEST"
    if base == "manage.py" and tokens[1:] and tokens[1].lower() == "test":
        return "TEST"

    # 3. Git → VCS (one bucket per Q4).
    if base == "git":
        return "VCS"

    # 4. Python interpreters.
    if base in {"python", "python2", "python3", "py", "ipython"}:
        if _is_python_test_invocation(tokens):
            return "TEST"
        # ``python <path>/runtests.py ...`` and ``python ./manage.py test ...``
        # also count as tests.
        for tok in tokens[1:]:
            if tok.startswith("-"):
                continue
            tok_base = tok.rsplit("/", 1)[-1].lower()
            if tok_base == "runtests.py" or tok.endswith("bin/test"):
                return "TEST"
            if tok_base == "manage.py":
                idx = tokens.index(tok) + 1
                while idx < len(tokens) and tokens[idx].startswith("-"):
                    idx += 1
                if idx < len(tokens) and tokens[idx].lower() == "test":
                    return "TEST"
            break
        return "SCRIPT"

    # 5. Package install (pip/conda/mamba). Per Q5a, install verbs → BUILD;
    # read-only ``pip list`` / ``conda info`` → UTIL.
    if base in {"pip", "pip2", "pip3"}:
        if any(verb in rest_lower for verb in ("install", "uninstall", "download")):
            return "BUILD"
        return "UTIL"
    if base in {"conda", "mamba", "micromamba"}:
        if any(verb in rest_lower for verb in ("install", "create", "update", "remove", "uninstall")):
            return "BUILD"
        return "UTIL"

    # 6. Static base-command table.
    if base in _BASH_BASE_TO_PAPER:
        return _BASH_BASE_TO_PAPER[base]

    # 7. Default.
    return "OTHER"


def categorize_action(tool_name: str, command: str = "") -> str:
    """Return one of the 16 paper categories (or ``OTHER``) for one tool call.

    Parameters
    ----------
    tool_name:
        The Claude Code tool name as it appears in the trajectory
        ``tool_use`` event (e.g. ``"Read"``, ``"Edit"``, ``"Bash"``).
    command:
        For ``tool_name == "Bash"``, the ``input.command`` field of the
        tool call. Ignored for native tools.

    Returns
    -------
    One of :data:`PAPER_CATEGORIES`.

    This is the function downstream paper-aligned analyses
    (Table 14, Figs 9-10) should call. It unifies native-tool calls
    and shell invocations under one functional taxonomy that mirrors
    the Defects4J pipeline's :class:`CommandCategorizer`.
    """
    if tool_name == "Bash":
        return _bash_to_paper_category(command)
    return _NATIVE_TOOL_CATEGORY.get(tool_name, "OTHER")


__all__ = [
    "categorize_command",
    "categorize_action",
    "PAPER_CATEGORIES",
]
