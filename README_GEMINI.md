## Running gemini-cli

This script batch-runs Gemini CLI APR (Automated Program Repair) for bugs from Defects4J.

### Prerequisites

- Defects4J installed and available in PATH
- Gemini CLI installed (default binary name: `gemini`)
- Python dependencies: standard library modules
- `.env` file with `GEMINI_API_KEY`

### Creating Conda Environments
- To create the conda environment necessary to run the project, run the following command:
- `conda env create -f llm-code-repair-env.yml`

### Basic Usage

```bash
python automated_gemini-cli.py
```

### Command-line Arguments

- `--model` - Model name (default: `gemini-2.5-flash`)
- `--workspace` - Directory to checkout bugs (default: `~/Desktop/example_dir`)
- `--env-file` - Path to .env file with GEMINI_API_KEY (default: `./.env`)
- `--meta-json` - Path to bug metadata JSON (default: `./config/50_random_bugs_final_tosem.json`)
- `--base-prompt` - Path to base prompt template with `{{bug_title}}` and `{{bug_description}}` placeholders (default: `./agentic_ai/prompt.md`)
- `--gemini-bin` - Gemini CLI binary path (default: `gemini`)
- `--duration-min` - Per-bug timeout in minutes (default: `30`)
- `--results-base` - Directory to store CSV results (default: `./results`)
- `--mode` - Tag for results CSV filename (default: `4`)
- `--only` - Process only specific bugs (e.g., `--only Chart_2 Lang_5`)
- `--start-from` - Start from a specific bug key (inclusive)
- `--processed-json` - File storing already processed bugs (default: `./config/processed_gemini.json`)
- `--debug` - Enable debug mode

### Example Commands

```bash
# Run with default settings
python automated_gemini-cli.py

# Run specific bugs only
python automated_gemini-cli.py --only Chart_2 Lang_5

# Run with custom model and timeout
python automated_gemini-cli.py --model gemini-2.0-pro --duration-min 60

# Start from a specific bug
python automated_gemini-cli.py --start-from Chart_10

# Run in debug mode
python automated_gemini-cli.py --debug
```

### Output

- Results are saved to CSV files in the results directory (default: `./results/test_results_mode_{mode}.csv`)
- Logs and patches are saved to `logs/` subdirectories within each bug's workspace
- Progress is tracked in `processed_gemini.json` to allow resuming interrupted runs

## Running automated_gemini-cli_mcp.py

This script is similar to automated_gemini-cli.py but uses MCP (Model Context Protocol) for enhanced code analysis capabilities.

### Prerequisites

- Defects4J installed and available in PATH
- Gemini CLI installed (default binary name: `gemini`)
- Python dependencies: standard library modules
- `.env` file with `GEMINI_API_KEY`
- **MCP server running** (see below)

### Important: Running the MCP Server

**You must start the MCP server in a separate tab/terminal before running this script.**

```bash
# In a separate terminal tab, run the MCP server
python /path/to/progctx-mcp/mcp_server/java_analysis_server.py
```

The script automatically configures the MCP server in `~/.gemini/settings.json` for each bug, pointing to the Java source paths.

### Basic Usage

```bash
python automated_gemini-cli_mcp.py
```

### Command-line Arguments

- `--model` - Model name (default: `gemini-2.5-flash`)
- `--workspace` - Directory to checkout bugs (default: `~/Desktop/example_dir`)
- `--env-file` - Path to .env file with GEMINI_API_KEY (default: `./.env`)
- `--meta-json` - Path to bug metadata JSON (default: `./config/50_random_bugs_final_tosem.json`)
- `--base-prompt` - Path to base prompt template with `{{bug_title}}` and `{{bug_description}}` placeholders (default: `./agentic_ai/prompt_mcp.md`)
- `--gemini-bin` - Gemini CLI binary path (default: `gemini`)
- `--duration-min` - Per-bug timeout in minutes (default: `30`)
- `--results-base` - Directory to store CSV results (default: `./results`)
- `--mode` - Tag for results CSV filename (default: `4`)
- `--only` - Process only specific bugs (e.g., `--only Chart_2 Lang_5`)
- `--start-from` - Start from a specific bug key (inclusive)
- `--processed-json` - File storing already processed bugs (default: `./config/processed_gemini.json`)
- `--debug` - Enable debug mode

### Example Commands

```bash
# Run with default settings
python automated_gemini-cli_mcp.py

# Run specific bugs only
python automated_gemini-cli_mcp.py --only Chart_2 Lang_5

# Run with custom model and timeout
python automated_gemini-cli_mcp.py --model gemini-2.0-pro --duration-min 60

# Start from a specific bug
python automated_gemini-cli_mcp.py --start-from Chart_10

# Run in debug mode
python automated_gemini-cli_mcp.py --debug
```

### Output

- Results are saved to CSV files in the results directory (default: `./results/test_results_mode_{mode}.csv`)
- Logs and patches are saved to `logs/` subdirectories within each bug's workspace
- Progress is tracked in `processed_gemini.json` to allow resuming interrupted runs
- MCP server configuration is automatically written to `~/.gemini/settings.json` for each bug


