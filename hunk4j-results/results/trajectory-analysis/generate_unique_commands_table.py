#!/usr/bin/env python3
"""
Generate LaTeX table showing unique command counts per agent.

This script analyzes all commands executed by each agent and generates
a table showing:
- Total unique commands
- Native tools vs Bash commands breakdown
- Examples of commands used
"""

import sys
import csv
from pathlib import Path
from collections import defaultdict, Counter

# Add paths
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bash_parser.shell_command_parser import ShellCommandParser

# Agent paths
AGENT_DATA = {
    'Qwen': {
        'tools': '../qwen_code_results/qwen_results/tools_count_qwen.csv',
    },
    'Gemini': {
        'tools': '../gemini_cli_results/tools_count_gemini.csv',
    },
    'Claude': {
        'tools': '../claude_code_results/claude_results/tools_count_claude.csv',
    },
    'Codex': {
        'tools': '../openai_codex_results/results-codex/tools_count_codex.csv',
    },
}

# Tool name normalization
TOOL_NAME_MAP = {
    'Bash': 'run_shell_command',
    'Read': 'read_file',
    'Edit': 'edit',
    'Write': 'write_file',
    'Glob': 'glob',
    'Grep': 'grep',
    'TodoWrite': 'todo_write',
    'WebFetch': 'web_fetch',
    'Task': 'task',
}

def main():
    parser = ShellCommandParser()

    # Store unique commands per agent
    agent_stats = {}

    print("=" * 70)
    print("UNIQUE COMMAND ANALYSIS PER AGENT")
    print("=" * 70)
    print()

    for agent_name, paths in AGENT_DATA.items():
        tools_path = Path(__file__).parent / paths['tools']

        if not tools_path.exists():
            print(f"WARNING: {paths['tools']} not found, skipping {agent_name}")
            continue

        print(f"Processing {agent_name}...")

        # Track unique commands
        unique_native = set()
        unique_bash = set()
        all_commands = set()

        with open(tools_path, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Get tool name (different column names for different agents)
                tool_name = row.get('function_name') or row.get('tool_name', '')
                tool_name = tool_name.strip()
                tool_name = TOOL_NAME_MAP.get(tool_name, tool_name)

                # Get command
                command_str = row['command'].strip() if row['command'] else ''

                # Categorize
                if tool_name == 'run_shell_command' and command_str:
                    try:
                        # Parse bash commands
                        commands = parser.parse_command(
                            command_str, preserve_sequence=False
                        )

                        for cmd in commands:
                            unique_bash.add(cmd)
                            all_commands.add(cmd)
                    except Exception:
                        # Parsing failed, use first word
                        first_word = command_str.split()[0] if command_str.split() else command_str
                        unique_bash.add(first_word)
                        all_commands.add(first_word)
                else:
                    # Native tool
                    unique_native.add(tool_name)
                    all_commands.add(tool_name)

        agent_stats[agent_name] = {
            'total_unique': len(all_commands),
            'native': len(unique_native),
            'bash': len(unique_bash),
            'native_cmds': sorted(unique_native),
            'bash_cmds': sorted(unique_bash)
        }

        print(f"  Total unique commands: {len(all_commands)}")
        print(f"    Native tools: {len(unique_native)}")
        print(f"    Bash commands: {len(unique_bash)}")
        print()

    print("=" * 70)
    print("SUMMARY BY AGENT")
    print("=" * 70)
    print()

    for agent_name in ['Qwen', 'Gemini', 'Codex', 'Claude']:
        if agent_name not in agent_stats:
            continue

        stats = agent_stats[agent_name]
        print(f"{agent_name}:")
        print(f"  Total: {stats['total_unique']}")
        print(f"  Native: {stats['native']} ({stats['native']/stats['total_unique']*100:.1f}%)")
        print(f"  Bash: {stats['bash']} ({stats['bash']/stats['total_unique']*100:.1f}%)")
        print()
        print(f"  Top 5 native tools: {', '.join(stats['native_cmds'][:5])}")
        print(f"  Top 5 bash commands: {', '.join(stats['bash_cmds'][:5])}")
        print()

    # Generate LaTeX table
    print("=" * 70)
    print("LATEX TABLE")
    print("=" * 70)
    print()

    generate_latex_table(agent_stats)

    # Save to file
    output_path = Path(__file__).parent / 'unique_commands_table.txt'
    with open(output_path, 'w') as f:
        f.write(generate_latex_table(agent_stats, to_string=True))

    print(f"\n✅ LaTeX table saved to: {output_path}")


def generate_latex_table(agent_stats, to_string=False):
    """Generate LaTeX table for unique commands."""

    lines = []

    lines.append("\\begin{table}[t]")
    lines.append("\\centering")
    lines.append("\\caption{Unique Command Diversity Across Coding Agents}")
    lines.append("\\label{tab:unique_commands_per_agent}")
    lines.append("\\small")
    lines.append("\\begin{tabular}{lrrr}")
    lines.append("\\toprule")
    lines.append("\\textbf{Agent} & \\textbf{Total Unique} & \\textbf{Native Tools} & \\textbf{Bash Commands} \\\\")
    lines.append("\\midrule")

    # Add rows for each agent
    for agent_name in ['Qwen', 'Gemini', 'Codex', 'Claude']:
        if agent_name not in agent_stats:
            continue

        stats = agent_stats[agent_name]

        # Format agent name
        if agent_name == 'Qwen':
            display_name = "Qwen Code"
        elif agent_name == 'Gemini':
            display_name = "Gemini CLI"
        elif agent_name == 'Codex':
            display_name = "OpenAI Codex"
        elif agent_name == 'Claude':
            display_name = "Claude Code"
        else:
            display_name = agent_name

        lines.append(f"{display_name} & {stats['total_unique']} & {stats['native']} & {stats['bash']} \\\\")

    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")

    table_str = "\n".join(lines)

    if not to_string:
        print(table_str)

    return table_str


if __name__ == '__main__':
    main()
