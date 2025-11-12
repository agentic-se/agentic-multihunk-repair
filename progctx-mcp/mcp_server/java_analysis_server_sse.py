#!/usr/bin/env python3
"""
MAPLE - Model Context Protocol for Automated Lightweight Repository Context Extraction
Java Code Analysis MCP Server

This server provides Java code parsing and analysis capabilities through the MCP protocol.
It uses FastMCP with annotations to define tools for integration with LLM systems like Claude.

Maple is a context-assistance MCP layer that helps you efficiently explore and understand
the project before making code edits. Use Maple tools whenever you need to locate, inspect,
or understand specific code elements in the repository.

Available Tools:
1. maple_find_class - Locate a class anywhere in the codebase (returns class signature)
2. maple_find_class_in_file - Locate a class within a specific file
3. maple_find_method - Locate a method anywhere in the codebase
4. maple_find_method_in_class - Locate a method within a given class
5. maple_find_method_in_file - Locate a method within a specific file
6. maple_find_code - Search for code snippets or keywords (returns ±5 lines of surrounding context)
7. maple_find_code_in_file - Search for code snippets within a specific file
8. maple_extract_class_skeleton - Retrieve the structural outline of a class, including its method signatures
9. maple_repo_structure - View the repository structure in a tree format
"""

import sys
import os
import logging
import time
import argparse
import subprocess
import signal
from datetime import datetime
from typing import Optional

# Add parent directory to path to import context module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from context.search.java_search_manager import JavaSearchManager

# Create an MCP server (use port 9900 for SSE to avoid conflicts)
mcp = FastMCP("MAPLE-Java-Analysis", port=9900)

# Global manager instance
java_manager: Optional[JavaSearchManager] = None
# Global project path (can be set from command-line args)
_project_path: Optional[str] = None

def setup_logging():
    """Set up comprehensive logging for MCP server API calls."""
    log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    os.makedirs(log_dir, exist_ok=True)

    # Create log file with timestamp
    log_file = os.path.join(log_dir, f"mcp_server_{datetime.now().strftime('%Y%m%d')}.log")

    # Configure logger
    logger = logging.getLogger("mcp_server")
    logger.setLevel(logging.INFO)

    # Clear any existing handlers
    logger.handlers.clear()

    # File handler with detailed format
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    # Console handler with simpler format (stderr for MCP protocol compliance)
    console_handler = logging.StreamHandler(sys.stderr)
    console_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Prevent duplicate logs
    logger.propagate = False

    return logger

# Initialize logger
mcp_logger = setup_logging()

def get_java_manager() -> JavaSearchManager:
    """
    Get or initialize the Java search manager.

    The project path can be set via:
    1. --project-path command-line argument (preferred for Qwen Code)
    2. JAVA_PROJECT_PATH environment variable
    """
    global java_manager, _project_path
    if java_manager is None:
        # Check global project path first (set from command-line args)
        project_path = _project_path or os.environ.get('JAVA_PROJECT_PATH')
        if not project_path:
            raise ValueError(
                "Project path not set. Use --project-path argument or "
                "set JAVA_PROJECT_PATH environment variable."
            )
        if not os.path.exists(project_path):
            raise ValueError(
                f"Project path points to non-existent directory: {project_path}"
            )
        java_manager = JavaSearchManager(project_path)
    return java_manager


def log_mcp_request(tool_name: str, **kwargs):
    """Log detailed MCP request information."""
    params_str = ", ".join(f"{k}={repr(v)}" for k, v in kwargs.items())
    mcp_logger.info(f"🚀 MCP REQUEST: {tool_name}({params_str}) - Client invoking Java analysis")


def log_mcp_response(tool_name: str, success: bool, duration: float, result: str, summary: str, **metrics):
    """Log comprehensive MCP response information."""
    status_icon = "✅" if success else "❌"
    status_text = "SUCCESS" if success else "FAILED"

    # Basic response log
    result_size = len(result) if result else 0
    summary_preview = (summary[:100] + "...") if len(summary) > 100 else summary

    base_msg = f"{status_icon} MCP RESPONSE: {tool_name} {status_text} in {duration:.3f}s | Result: {result_size} chars"

    if metrics:
        metrics_str = ", ".join(f"{k}={v}" for k, v in metrics.items())
        base_msg += f" | {metrics_str}"

    mcp_logger.info(base_msg)
    mcp_logger.info(f"📝 SUMMARY: {summary_preview}")

    # Log result content preview (first 200 chars)
    if result and success:
        result_preview = (result[:200] + "...") if len(result) > 200 else result
        # Clean up the preview for logging (remove newlines, excessive spaces)
        result_clean = " ".join(result_preview.split())
        mcp_logger.info(f"📄 RESULT_PREVIEW: {result_clean}")
    elif not success:
        error_preview = (result[:150] + "...") if len(result) > 150 else result
        error_clean = " ".join(error_preview.split())
        mcp_logger.error(f"❌ ERROR_DETAIL: {error_clean}")

    # Add separator for readability
    mcp_logger.info("─" * 80)


