"""
Bash Command Parser Module

This module provides AST-based bash command parsing utilities for all agents
(Qwen, Gemini, Claude, Codex) in the Oak project.

Author: Research Team
Date: November 6, 2025
Status: Production-ready (validated on 21,652 commands, 100% success rate)
"""

from .shell_command_parser import ShellCommandParser

__all__ = ['ShellCommandParser']
__version__ = '1.0.0'
__author__ = 'Oak Research Team'
