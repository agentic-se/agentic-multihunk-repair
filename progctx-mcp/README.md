# 🍁 MAPLE - Model Context Protocol for Automated Lightweight Repository Context Extraction

This document describes how to run the MAPLE MCP server in SSE (Server-Sent Events) mode and integrate it with Qwen Code for automated Java bug fixing.

## Overview

The SSE version (`java_analysis_server_sse.py`) provides Java code analysis tools through the Model Context Protocol using HTTP-based Server-Sent Events transport. This avoids the STDIO transport issues present in the original implementation.

## Quick Start

### Running the SSE Server Standalone

```bash
python3 mcp_server/java_analysis_server_sse.py --project-path /path/to/java/project
```

The server will:
- Start on port 9900
- Index all Java files in the specified project at startup
- Expose SSE endpoint at `http://localhost:9900/sse`
- Wait for Qwen Code or other MCP clients to connect

### Integration with Automated Qwen Code

The `automated_qwen_code_mcp.py` script automatically manages the SSE server lifecycle:

```bash
cd /Users/nashid/repos/qwen-cli-automation-mcp/qwen-cli-automation
python3 automated_qwen_code_mcp.py --project Chart --bug_id 2 --prompt_file prompts/prompt_mcp.md
```

The automation script will:
1. Start SSE MCP server for the bug's source directory
2. Write `~/.qwen/settings.json` with SSE configuration
3. Run Qwen Code with MCP tools available
4. Stop the SSE server when done

## Configuration

### Qwen Code Settings

The automation script writes the following to `~/.qwen/settings.json`:

```json
{
  "mcpServers": {
    "java-analysis-server": {
      "url": "http://localhost:9900/sse",
      "timeout": 30000
    }
  }
}
```

This configuration:
- Connects to SSE server on port 9900
- Sets 30-second timeout for tool operations
- Automatically reconnects if needed

### Port Configuration

Port 9900 is used to avoid conflicts with:
- Port 8000: Common development servers
- Other MCP servers running concurrently

## Available Maple Tools

Once connected, Qwen Code can use these Java code search tools:

- `maple_find_class(class_name)` - Find class definitions by name
- `maple_find_class_in_file(class_name, file_name)` - Find class in specific file
- `maple_find_method(method_name)` - Find method definitions by name
- `maple_find_method_in_class(method_name, class_name)` - Find method in specific class
- `maple_find_method_in_file(method_name, file_name)` - Find method in specific file
- `maple_find_code(code_snippet)` - Search for code patterns
- `maple_find_code_in_file(code_snippet, file_name)` - Search code in specific file
- `maple_extract_class_skeleton(file_name)` - Get class structure without implementation
- `maple_repo_structure(max_depth)` - View repository structure in tree format

## How Integration Works

### 1. Server Startup

`automated_qwen_code_mcp.py` calls `write_per_bug_qwen_settings()` which:

```python
# Start SSE server with project-specific path
cmd = [PYTHON_BIN, MCP_SCRIPT, "--project-path", str(java_src)]
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(2)  # Allow server to initialize

# Write SSE configuration
settings = {
    "mcpServers": {
        "java-analysis-server": {
            "url": "http://localhost:9900/sse",
            "timeout": 30000
        }
    }
}
cfg_path.write_text(json.dumps(settings, indent=2))
```

The server startup sequence:
1. Parse `--project-path` command-line argument
2. Set global `_project_path` variable
3. **Initialize JavaSearchManager immediately** (index all files)
4. Log initialization statistics (files, classes, methods)
5. Start SSE server on port 9900
6. Wait for connections

### 2. Initialization Details

The SSE server initializes the Java manager **before** serving requests:

```python
# In java_analysis_server_sse.py at startup
global _project_path
_project_path = args.project_path

# Initialize Java manager upfront to index files before serving requests
manager = get_java_manager()
# Logs: "✅ Indexed X files, Y classes, Z methods in N.NNNs"

# Then start serving
mcp.run(transport="sse")
```

This ensures:
- Files are indexed once at startup (not lazily on first request)
- First tool call is fast (no indexing delay)
- Project path is properly passed from command line to JavaSearchManager

### 3. Qwen Code Execution

The Qwen Code CLI:
- Reads `~/.qwen/settings.json`
- Connects to SSE endpoint at startup
- Discovers available Maple tools
- Makes tools available to the LLM agent



### Check Qwen Code Connection

```bash
qwen mcp list
```

Should show:
```
java-analysis-server: Connected
```

## Troubleshooting

### Server Won't Start

**Error:** `Address already in use`
**Solution:** Kill existing server on port 9900:
```bash
lsof -ti:9900 | xargs kill -9
```

### Project Path Not Set

**Error:** `Project path not set. Use --project-path argument`
**Solution:** Always use `--project-path` argument:
```bash
python3 java_analysis_server_sse.py --project-path /path/to/project
```


## Environment Setup

```bash
# Create conda environment
conda env create -f environment.yml
conda activate qwen-code-env

# Verify installations
qwen --version  # Should show 0.0.14+
python3 -c "import fastmcp; print(fastmcp.__version__)"  # Should show 1.20.0+
```

## Complete Example

Run automated bug fixing with MCP:

```bash
# Navigate to automation directory
cd /Users/nashid/repos/qwen-cli-automation-mcp/qwen-cli-automation

# Run with MCP support
python3 automated_qwen_code_mcp.py \
  --project Chart \
  --bug_id 2 \
  --prompt_file prompts/prompt_mcp.md \
  --result_file test_results_run_mcp.csv
```


## MCP with STDIO JSON-RPC
Steps to run MCP server with [STDIO JSON-RPC](./README_STDIO.md).