# Java Analysis Tools using FastMCP annotations
@mcp.tool()
def maple_find_class(class_name: str) -> str:
    """Locate a class anywhere in the codebase. Returns signature of the class."""
    start_time = time.time()
    log_mcp_request("maple_find_class", class_name=class_name)

    try:
        manager = get_java_manager()
        result, summary, success = manager.search_class(class_name)
        duration = time.time() - start_time

        # Count matches if successful
        match_count = 0
        if success and "Found " in summary:
            try:
                match_count = int(summary.split("Found ")[1].split(" ")[0])
            except (IndexError, ValueError):
                pass

        log_mcp_response("maple_find_class", success, duration, result, summary,
                        matches=match_count, class_searched=class_name)

        status_icon = "✅" if success else "❌"
        response_text = f"{status_icon} Tool: maple_find_class\n"
        response_text += f"Status: {'SUCCESS' if success else 'FAILED'}\n"
        response_text += f"Summary: {summary}\n\n"

        if success:
            response_text += f"Result:\n{result}"
        else:
            response_text += f"Error: {result}"

        return response_text

    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Error executing maple_find_class: {str(e)}"
        log_mcp_response("maple_find_class", False, duration, error_msg, f"Exception: {str(e)}",
                        class_searched=class_name)
        return f"❌ Tool: maple_find_class\nStatus: FAILED\nError: {error_msg}"


@mcp.tool()
def maple_find_class_in_file(class_name: str, file_name: str) -> str:
    """Locate a class within a specific file. Returns signature of the class."""
    start_time = time.time()
    log_mcp_request("maple_find_class_in_file", class_name=class_name, file_name=file_name)

    try:
        manager = get_java_manager()
        result, summary, success = manager.search_class_in_file(class_name, file_name)
        duration = time.time() - start_time

        # Extract metrics
        match_count = 0
        if success and "Found " in summary:
            try:
                match_count = int(summary.split("Found ")[1].split(" ")[0])
            except (IndexError, ValueError):
                pass

        log_mcp_response("maple_find_class_in_file", success, duration, result, summary,
                        matches=match_count, class_searched=class_name, target_file=file_name)

        status_icon = "✅" if success else "❌"
        response_text = f"{status_icon} Tool: maple_find_class_in_file\n"
        response_text += f"Status: {'SUCCESS' if success else 'FAILED'}\n"
        response_text += f"Summary: {summary}\n\n"

        if success:
            response_text += f"Result:\n{result}"
        else:
            response_text += f"Error: {result}"

        return response_text

    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Error executing maple_find_class_in_file: {str(e)}"
        log_mcp_response("maple_find_class_in_file", False, duration, error_msg, f"Exception: {str(e)}",
                        class_searched=class_name, target_file=file_name)
        return f"❌ Tool: maple_find_class_in_file\nStatus: FAILED\nError: {error_msg}"


@mcp.tool()
def maple_find_method(method_name: str) -> str:
    """Locate a method anywhere in the codebase. Returns full implementation of the method."""
    start_time = time.time()
    log_mcp_request("maple_find_method", method_name=method_name)

    try:
        manager = get_java_manager()
        result, summary, success = manager.search_method(method_name)
        duration = time.time() - start_time

        # Extract metrics
        match_count = 0
        file_count = 0
        if success and "Found " in summary:
            try:
                match_count = int(summary.split("Found ")[1].split(" ")[0])
                # Count files if "files" appears in result
                if "files:" in result:
                    file_count = result.count("<file>")
            except (IndexError, ValueError):
                pass

        log_mcp_response("maple_find_method", success, duration, result, summary,
                        matches=match_count, files_searched=file_count, method_searched=method_name)

        status_icon = "✅" if success else "❌"
        response_text = f"{status_icon} Tool: maple_find_method\n"
        response_text += f"Status: {'SUCCESS' if success else 'FAILED'}\n"
        response_text += f"Summary: {summary}\n\n"

        if success:
            response_text += f"Result:\n{result}"
        else:
            response_text += f"Error: {result}"

        return response_text

    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Error executing maple_find_method: {str(e)}"
        log_mcp_response("maple_find_method", False, duration, error_msg, f"Exception: {str(e)}",
                        method_searched=method_name)
        return f"❌ Tool: maple_find_method\nStatus: FAILED\nError: {error_msg}"


