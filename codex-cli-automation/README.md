# OpenAI Codex CLI for Multi-hunk Program Repair Evaluation

## Environment Setup

### 1. Conda Environment

Create and activate a conda environment from the provided specification (Python 3.11):

```bash
conda env create -f environment.yml
conda activate codex-env
```

### 2. Java Version Configuration

Set Java 8 before execution (required for Defects4J):

```bash
sdk use java 8.0.412-amzn
```

### 3. External Dependencies

Ensure the following tools are installed and accessible:
- `defects4j` (Defects4J framework)
- `codex` (OpenAI Codex CLI binary from https://github.com/openai/codex)
- `git`

## Execution

Run the script with default parameters:

```bash
python automated_codex_cli.py
```

### Key Parameters

- `--workspace`: Bug checkout directory (default: `./workspace`)
- `--env-file`: Path to `.env` file (default: `./.env`)
- `--meta-json`: Metadata file path (default: `./config/multihunk.json`)
- `--base-prompt`: Base prompt template (default: `./prompts/prompt.md`)
- `--codex-bin`: OpenAI Codex CLI binary (default: `codex`)
- `--duration-min`: Timeout per bug in minutes (default: 30)
- `--results-base`: Output directory for results (default: `./results`)
- `--only`: Process specific bugs (e.g., `--only Chart_2 Lang_5`)

## Output

The script generates the following artifacts:

1. **CSV Results** (`results/test_results_run_{run}.csv`): Compilation status, test outcomes, and failed test cases per bug
2. **Patches** (`workspace/{bug_id}/logs/patch-{timestamp}.diff`): Generated patches for source code modifications
3. **Session Logs** (`workspace/{bug_id}/logs/codex-session-rollout-{timestamp}.jsonl`): Complete Codex execution traces and model interactions
4. **Console Logs** (`workspace/{bug_id}/logs/run-{timestamp}.log`): Runtime command output
5. **Progress Tracking** (`config/processed_codex.json`): Processed bug identifiers

## Collecting Logs

After execution completes, collect all logs from individual bug directories into a single folder:

```bash
python collect_codex_cli_logs.py
```

This creates a `collected-codex-cli-logs/` directory with the following structure:

```
collected-codex-cli-logs/
├── Chart_2/
│   ├── codex-session-rollout-*.jsonl
│   ├── run-*.log
│   └── patch-*.diff
├── Time_26/
│   └── ...
└── ...
```

Each bug's logs are preserved in separate subdirectories for easy analysis and archival.
