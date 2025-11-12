# Coding Agents Automation

This document provides an overview of the coding agent automation frameworks included in this repository. Each agent has its own automation pipeline for evaluating Automated Program Repair (APR) capabilities on Defects4J bugs.

## Available Coding Agents

### 1. Claude Code CLI Automation
**Directory:** [`claude-cli-automation/`](claude-cli-automation/)

Automation framework for Claude Code CLI (Anthropic's official coding agent).

**Key Files:**
- `automated_claude_cli.py` - Main automation script
- `collect_claude_logs.py` - Log collection and analysis
- `recover_timeouts.py` - Recover from timeout scenarios
- `run_with_timeout.sh` - Shell wrapper with timeout handling
- [`README.md`](claude-cli-automation/README.md) - Detailed documentation

**Features:**
- Batch processing of Defects4J bugs
- Configurable timeout handling
- Automatic log collection and parsing
- Resume capability from interruptions

---

### 2. Codex CLI Automation
**Directory:** [`codex-cli-automation/`](codex-cli-automation/)

Automation framework for OpenAI Codex CLI.

**Key Files:**
- `automated_codex_cli.py` - Main automation script
- `collect_codex_cli_logs.py` - Log collection utilities
- `prompts/` - Prompt templates directory
- [`README.md`](codex-cli-automation/README.md) - Detailed documentation

**Features:**
- OpenAI Codex integration
- Custom prompt management
- Log parsing and result aggregation
- Configurable evaluation settings

---

### 3. Qwen Code CLI Automation
**Directory:** [`qwen-cli-automation/`](qwen-cli-automation/)

Automation framework for Qwen Code CLI (Alibaba's coding agent).

**Key Files:**
- `automated_qwen_code.py` - Main automation script
- `collect_logs_qwen_code.py` - Log collection utilities
- `prompts/` - Prompt templates directory
- [`README.md`](qwen-cli-automation/README.md) - Detailed documentation

**Features:**
- Qwen Code model integration
- Prompt customization support
- Result tracking and analysis
- Defects4J bug evaluation

---

## MCP (Model Context Protocol) Support

**Directory:** [`progctx-mcp/`](progctx-mcp/)

MCP server implementation for enhanced code analysis capabilities. This is currently in progress and provides additional context to agents during evaluation.

**Key Files:**
- `mcp_server/` - MCP server implementation
- `context/` - Context management utilities
- [`README.md`](progctx-mcp/README.md) - MCP server documentation
- [`README_STDIO.md`](progctx-mcp/README_STDIO.md) - STDIO transport documentation

**Status:** In progress

---

## Common Setup

### Prerequisites
All automation frameworks require:
- Python 3.8+
- Defects4J installed and in PATH
- Respective CLI tool installed (claude, codex, qwen)
- API keys configured (where applicable)

### Environment Setup
Create the conda environment:
```bash
conda env create -f llm-code-repair-env.yml
conda activate llm-code-repair-env
```

### Configuration
Each agent has its own `config/` directory containing:
- Bug metadata JSON
- Processed bugs tracking
- Agent-specific configuration files

---

## Usage Pattern

All automation scripts follow a similar pattern:

```bash
# Run with defaults
python automated_<agent>_cli.py

# Run specific bugs
python automated_<agent>_cli.py --only Chart_2 Lang_5

# Custom timeout
python automated_<agent>_cli.py --duration-min 60

# Resume from specific bug
python automated_<agent>_cli.py --start-from Chart_10

# Debug mode
python automated_<agent>_cli.py --debug
```

---

## Results and Output

Each automation framework produces:
- **CSV Results:** Summary of bug repair attempts
- **Logs:** Detailed execution logs for each bug
- **Patches:** Generated code patches
- **Progress Tracking:** JSON files to resume interrupted runs

Results are typically stored in:
- `results/` - CSV result files
- `logs/` - Per-bug execution logs within workspace directories
- `config/processed_*.json` - Progress tracking files

---

## Additional Resources

### Prompts
- Vanilla agent prompt: [`agentic_ai/prompt.md`](agentic_ai/prompt.md)
- MCP agent prompt: [`agentic_ai/prompt_mcp.md`](agentic_ai/prompt_mcp.md)

### Analysis Tools
- Command statistics: [`agent_command_statistics/`](agent_command_statistics/)
- Bash parsing: [`bash_parser/`](bash_parser/)

---

## Contributing

Each agent directory contains its own README with specific setup and usage instructions. Please refer to the individual documentation for detailed information about each coding agent framework.
