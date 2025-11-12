# Bash Parser

AST-based bash command parser for extracting commands from shell strings.

## Quick Start

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bash_parser import ShellCommandParser

parser = ShellCommandParser()
commands = parser.parse_command("defects4j test && git diff")
print(commands)  # ['defects4j test', 'git diff']
```

## API

**`parse_command(command_string: str, preserve_sequence: bool = True) -> List[str]`**

Extract commands from shell strings with optional sequence preservation.

**Parameters:**
- `command_string` (str): Raw shell command string
- `preserve_sequence` (bool): If True (default), return full sequence with all occurrences.
                             If False, deduplicate while preserving order.

**Examples:**

```python
# Basic usage
parser.parse_command("ls")                    # → ['ls']
parser.parse_command("defects4j test")        # → ['defects4j test']
parser.parse_command("mvn clean && mvn test") # → ['mvn clean', 'mvn test']
parser.parse_command("ls | grep foo")         # → ['ls', 'grep']

# Sequence preservation (default)
parser.parse_command("test && test && grep")
# → ['test', 'test', 'grep']  (full sequence with duplicates)

# Unique commands only
parser.parse_command("test && test && grep", preserve_sequence=False)
# → ['test', 'grep']  (deduplicated, order preserved)
```

**Use cases:**
- `preserve_sequence=True`: Trajectory analysis (understand agent behavior patterns)
- `preserve_sequence=False`: Summary statistics (count unique commands used)

## Installation

```bash
pip install bashlex
```

## Features

✅ AST-based using bashlex
✅ Handles `&&`, `||`, `|`, `;`, redirections, heredocs
✅ Two-token commands: `defects4j test`, `git diff`
✅ 100% validated on 21,652 real commands

## Testing

```bash
python test_shell_command_parser.py  # 43 tests
python comprehensive_validation.py   # Full validation
```

## Files

- `shell_command_parser.py` - Parser
- `test_shell_command_parser.py` - Tests
- `comprehensive_validation.py` - Validation
- `TOSEM_CORRECTNESS_REPORT.md` - Proof of correctness
