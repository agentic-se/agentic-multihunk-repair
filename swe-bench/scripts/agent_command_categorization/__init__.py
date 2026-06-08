"""
Agent Command Categorization (SWE-bench)

Categorizes shell commands executed by AI coding agents inside the
SWE-bench Verified Docker evaluation containers. Adapted from the
Defects4J version at ``birch/oak/agent_command_categorization/``.

Two public functions:

:func:`categorize_command` -- maps a *Bash command string* to one of the
seven SWE-bench buckets consumed by the existing ``metrics-claude``
pipeline:

    ``test``, ``python_exec``, ``git_all``, ``package_install``,
    ``file_operations``, ``text_search``, ``other``.

:func:`categorize_action` -- maps an *entire tool call* (native Claude
tools *and* Bash) to one of the 16 paper categories used in the
Defects4J pipeline (and reported in Table 14 / Figs 9-10):

    ``READ``, ``SEARCH_CONTENT``, ``SEARCH_FILES``, ``NAVIGATE``,
    ``WRITE``, ``TRANSFORM``, ``BUILD``, ``TEST``, ``VCS``, ``PATCH``,
    ``FILE_OPS``, ``UTIL``, ``SCRIPT``, ``WEB``, ``BENCHMARK_OTHER``,
    ``ARCHIVE``, plus ``OTHER`` as a fallback.

The two functions answer different questions: ``categorize_command`` is
the legacy SWE-bench grouping used by the wide-CSV columns;
``categorize_action`` is the paper-aligned grouping for behavioral
trajectory analyses.
"""

from .categorizer import (
    PAPER_CATEGORIES,
    categorize_action,
    categorize_command,
)

__all__ = ["categorize_command", "categorize_action", "PAPER_CATEGORIES"]
__version__ = "1.0.0"
