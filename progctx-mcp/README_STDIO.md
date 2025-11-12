# 🍁 MAPLE - Model Context Protocol for Automated Lightweight Repository Context Extraction

A Model Context Protocol (MCP) server providing Java code analysis capabilities through AST parsing and intelligent indexing. Built with FastMCP for seamless integration with Claude Code and other MCP clients.


## Installation

```bash
pip install mcp javalang
```

## Available Tools

| Tool Name | Description | Parameters |
|-----------|-------------|------------|
| `maple_find_class` | Locate a class anywhere in codebase | `class_name: str` |
| `maple_find_class_in_file` | Locate a class in specific file | `class_name: str`, `file_name: str` |
| `maple_find_method` | Locate a method anywhere in codebase | `method_name: str` |
| `maple_find_method_in_class` | Locate a method in specific class | `method_name: str`, `class_name: str` |
| `maple_find_method_in_file` | Locate a method in specific file | `method_name: str`, `file_name: str` |
| `maple_find_code` | Search code snippets (±5 lines context) | `code_snippet: str` |
| `maple_find_code_in_file` | Search code in specific file | `code_snippet: str`, `file_name: str` |
| `maple_extract_class_skeleton` | Get class structure with method signatures | `file_name: str` |
| `maple_repo_structure` | View repository tree structure | `max_depth: int` (default: 100) |

## Running the MCP Server

### Command Line Usage

**IMPORTANT:** The `JAVA_PROJECT_PATH` environment variable is **REQUIRED**. The server will not start without it.

#### 1. **Start with Environment Variable**
```bash
# Set Java project path and start server
export JAVA_PROJECT_PATH="/path/to/your/java/project"
python mcp_server/java_analysis_server.py
```

#### 2. **One-liner with Custom Path**
```bash
# Start server with inline environment variable
JAVA_PROJECT_PATH="/path/to/your/java/project" python mcp_server/java_analysis_server.py
```

### Server Configuration

#### Environment Variables
- `JAVA_PROJECT_PATH`: **[REQUIRED]** Absolute path to the Java project to analyze (e.g., `/path/to/project/source`)

#### Server Output Example
```
================================================================================
 🍁 MAPLE - Model Context Protocol for Automated Lightweight Repository Context Extraction
 Java Code Analysis Server
================================================================================
Starting MAPLE (Model Context Protocol for Automated Lightweight Repository Context Extraction)...
Project Path: /path/to/java/project
✅ Java Search Manager initialized successfully!
   📄 Parsed Files: 571
   🏛️  Indexed Classes: 589
   🔧 Indexed Methods: 6621
🎯 MAPLE Server ready and listening on stdio...
```