@mcp.tool()
def maple_find_method_in_class(method_name: str, class_name: str) -> str:
    """Locate a method within a given class. Returns full implementation of the method."""
    start_time = time.time()
    log_mcp_request("maple_find_method_in_class", method_name=method_name, class_name=class_name)

    try:
        manager = get_java_manager()
        result, summary, success = manager.search_method_in_class(method_name, class_name)
        duration = time.time() - start_time

        # Extract metrics
        match_count = 0
        if success and "Found " in summary:
            try:
                match_count = int(summary.split("Found ")[1].split(" ")[0])
            except (IndexError, ValueError):
                pass

        log_mcp_response("maple_find_method_in_class", success, duration, result, summary,
                        matches=match_count, method_searched=method_name, target_class=class_name)

        status_icon = "✅" if success else "❌"
        response_text = f"{status_icon} Tool: maple_find_method_in_class\n"
        response_text += f"Status: {'SUCCESS' if success else 'FAILED'}\n"
        response_text += f"Summary: {summary}\n\n"

        if success:
            response_text += f"Result:\n{result}"
        else:
            response_text += f"Error: {result}"

        return response_text

    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Error executing maple_find_method_in_class: {str(e)}"
        log_mcp_response("maple_find_method_in_class", False, duration, error_msg, f"Exception: {str(e)}",
                        method_searched=method_name, target_class=class_name)
        return f"❌ Tool: maple_find_method_in_class\nStatus: FAILED\nError: {error_msg}"


@mcp.tool()
def maple_find_method_in_file(method_name: str, file_name: str) -> str:
    """Locate a method within a specific file. Returns full implementation of the method."""
    start_time = time.time()
    log_mcp_request("maple_find_method_in_file", method_name=method_name, file_name=file_name)

    try:
        manager = get_java_manager()
        result, summary, success = manager.search_method_in_file(method_name, file_name)
        duration = time.time() - start_time

        # Extract metrics
        match_count = 0
        if success and "Found " in summary:
            try:
                match_count = int(summary.split("Found ")[1].split(" ")[0])
            except (IndexError, ValueError):
                pass

        log_mcp_response("maple_find_method_in_file", success, duration, result, summary,
                        matches=match_count, method_searched=method_name, target_file=file_name)

        status_icon = "✅" if success else "❌"
        response_text = f"{status_icon} Tool: maple_find_method_in_file\n"
        response_text += f"Status: {'SUCCESS' if success else 'FAILED'}\n"
        response_text += f"Summary: {summary}\n\n"

        if success:
            response_text += f"Result:\n{result}"
        else:
            response_text += f"Error: {result}"

        return response_text

    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Error executing maple_find_method_in_file: {str(e)}"
        log_mcp_response("maple_find_method_in_file", False, duration, error_msg, f"Exception: {str(e)}",
                        method_searched=method_name, target_file=file_name)
        return f"❌ Tool: maple_find_method_in_file\nStatus: FAILED\nError: {error_msg}"


@mcp.tool()
def maple_find_code(code_snippet: str) -> str:
    """Search for code snippets or keywords in the codebase. Returns ±5 lines of surrounding context."""
    start_time = time.time()
    log_mcp_request("maple_find_code", code_snippet=code_snippet[:50] + "..." if len(code_snippet) > 50 else code_snippet)

    try:
        manager = get_java_manager()
        result, summary, success = manager.search_code(code_snippet)
        duration = time.time() - start_time

        # Extract metrics
        match_count = 0
        file_count = 0
        if success and "Found " in summary:
            try:
                match_count = int(summary.split("Found ")[1].split(" ")[0])
                file_count = result.count("<file>")
            except (IndexError, ValueError):
                pass

        log_mcp_response("maple_find_code", success, duration, result, summary,
                        matches=match_count, files_searched=file_count,
                        snippet_length=len(code_snippet))

        status_icon = "✅" if success else "❌"
        response_text = f"{status_icon} Tool: maple_find_code\n"
        response_text += f"Status: {'SUCCESS' if success else 'FAILED'}\n"
        response_text += f"Summary: {summary}\n\n"

        if success:
            response_text += f"Result:\n{result}"
        else:
            response_text += f"Error: {result}"

        return response_text

    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Error executing maple_find_code: {str(e)}"
        log_mcp_response("maple_find_code", False, duration, error_msg, f"Exception: {str(e)}",
                        snippet_length=len(code_snippet))
        return f"❌ Tool: maple_find_code\nStatus: FAILED\nError: {error_msg}"


