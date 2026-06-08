#!/usr/bin/env python3
"""
Extract per-bug action-category counts for HunkSWE, in the same 17-bucket
PAPER_CATEGORIES schema that the Hunk4J `tools_count_all_abstracted_*.csv`
files use. Source data is the trajectory log shipped inside every
`swe-bench/<agent>-cli-automation[-mcp]/workspace_docker/<instance>/agent_logs/`.

The categorization itself is delegated to
`swe-bench/scripts/agent_command_categorization/categorizer.py`
(`categorize_action(tool_name, command)`), so this script's job is
purely (a) parse each agent's trajectory format and (b) call the
categorizer once per tool call. Both native-tool calls and shell-exec
calls are unified into the same 17 buckets.

Per-agent trajectory formats:
  - Claude (.jsonl)   : one JSON object per line; tool calls live in
                         `message.content[].type == "tool_use"` with
                         `name` and `input.command` (for Bash).
  - Codex (.jsonl)    : one JSON object per line; shell execs are
                         `msg.type == "exec_command_begin"` with
                         `command` as a list (e.g. ['bash','-lc','<cmd>']).
                         No native tools — everything is Bash.
  - Gemini / Qwen     : OTLP-style telemetry, a stream of concatenated
                         top-level JSON objects. Tool calls are events
                         with `attributes['event.name'] ==
                         '<agent>.tool_call'`, carrying
                         `function_name` and `function_args` (JSON).

Output: per agent + mode, one CSV at
  swe-bench/<agent>-cli-automation[-mcp]/results/
      <tag>_hunkswe_action_counts.csv
with header `instance_id, <17 paper categories...>`.
"""
from __future__ import annotations
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterator

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "swe-bench" / "scripts"))
sys.path.insert(0, str(REPO))
from agent_command_categorization.categorizer import (
    PAPER_CATEGORIES,
    categorize_action,
)
from bash_parser.shell_command_parser import ShellCommandParser

_SHELL_PARSER = ShellCommandParser()


_HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")


def _strip_heredoc_bodies(command: str) -> str:
    """Remove the bodies of any ``<<EOF ... EOF`` heredocs from a shell
    command, keeping just the invocation that uses them. Used by Codex's
    ``apply_patch <<'EOF' ... EOF`` idiom — without stripping, the
    shell-parser walks the heredoc body line-by-line and emits hundreds
    of phantom ``commands`` (``+``, ``-``, ``}``, ``i++)``, ``+import``,
    etc.) that all fall into OTHER. With stripping, the parser sees just
    ``apply_patch`` and classifies it correctly."""
    out = command
    while True:
        m = _HEREDOC_RE.search(out)
        if not m:
            return out
        delim = m.group(2)
        end_re = re.compile(rf"\n\s*{re.escape(delim)}\s*(\n|$)")
        body_start = m.end()
        em = end_re.search(out, body_start)
        if not em:
            # Unterminated heredoc — just keep prefix up to the heredoc opener
            return out[:m.start()].rstrip()
        out = out[:m.start()].rstrip() + " " + out[em.end():]


def _split_atomic(command: str) -> list[str]:
    """Break a compound shell command into atomic commands.

    Mirrors the Defects4J `command_categorizer.categorize_shell_command`
    behavior: a single ``bash -lc "cmd1 && cmd2 && cmd3"`` invocation
    contributes one categorization per atomic sub-command, not just one
    for the head. Both d4j and hunkswe agents chain commands this way
    (especially Codex via ``bash -lc``), so without this split we'd
    silently under-count BUILD / TEST / VCS etc.

    Heredoc bodies are stripped first — see `_strip_heredoc_bodies`."""
    if not command or not command.strip():
        return []
    command = _strip_heredoc_bodies(command)
    try:
        # preserve_sequence=True keeps every atomic command occurrence —
        # one categorization per call, matching the paper's
        # `categorize_shell_command` which iterates over every atom
        # returned by `ShellCommandParser.parse_shell_command`.
        atoms = _SHELL_PARSER.parse_command(command, preserve_sequence=True)
    except Exception:
        atoms = []
    return atoms or [command]

SWE = REPO / "swe-bench"
AGENT_DIRS = {
    ("claude", "vanilla"): SWE / "claude-cli-automation",
    ("codex",  "vanilla"): SWE / "codex-cli-automation",
    ("gemini", "vanilla"): SWE / "gemini-cli-automation",
    ("qwen",   "vanilla"): SWE / "qwen-cli-automation",
    ("gemini", "mcp"):     SWE / "gemini-cli-automation-mcp",
    ("qwen",   "mcp"):     SWE / "qwen-cli-automation-mcp",
}
GLOB = {
    "claude": "claude-trajectory-*.jsonl",
    "codex":  "codex-trajectory-*.jsonl",
    "gemini": "gemini-telemetry-*.json",
    "qwen":   "qwen-telemetry-*.json",
}


# -------------------------------------------------------------------------
# Per-agent trajectory parsers — yield (tool_name, command) per tool call.
# `tool_name == "Bash"` is the categorizer's convention for shell execs;
# every concrete native-tool name (Read / Edit / read_file / replace / ...)
# is passed through as-is.
# -------------------------------------------------------------------------

