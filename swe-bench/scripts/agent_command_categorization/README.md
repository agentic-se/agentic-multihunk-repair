# Agent Command Categorization (SWE-bench)

Categorization logic for shell commands executed by AI coding agents
inside SWE-bench Verified Docker evaluation containers.

Adapted from the Defects4J version at
`~/Desktop/birch/oak/agent_command_categorization/`. The Defects4J
buckets (`defects4j_compile`, `defects4j_test`, `build_and_execution`
for `mvn`/`gradle`/`ant`/`java`, ...) were retargeted to the
Python/`pytest` world that every SWE-bench instance lives in.

## Buckets

| Bucket            | Examples                                              |
| ----------------- | ----------------------------------------------------- |
| `test`            | `pytest -q`, `python -m pytest tests/test_x.py`,      |
|                   | `python -m unittest`, `nosetests`, `tox`, `coverage`, |
|                   | `./run_failing_tests.sh`, `./run_all_tests.sh`,       |
|                   | `./tests/runtests.py …` (Django), `bin/test` (sympy), |
|                   | `./manage.py test …` (Django alt)                     |
| `python_exec`     | `python repro.py`, `python -c "..."`, `python3 -V`    |
| `git_all`         | every `git` invocation (diff, log, status, apply, …)  |
| `package_install` | `pip install …`, `conda install …`, `mamba create …`  |
| `file_operations` | `rm`, `mkdir`, `cp`, `mv`, `ls`, `chmod`, `touch`     |
| `text_search`     | `grep`, `rg`, `ag`, `find`, `which`                   |
| `other`           | everything else (`cat`, `sed`, `awk`, `cd`, `echo`, …)|

The bucket names are used verbatim as `Bash_<bucket>` columns by the
metric scripts in `swe-bench/scripts/metrics-<agent>/`, so they must
not be renamed in isolation.

## Usage

```python
from agent_command_categorization import categorize_command

categorize_command("pytest -q tests/test_units.py")  # → 'test'
categorize_command("python -m pytest -x")            # → 'test'
categorize_command("./run_failing_tests.sh")         # → 'test'
categorize_command("./tests/runtests.py -v 2")       # → 'test'
categorize_command("python repro.py")                # → 'python_exec'
categorize_command("git diff HEAD")                  # → 'git_all'
categorize_command("pip install scipy")              # → 'package_install'
categorize_command("rg 'def foo' src/")              # → 'text_search'
categorize_command("ls -la")                         # → 'file_operations'
categorize_command("cat README.md")                  # → 'other'
```

## Why a separate module?

Same separation as the Defects4J side:

* **Parsing** (`bash_parser/`) extracts commands from raw shell strings.
* **Categorization** (this module) groups them for research analysis.

Keeping the two apart lets us adjust the SWE-bench bucket set without
touching the AST-based parser or the metric scripts beyond a one-line
import swap.