@mcp.tool()
def maple_find_code_in_file(code_snippet: str, file_name: str) -> str:
    """Search for code snippets within a specific file. Returns matching code with context."""
    start_time = time.time()
    snippet_preview = code_snippet[:50] + "..." if len(code_snippet) > 50 else code_snippet
    log_mcp_request("maple_find_code_in_file", code_snippet=snippet_preview, file_name=file_name)

    try:
        manager = get_java_manager()
        result, summary, success = manager.search_code_in_file(code_snippet, file_name)
        duration = time.time() - start_time

        # Extract metrics
        match_count = 0
        if success and "Found " in summary:
            try:
                match_count = int(summary.split("Found ")[1].split(" ")[0])
            except (IndexError, ValueError):
                pass

        log_mcp_response("maple_find_code_in_file", success, duration, result, summary,
                        matches=match_count, target_file=file_name,
                        snippet_length=len(code_snippet))

        status_icon = "✅" if success else "❌"
        response_text = f"{status_icon} Tool: maple_find_code_in_file\n"
        response_text += f"Status: {'SUCCESS' if success else 'FAILED'}\n"
        response_text += f"Summary: {summary}\n\n"

        if success:
            response_text += f"Result:\n{result}"
        else:
            response_text += f"Error: {result}"

        return response_text

    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Error executing maple_find_code_in_file: {str(e)}"
        log_mcp_response("maple_find_code_in_file", False, duration, error_msg, f"Exception: {str(e)}",
                        target_file=file_name, snippet_length=len(code_snippet))
        return f"❌ Tool: maple_find_code_in_file\nStatus: FAILED\nError: {error_msg}"


@mcp.tool()
def maple_extract_class_skeleton(file_name: str) -> str:
    """Retrieve the structural outline of a class, including its method signatures from a file."""
    start_time = time.time()
    log_mcp_request("maple_extract_class_skeleton", file_name=file_name)

    try:
        manager = get_java_manager()
        result, summary, success = manager.extract_class_skeleton(file_name)
        duration = time.time() - start_time

        # Extract metrics - count classes and methods in skeleton
        class_count = result.count("class ") + result.count("interface ") + result.count("enum ")
        method_count = result.count("public ") + result.count("private ") + result.count("protected ")
        skeleton_lines = len(result.split('\n')) if success else 0

        log_mcp_response("maple_extract_class_skeleton", success, duration, result, summary,
                        target_file=file_name, classes_found=class_count,
                        methods_found=method_count, skeleton_lines=skeleton_lines)

        status_icon = "✅" if success else "❌"
        response_text = f"{status_icon} Tool: maple_extract_class_skeleton\n"
        response_text += f"Status: {'SUCCESS' if success else 'FAILED'}\n"
        response_text += f"Summary: {summary}\n\n"

        if success:
            response_text += f"Result:\n{result}"
        else:
            response_text += f"Error: {result}"

        return response_text

    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Error executing maple_extract_class_skeleton: {str(e)}"
        log_mcp_response("maple_extract_class_skeleton", False, duration, error_msg, f"Exception: {str(e)}",
                        target_file=file_name)
        return f"❌ Tool: maple_extract_class_skeleton\nStatus: FAILED\nError: {error_msg}"


@mcp.tool()
def maple_repo_structure(max_depth: int = 100) -> str:
    """View the repository structure in a tree format."""
    start_time = time.time()
    log_mcp_request("maple_repo_structure", max_depth=max_depth)

    try:
        manager = get_java_manager()
        result, summary, success = manager.get_repo_structure(max_depth)
        duration = time.time() - start_time

        # Count lines in result for metrics
        line_count = len(result.split('\n')) if success else 0

        log_mcp_response("maple_repo_structure", success, duration, result, summary,
                        max_depth=max_depth, tree_lines=line_count)

        status_icon = "✅" if success else "❌"
        response_text = f"{status_icon} Tool: maple_repo_structure\n"
        response_text += f"Status: {'SUCCESS' if success else 'FAILED'}\n"
        response_text += f"Summary: {summary}\n\n"

        if success:
            response_text += f"Repository Structure:\n```\n{result}\n```"
        else:
            response_text += f"Error: {result}"

        return response_text

    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Error executing maple_repo_structure: {str(e)}"
        log_mcp_response("maple_repo_structure", False, duration, error_msg, f"Exception: {str(e)}",
                        max_depth=max_depth)
        return f"❌ Tool: maple_repo_structure\nStatus: FAILED\nError: {error_msg}"


