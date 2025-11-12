#!/usr/bin/env python3
"""
Shell Command Parser using AST-based approach with bashlex.

This module provides a robust parser for shell commands that uses an AST
(Abstract Syntax Tree) approach instead of fragile text processing. It can
properly extract all commands from complex shell constructs including pipes,
logical operators, command substitution, and more.

Author: Noor Nashid
Date: 2025-11-06
"""

from __future__ import annotations

import logging
from typing import List, Set, Optional
import shlex

try:
    import bashlex
    BASHLEX_AVAILABLE = True
except ImportError:
    BASHLEX_AVAILABLE = False
    logging.warning(
        "bashlex not available. Install with: pip install bashlex\n"
        "Falling back to simple text-based parsing."
    )


class ShellCommandParser:
    """
    Parse shell commands using AST-based approach (bashlex) with fallback.

    This parser extracts individual commands from complex shell command strings,
    properly handling operators like &&, ||, |, ;, and command substitutions.

    For certain commands (like 'defects4j', 'git'), it captures both the base
    command and the subcommand (2 tokens) to provide meaningful semantics.

    Examples:
        >>> parser = ShellCommandParser()
        >>> parser.parse_command("defects4j test && echo done")
        ['defects4j test', 'echo']

        >>> parser.parse_command("ls -la | grep foo")
        ['ls', 'grep']

        >>> parser.parse_command("VAR=$(cat file)")
        ['cat']
    """

    # Commands that require 2 tokens for meaningful semantics
    # e.g., "defects4j test" not just "defects4j"
    TWO_TOKEN_COMMANDS: Set[str] = {
        'defects4j',
        'git',
        'docker',
        'npm',
        'mvn',
        'gradle',
        'cargo',
        'pip',
        'conda',
        'apt',
        'apt-get',
        'yum',
        'brew',
    }

    def __init__(self, use_bashlex: bool = True):
        """
        Initialize the parser.

        Args:
            use_bashlex: If True and bashlex is available, use AST parsing.
                        Otherwise fall back to simple text-based parsing.
        """
        self.use_bashlex = use_bashlex and BASHLEX_AVAILABLE
        if use_bashlex and not BASHLEX_AVAILABLE:
            logging.warning("bashlex requested but not available, using fallback")

    def parse_command(self, command_string: str, preserve_sequence: bool = True) -> List[str]:
        """
        Extract all commands from a shell command string.

        Args:
            command_string: Raw shell command string
            preserve_sequence: If True, return full sequence with all occurrences.
                             If False, deduplicate while preserving order.

        Returns:
            List of normalized command strings (e.g., ["defects4j test", "echo"])

        Examples:
            >>> parser = ShellCommandParser()
            >>> parser.parse_command("defects4j test && cat file || echo fail")
            ['defects4j test', 'cat', 'echo']

            >>> parser.parse_command("test && test && grep", preserve_sequence=True)
            ['test', 'test', 'grep']

            >>> parser.parse_command("test && test && grep", preserve_sequence=False)
            ['test', 'grep']
        """
        if not command_string or not command_string.strip():
            return []

        # Pre-process: remove heredocs before parsing
        # Heredocs cause issues with bashlex and contain content we don't want to parse
        command_string = self._remove_heredocs(command_string)

        if self.use_bashlex:
            try:
                return self._parse_with_bashlex(command_string, preserve_sequence)
            except Exception as e:
                # If bashlex fails, fall back to simple parsing
                logging.debug(f"bashlex parsing failed for '{command_string[:50]}...': {e}")
                return self._parse_fallback(command_string, preserve_sequence)
        else:
            return self._parse_fallback(command_string, preserve_sequence)

    def _remove_heredocs(self, command_string: str) -> str:
        """
        Remove heredoc content from command string.

        Heredocs (<<EOF ... EOF) contain arbitrary content that should not be parsed.
        We remove everything between << DELIMITER and the closing DELIMITER.

        Args:
            command_string: Original command string

        Returns:
            Command string with heredocs removed
        """
        import re

        # Pattern to match heredoc start: << followed by optional - and delimiter
        # Delimiter can be quoted ('EOF', "EOF") or unquoted (EOF)
        heredoc_pattern = r'<<-?\s*(["\']?)(\w+)\1'

        result = command_string
        while True:
            match = re.search(heredoc_pattern, result)
            if not match:
                break

            delimiter = match.group(2)  # The delimiter (e.g., 'EOF')
            start_pos = match.start()

            # Find the closing delimiter on its own line
            # Look for \n<delimiter> or start of string followed by delimiter
            closing_pattern = r'\n' + re.escape(delimiter) + r'(?:\n|$)'
            closing_match = re.search(closing_pattern, result[start_pos:])

            if closing_match:
                # Remove everything from << to the closing delimiter
                end_pos = start_pos + closing_match.end()
                result = result[:start_pos] + result[end_pos:]
            else:
                # No closing delimiter found, remove from << to end
                # Keep the part before <<
                result = result[:start_pos]
                break

        return result.strip()

    def _parse_with_bashlex(self, command_string: str, preserve_sequence: bool = True) -> List[str]:
        """
        Parse command using bashlex AST.

        Args:
            command_string: Raw shell command string
            preserve_sequence: If True, keep full sequence with all occurrences

        Returns:
            List of normalized commands
        """
        commands = []

        try:
            # Parse the command into an AST
            parts = bashlex.parse(command_string)

            # Extract commands from the AST
            for part in parts:
                commands.extend(self._extract_from_node(part))

        except bashlex.errors.ParsingError as e:
            # If parsing fails, try to recover
            logging.debug(f"Parsing error: {e}")
            raise

        # Filter out empty commands
        commands = [cmd for cmd in commands if cmd]

        if preserve_sequence:
            # Return full sequence with all occurrences
            return commands
        else:
            # Deduplicate while preserving order
            seen = set()
            result = []
            for cmd in commands:
                if cmd not in seen:
                    seen.add(cmd)
                    result.append(cmd)
            return result

    def _extract_from_node(self, node) -> List[str]:
        """
        Recursively extract commands from a bashlex AST node.

        Args:
            node: bashlex AST node

        Returns:
            List of command strings
        """
        commands = []

        node_kind = node.kind

        # Command node - the actual command
        if node_kind == 'command':
            cmd = self._extract_command_from_parts(node)
            if cmd:
                commands.append(cmd)

        # Compound command - contains multiple commands (e.g., &&, ||, ;)
        elif node_kind == 'compound':
            if hasattr(node, 'list'):
                for child in node.list:
                    commands.extend(self._extract_from_node(child))

        # List - sequence of commands
        elif node_kind == 'list':
            if hasattr(node, 'parts'):
                for child in node.parts:
                    commands.extend(self._extract_from_node(child))

        # Pipeline - commands connected with |
        elif node_kind == 'pipeline':
            if hasattr(node, 'parts'):
                for child in node.parts:
                    commands.extend(self._extract_from_node(child))

        # Operator nodes (&&, ||, ;) - process both sides
        elif node_kind == 'operator':
            if hasattr(node, 'parts'):
                for child in node.parts:
                    commands.extend(self._extract_from_node(child))

        # Command substitution - $(command) or `command`
        elif node_kind == 'commandsubstitution':
            if hasattr(node, 'command'):
                # The command attribute is a CommandNode, extract from it directly
                commands.extend(self._extract_from_node(node.command))
            # Also check for parts attribute
            elif hasattr(node, 'parts'):
                for child in node.parts:
                    if hasattr(child, 'kind'):
                        commands.extend(self._extract_from_node(child))

        # Assignment nodes (VAR=value) - extract from command substitutions inside
        elif node_kind == 'assignment':
            if hasattr(node, 'parts'):
                for child in node.parts:
                    if hasattr(child, 'kind'):
                        commands.extend(self._extract_from_node(child))

        # For other node types, check if they have parts/children
        elif hasattr(node, 'parts'):
            for child in node.parts:
                if hasattr(child, 'kind'):
                    commands.extend(self._extract_from_node(child))

        return commands

    def _extract_command_from_parts(self, node) -> Optional[str]:
        """
        Extract command string from a command node's parts.

        Args:
            node: bashlex command node

        Returns:
            Normalized command string or None
        """
        if not hasattr(node, 'parts') or not node.parts:
            return None

        tokens = []

        for part in node.parts:
            # Skip redirections
            if hasattr(part, 'kind') and part.kind == 'redirect':
                continue

            # Skip assignment nodes - they're handled separately
            if hasattr(part, 'kind') and part.kind == 'assignment':
                continue

            # Handle word nodes
            if hasattr(part, 'word'):
                word = part.word
                # Skip environment variable assignments
                if '=' in word and not word.startswith('--'):
                    # Check if it looks like VAR=value
                    if word.split('=')[0].isidentifier():
                        continue
                tokens.append(word)

        if not tokens:
            return None

        return self._normalize_command_tokens(tokens)

    def _normalize_command_tokens(self, tokens: List[str]) -> str:
        """
        Normalize command tokens to canonical form.

        For commands in TWO_TOKEN_COMMANDS, returns "base subcommand".
        Otherwise returns just the base command.
        Ignores flags and arguments.

        Args:
            tokens: List of command tokens

        Returns:
            Normalized command string

        Examples:
            >>> parser = ShellCommandParser()
            >>> parser._normalize_command_tokens(['defects4j', 'test', '-t', 'FooTest'])
            'defects4j test'
            >>> parser._normalize_command_tokens(['cat', 'file.txt'])
            'cat'
        """
        if not tokens:
            return ""

        base = tokens[0].lower()

        # Handle path-based commands (e.g., ./script.sh)
        if '/' in base:
            base = base.split('/')[-1]

        # If this is a two-token command and we have a second token
        if base in self.TWO_TOKEN_COMMANDS and len(tokens) > 1:
            subcommand = tokens[1].lower()
            # Skip if second token is a flag
            if not subcommand.startswith('-'):
                return f"{base} {subcommand}"

        return base

    def _parse_fallback(self, command_string: str, preserve_sequence: bool = True) -> List[str]:
        """
        Fallback parser using simple text processing.

        This is used when bashlex is not available or fails.
        It's less robust but handles common cases.

        Args:
            command_string: Raw shell command string
            preserve_sequence: If True, keep full sequence with all occurrences

        Returns:
            List of normalized commands
        """
        commands = []

        # Split by common shell operators
        # Note: This is fragile and doesn't handle nested structures well
        segments = []
        current_segment = command_string

        # Split by operators, handling them one at a time
        for delimiter in ['&&', '||', ';', '|']:
            new_segments = []
            for seg in [current_segment] if not segments else segments:
                new_segments.extend(seg.split(delimiter))
            segments = new_segments

        # Process each segment
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue

            # Try to extract base command
            cmd = self._extract_base_command_fallback(segment)
            if cmd:
                if preserve_sequence:
                    # Add every occurrence
                    commands.append(cmd)
                else:
                    # Only add if not already present
                    if cmd not in commands:
                        commands.append(cmd)

        return commands

    def _extract_base_command_fallback(self, segment: str) -> Optional[str]:
        """
        Extract base command from a segment using simple parsing.

        Args:
            segment: Command segment

        Returns:
            Normalized command or None
        """
        segment = segment.strip()
        if not segment:
            return None

        # Try to tokenize
        try:
            tokens = shlex.split(segment)
        except ValueError:
            # If shlex fails, use simple split
            tokens = segment.split()

        if not tokens:
            return None

        # Skip environment variable assignments
        idx = 0
        while idx < len(tokens):
            token = tokens[idx]
            # Check if it's an assignment (VAR=value)
            if '=' in token and not token.startswith('--'):
                parts = token.split('=', 1)
                if parts[0].isidentifier():
                    idx += 1
                    continue
            break

        if idx >= len(tokens):
            return None

        return self._normalize_command_tokens(tokens[idx:])

    def categorize_command(self, command: str) -> str:
        """
        Categorize a command into logical groups.

        DEPRECATED: This method is now a thin wrapper around the categorizer module.
        For new code, use: from agent_command_categorization import categorize_command

        Args:
            command: Normalized command string

        Returns:
            Category name

        Examples:
            >>> parser = ShellCommandParser()
            >>> parser.categorize_command("defects4j test")
            'defects4j_test'
        """
        # Import here to avoid circular dependency
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

        try:
            from agent_command_categorization import categorize_command as _categorize
            return _categorize(command)
        except ImportError:
            # Fallback if categorization module not available
            return 'other'


def main():
    """Demo/test function."""
    parser = ShellCommandParser()

    test_commands = [
        "defects4j test",
        "defects4j test && echo done",
        "defects4j test -t FooTest::testBar && defects4j compile",
        "ls -la | grep foo",
        "cat file || echo error",
        "VAR=$(cat /tmp/file)",
        "git diff > output.txt",
        "ant clean && ant compile.test && defects4j test",
        "defects4j test -t org.apache.commons.cli.BasicParserTest::testPropertyOptionGroup && defects4j test -t org.apache.commons.cli.BasicParserTest::testPropertyOptionUnexpected",
    ]

    print("Shell Command Parser Demo")
    print("=" * 80)
    print(f"Using bashlex: {parser.use_bashlex}")
    print()

    for cmd in test_commands:
        result = parser.parse_command(cmd)
        print(f"Input:  {cmd}")
        print(f"Output: {result}")
        print()


if __name__ == '__main__':
    main()
