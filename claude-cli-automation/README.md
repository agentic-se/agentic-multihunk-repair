# Claude CLI Automation for Defects4J

Run Claude Code on Defects4J bugs automatically.

## Environment Setup

### 1. Conda Environment

Create and activate a conda environment from the provided specification (Python 3.11):

```bash
conda env create -f environment.yml
conda activate claude-cli-env
```

### 2. Java 8

```bash
sdk use java 8.0.412-amzn
```

### 3. External Dependencies

- **claude** - [Claude Code CLI](https://docs.claude.com/en/docs/claude-code/installation)
- **defects4j** - [Defects4J framework](https://github.com/rjust/defects4j)
- **git**

## Usage

```bash
./run_with_timeout.sh 5 Chart_25
```

This will:
1. Checkout Chart-25 to `prompts/Chart_25_buggy/`
2. Copy `prompts/prompt.md` to `CLAUDE.md` in bug directory
3. Run Claude CLI with 5-minute timeout
4. Test the fix with `defects4j test`
5. Save results to `results.csv`

## Options

```bash
# Verbose logging
python3 automated_claude_cli.py Chart-25 --verbose

# Multiple bugs
python3 automated_claude_cli.py Chart_1 Lang_2 Math_3

# Verbose with multiple bugs
python3 automated_claude_cli.py Chart_1 Lang_2 --verbose
```

## Timeout Handling

If a bug processing times out, a status file `.processing-{project}-{bug_id}.json` will be left behind. To recover and record the timeout results:

```bash
python3 recover_timeouts.py
```

This will:
1. Find all orphaned status files
2. Run `defects4j compile` and `defects4j test` on the bug
3. Write results to CSV with actual compile/test status
4. Mark exit code as "TIMEOUT"
5. Clean up status files

## Collecting Logs

After processing bugs, collect all logs, patches, and session data:

```bash
python3 collect_claude_logs.py
```

This will:
1. Collect Claude JSON logs from `prompts/*/claude-logs/`
2. Generate git diff patches for each bug
3. Collect session logs from `claude_code_session_logs/`
4. Organize output in `collected-claude-logs/{bug_name}/`
5. Create `collection_summary.json` with metadata

Output structure:
```
collected-claude-logs/
  csv_16/
    claude-output-20251010-130728.json
    patch-2025-10-30-004200.diff
    506c8ad0-ce89-4c1c-b042-1b865097b7f9.jsonl
  closure_110/
    ...
  collection_summary.json
```