# Initialize Java manager on startup
def initialize_java_manager():
    """Initialize the Java search manager from JAVA_PROJECT_PATH environment variable."""
    global java_manager
    if java_manager is None:
        project_path = os.environ.get('JAVA_PROJECT_PATH')

        mcp_logger.info("Starting MAPLE (Model Context Protocol for Automated Lightweight Repository Context Extraction)...")

        if not project_path:
            error_msg = (
                "❌ INITIALIZATION FAILED - JAVA_PROJECT_PATH environment variable is not set.\n"
                "   Set it in your MCP config file under 'env.JAVA_PROJECT_PATH'.\n"
                "   Example: \"JAVA_PROJECT_PATH\": \"/path/to/your/java/project\""
            )
            mcp_logger.error(error_msg)
            raise ValueError(error_msg)

        if not os.path.exists(project_path):
            error_msg = f"❌ INITIALIZATION FAILED - JAVA_PROJECT_PATH points to non-existent directory: {project_path}"
            mcp_logger.error(error_msg)
            raise ValueError(error_msg)

        mcp_logger.info("🚀 MAPLE SERVER STARTING - Model Context Protocol for Automated Lightweight Repository Context Extraction")
        mcp_logger.info(f"📁 PROJECT PATH: {project_path}")

        try:
            init_start = time.time()
            java_manager = JavaSearchManager(project_path)
            init_duration = time.time() - init_start

            stats = {
                "files": len(java_manager.parsed_files),
                "classes": len(java_manager.class_index),
                "methods": sum(len(methods) for methods in java_manager.class_method_index.values())
            }

            mcp_logger.info("✅ Java Search Manager initialized successfully!")
            mcp_logger.info(f"   📄 Parsed Files: {stats['files']}")
            mcp_logger.info(f"   🏛️  Indexed Classes: {stats['classes']}")
            mcp_logger.info(f"   🔧 Indexed Methods: {stats['methods']}")

            mcp_logger.info(f"✅ INITIALIZATION SUCCESS - {stats['files']} files, {stats['classes']} classes, {stats['methods']} methods indexed in {init_duration:.3f}s")

        except Exception as e:
            mcp_logger.error(f"❌ INITIALIZATION FAILED - Unable to initialize Java Search Manager: {e}")
            raise e

# Don't initialize on import - let it initialize lazily on first tool call
# This allows MCP protocol handshake to complete quickly without the 4-5s indexing delay
# initialize_java_manager()

def run_server(project_path: str):
    """Run the SSE MCP server with the given project path."""
    global _project_path

    # Set module-level project path
    _project_path = project_path
    mcp_logger.info(f"📁 Project path set from command-line: {project_path}")

    mcp_logger.info("=" * 80)
    mcp_logger.info("🍁 MAPLE - Model Context Protocol for Automated Lightweight Repository Context Extraction")
    mcp_logger.info("Java Code Analysis Server (SSE Mode)")
    mcp_logger.info("=" * 80)

    # Initialize Java manager upfront to index files before serving requests
    mcp_logger.info("🚀 Initializing Java Search Manager...")
    try:
        init_start = time.time()
        manager = get_java_manager()
        init_duration = time.time() - init_start

        stats = {
            "files": len(manager.parsed_files),
            "classes": len(manager.class_index),
            "methods": sum(len(methods) for methods in manager.class_method_index.values())
        }

        mcp_logger.info("✅ Java Search Manager initialized successfully!")
        mcp_logger.info(f"   📄 Parsed Files: {stats['files']}")
        mcp_logger.info(f"   🏛️  Indexed Classes: {stats['classes']}")
        mcp_logger.info(f"   🔧 Indexed Methods: {stats['methods']}")
        mcp_logger.info(f"✅ Indexed {stats['files']} files, {stats['classes']} classes, {stats['methods']} methods in {init_duration:.3f}s")
    except Exception as e:
        mcp_logger.error(f"❌ Initialization failed: {e}")
        sys.exit(1)

    # Always run with SSE transport
    mcp_logger.info("🎯 MAPLE SERVER READY - Listening for connections on SSE (port 9900)")
    mcp_logger.info("   SSE endpoint: http://localhost:9900/sse")
    mcp.run(transport="sse")

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="MAPLE Java Analysis MCP Server")
    parser.add_argument(
        "--project-path",
        type=str,
        required=True,
        help="Path to the Java project to analyze"
    )
    args = parser.parse_args()

    # Run server with project path
    run_server(args.project_path)