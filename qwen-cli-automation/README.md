# Qwen Code CLI for Multi-hunk Program Repair Evaluation

## Environment Setup

### 1. Conda Environment

Create and activate a conda environment from the provided specification (Python 3.11):

```bash
conda env create -f environment.yml
conda activate qwen-code-env
```

### 2. Java Version Configuration

Set Java 8 before execution (required for Defects4J):

```bash
sdk use java 8.0.412-amzn
```

### 3. External Dependencies

Ensure the following tools are installed and accessible:
- `defects4j` (Defects4J framework)
- `qwen` (Qwen Code CLI binary)
- `git`

## Execution

Run the script with default parameters:

```bash
python automated_qwen_code.py
```

### Key Parameters

- `--workspace`: Bug checkout directory (default: `./workspace`)
- `--env-file`: Path to `.env` file (default: `./.env`)
- `--meta-json`: Metadata file path (default: `./config/multihunk.json`)
- `--base-prompt`: Base prompt template (default: `./prompts/prompt.md`)
- `--qwen-bin`: Qwen Code CLI binary (default: `qwen`)
- `--duration-min`: Timeout per bug in minutes (default: 30)
- `--results-base`: Output directory for results (default: `./results`)
- `--only`: Process specific bugs (e.g., `--only Chart_2 Lang_5`)

## Output

The script generates the following artifacts per bug in `workspace/{project}_{bug_id}/logs/`:

1. **CSV Results** (`results/test_results_run_{run}.csv`): Compilation status, test outcomes, failed test cases, and execution duration per bug
2. **Patches** (`logs/patch-{timestamp}.diff`): Generated patches for source code modifications
3. **Telemetry** (`logs/qwen-{timestamp}.json`): Execution traces and model interactions
4. **Console Logs** (`logs/run-{timestamp}.log`): Runtime command output
5. **Progress Tracking** (`config/processed_qwen.json`): Processed bug identifiers

## Collecting Logs

To collect all logs from workspace into a single directory:

```bash
python collect_logs_qwen_code.py
```

This creates `collected-qwen-code-logs/` containing all bug logs organized by bug identifier. The script verifies that each bug has the required files (`qwen-*.json`, `run-*.log`, `patch-*.diff`) and reports any missing files.