def claude_tool_calls(jsonl: Path) -> Iterator[tuple[str, str]]:
    for line in jsonl.open(errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "assistant":
            continue
        msg = obj.get("message", {})
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "tool_use":
                continue
            name = item.get("name") or ""
            cmd = (item.get("input") or {}).get("command", "") if name == "Bash" else ""
            yield name, cmd


def codex_tool_calls(jsonl: Path) -> Iterator[tuple[str, str]]:
    """Codex uses shell-only. Handles two JSONL schemas in the wild:

    A) HunkSWE schema (newer Codex CLI, e.g. 0.21.0+):
       `msg.type == "exec_command_begin"` with `msg.command` as a list
       like ['bash','-lc','<actual cmd>'].

    B) Hunk4J schema (older session-rollout format):
       `type == "function_call"`, `name == "shell"`, `arguments` is a
       JSON string with `{"command": ["bash","-lc","<actual cmd>"]}`.

    Both forms yield ("Bash", <bash cmd string>) for the categorizer."""
    for line in jsonl.open(errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        cmd_list = None
        msg = obj.get("msg")
        if isinstance(msg, dict) and msg.get("type") == "exec_command_begin":
            cmd_list = msg.get("command")
        elif obj.get("type") == "function_call" and obj.get("name") == "shell":
            raw = obj.get("arguments", "")
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                    cmd_list = parsed.get("command") if isinstance(parsed, dict) else None
                except json.JSONDecodeError:
                    cmd_list = None

        if cmd_list is None:
            continue
        if isinstance(cmd_list, list) and cmd_list:
            # Common form: ["bash", "-lc", "<bash cmd>"]  → take the last
            # element as the shell-to-parse.
            # Apply-patch form: ["apply_patch", "<patch body>"]  → don't
            # parse the body; the whole thing is one atomic apply_patch
            # invocation, which the categorizer routes to PATCH/WRITE.
            head = cmd_list[0] if isinstance(cmd_list[0], str) else ""
            if head in {"bash", "sh", "zsh", "fish"}:
                cmd = cmd_list[-1] if isinstance(cmd_list[-1], str) else " ".join(map(str, cmd_list))
            else:
                # Treat as `<head> ...` so the categorizer sees just the
                # head executable (apply_patch, sed, python, etc.).
                cmd = head
        elif isinstance(cmd_list, str):
            cmd = cmd_list
        else:
            cmd = ""
        yield "Bash", cmd


def _otlp_objects(path: Path) -> Iterator[dict]:
    decoder = json.JSONDecoder()
    text = path.read_text(errors="replace")
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n":
            i += 1
        if i >= n:
            return
        try:
            obj, end = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            return
        yield obj
        i = end


def otlp_tool_calls(path: Path, event_name: str) -> Iterator[tuple[str, str]]:
    """Gemini / Qwen telemetry: tool_call events.
    The categorizer expects tool_name == "Bash" for shell calls; we
    translate `run_shell_command` accordingly and extract the command
    from `function_args` JSON."""
    for obj in _otlp_objects(path):
        if not isinstance(obj, dict):
            continue
        attrs = obj.get("attributes")
        if not isinstance(attrs, dict):
            continue
        if attrs.get("event.name") != event_name:
            continue
        fname = attrs.get("function_name") or ""
        raw_args = attrs.get("function_args", "")
        cmd = ""
        if fname == "run_shell_command":
            if isinstance(raw_args, str):
                try:
                    parsed = json.loads(raw_args)
                except json.JSONDecodeError:
                    parsed = None
            else:
                parsed = raw_args
            if isinstance(parsed, dict):
                cmd = parsed.get("command", "") or parsed.get("cmd", "") or ""
            fname = "Bash"  # so categorize_action treats it as a shell call
        yield fname, cmd


EVENT_NAME = {"gemini": "gemini_cli.tool_call", "qwen": "qwen-code.tool_call"}


def iter_tool_calls(agent: str, log_path: Path) -> Iterator[tuple[str, str]]:
    if agent == "claude":
        yield from claude_tool_calls(log_path)
    elif agent == "codex":
        yield from codex_tool_calls(log_path)
    else:
        yield from otlp_tool_calls(log_path, EVENT_NAME[agent])


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main() -> None:
    for (agent, mode), agent_dir in AGENT_DIRS.items():
        ws = agent_dir / "workspace_docker"
        if not ws.is_dir():
            print(f"  MISSING workspace: {ws}")
            continue
        tag = agent if mode == "vanilla" else f"{agent}_mcp"
        out_csv = agent_dir / "results" / f"{tag}_hunkswe_action_counts.csv"
        out_csv.parent.mkdir(parents=True, exist_ok=True)

        per_bug: dict[str, Counter] = {}
        for inst_dir in sorted(p for p in ws.iterdir() if p.is_dir()):
            iid = inst_dir.name
            logs = sorted((inst_dir / "agent_logs").glob(GLOB[agent]))
            if not logs:
                per_bug[iid] = Counter()
                continue
            counts: Counter = Counter()
            for tool_name, cmd in iter_tool_calls(agent, logs[-1]):
                if tool_name in ("Bash", "run_shell_command") and cmd:
                    # Split compound shell commands into atomic ones and
                    # categorize each separately (matches the d4j paper's
                    # `categorize_shell_command` behavior).
                    for atom in _split_atomic(cmd):
                        counts[categorize_action("Bash", atom)] += 1
                else:
                    counts[categorize_action(tool_name, cmd)] += 1
            per_bug[iid] = counts

        with out_csv.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["instance_id"] + list(PAPER_CATEGORIES))
            for iid in sorted(per_bug):
                w.writerow([iid] + [per_bug[iid].get(c, 0) for c in PAPER_CATEGORIES])

        total_calls = sum(sum(c.values()) for c in per_bug.values())
        print(f"  {agent}/{mode}: {len(per_bug)} instances, "
              f"{total_calls} tool calls categorized -> {out_csv.name}")


if __name__ == "__main__":
    main()
