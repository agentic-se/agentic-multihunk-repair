# search_utils.py

import ast
import glob
import pathlib
import re
from dataclasses import dataclass
from os.path import join as pjoin
from typing import Optional, List, Tuple

@dataclass
class SearchResult:
    """Dataclass to hold search results."""
    file_path: str  # this is an absolute path
    class_name: Optional[str]
    func_name: Optional[str]
    code: str

    def to_tagged_upto_file(self, project_root: str) -> str:
        """Converts the search result to a tagged string up to the file path."""
        rel_path = self.file_path[len(project_root) + 1:]
        return f"<file>{rel_path}</file>"

    def to_tagged_upto_class(self, project_root: str) -> str:
        """Converts the search result to a tagged string up to the class level."""
        return f"{self.to_tagged_upto_file(project_root)}\n<class>{self.class_name}</class>" if self.class_name else self.to_tagged_upto_file(project_root)

    def to_tagged_upto_func(self, project_root: str) -> str:
        """Converts the search result to a tagged string up to the function level."""
        func_part = f" <func>{self.func_name}</func>" if self.func_name else ""
        return f"{self.to_tagged_upto_class(project_root)}{func_part}"

    def to_tagged_str(self, project_root: str) -> str:
        """Converts the search result to a full tagged string including code."""
        return f"{self.to_tagged_upto_func(project_root)}\n<code>\n{self.code}\n</code>"

    @staticmethod
    def collapse_to_file_level(results: List['SearchResult'], project_root: str) -> str:
        """Collapses search results to show a summary at the file level."""
        file_counts = {}
        for result in results:
            file_counts[result.file_path] = file_counts.get(result.file_path, 0) + 1
        summary = ""
        for file_path, count in file_counts.items():
            rel_path = file_path[len(project_root) + 1:]
            summary += f"- <file>{rel_path}</file> ({count} matches)\n"
        return summary

    @staticmethod
    def collapse_to_method_level(results: List['SearchResult'], project_root: str) -> str:
        """Collapses search results to show a summary at the method level."""
        summary_dict = {}
        for result in results:
            key = (result.file_path, result.func_name or "Not in a function")
            summary_dict[key] = summary_dict.get(key, 0) + 1
        summary = ""
        for (file_path, func_name), count in summary_dict.items():
            rel_path = file_path[len(project_root) + 1:]
            func_part = f" <func>{func_name}</func>" if func_name != "Not in a function" else func_name
            summary += f"- <file>{rel_path}</file>{func_part} ({count} matches)\n"
        return summary

def find_python_files(dir_path: str) -> List[str]:
    """Recursively finds all .py files in a directory, excluding some known non-source directories."""
    excluded_dirs = {"build", "doc", "requests/packages", "tests/regrtest_data", "tests/input"}
    py_files = glob.glob(pjoin(dir_path, "**/*.py"), recursive=True)
    return [file for file in py_files if not any(part in file for part in excluded_dirs)]

def parse_python_file(file_path: str) -> Optional[Tuple[List, dict, List]]:
    """Parses a Python file to extract classes and functions."""
    try:
        with open(file_path, "r") as f:
            file_content = f.read()
        tree = ast.parse(file_content)
    except Exception:
        return None

    classes = []
    class_to_funcs = {}
    top_level_funcs = []

    function_nodes_in_class = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append((node.name, node.lineno, node.end_lineno or node.lineno))
            class_to_funcs[node.name] = [(func.name, func.lineno, func.end_lineno or func.lineno)
                                         for func in node.body if isinstance(func, ast.FunctionDef)]
        elif isinstance(node, ast.FunctionDef) and node not in function_nodes_in_class:
            top_level_funcs.append((node.name, node.lineno, node.end_lineno or node.lineno))

    return classes, class_to_funcs, top_level_funcs

def get_code_region_containing_code(file_path: str, code_str: str) -> List[Tuple[int, str]]:
    """Finds regions in the file containing a specific code string."""
    with open(file_path, "r") as f:
        file_content = f.read()

    occurrences = []
    file_lines = file_content.splitlines()
    for match in re.finditer(re.escape(code_str), file_content):
        start_line = file_content.count("\n", 0, match.start())
        context = "\n".join(file_lines[max(0, start_line - 3):start_line + 4])
        occurrences.append((start_line, context))
    return occurrences

def get_func_snippet_with_code_in_file(file_path: str, code_str: str) -> List[str]:
    """Finds and extracts function code containing a specified string."""
    with open(file_path, "r") as f:
        file_content = f.read()
    tree = ast.parse(file_content)
    snippets = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func_code = get_code_snippets(file_path, node.lineno, node.end_lineno or node.lineno)
            if code_str in func_code.replace("\n", " "):
                snippets.append(func_code)
    return snippets

def get_code_snippets(file_path: str, start: int, end: int) -> str:
    """Extracts lines of code from start to end in a file."""
    with open(file_path, "r") as f:
        lines = f.readlines()
    return "".join(lines[start - 1:end])

def extract_func_sig_from_ast(func_ast: ast.FunctionDef) -> List[int]:
    """Extracts the function signature lines from an AST FunctionDef node."""
    start_line = func_ast.lineno
    end_line = func_ast.body[0].lineno - 1 if func_ast.body else func_ast.end_lineno
    return list(range(start_line, end_line))

def extract_class_sig_from_ast(class_ast: ast.ClassDef) -> List[int]:
    """Extracts the class signature lines from an AST ClassDef node."""
    start_line = class_ast.lineno
    end_line = class_ast.body[0].lineno - 1 if class_ast.body else class_ast.end_lineno
    return list(range(start_line, end_line))

def get_class_signature(file_path: str, class_name: str) -> str:
    """Returns the class signature for a specified class name."""
    with open(file_path, "r") as f:
        file_content = f.read()
    tree = ast.parse(file_content)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            sig_lines = extract_class_sig_from_ast(node)
            return "\n".join(file_content.splitlines()[line - 1] for line in sig_lines)
    return ""


def extract_class_skeleton(file_path: str) -> str:
    """
    Extract the skeleton of all top-level classes in a Python file: each class
    signature plus each method's def line (signature only, body elided to '...').
    Top-level import statements and class/method decorators are preserved.

    Mirrors the structure of progctx-mcp-d4j's java_search_utils.extract_class_skeleton,
    adapted for Python syntax (no modifiers, interfaces, enums, throws, or field
    declarations). Nested classes are not emitted (only top-level ClassDef nodes
    are walked).
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        return f"Error reading file: {e}"

    try:
        tree = ast.parse(content)
    except Exception as e:
        return f"Error parsing Python file: {e}"

    source_lines = content.splitlines()
    skeleton_parts: List[str] = []

    def emit_range(start: int, end: int) -> None:
        for line_no in range(start, end + 1):
            skeleton_parts.append(source_lines[line_no - 1])

    # Top-level imports
    has_imports = False
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            emit_range(node.lineno, node.end_lineno or node.lineno)
            has_imports = True
    if has_imports:
        skeleton_parts.append("")

    # Top-level classes
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            # Class decorators
            for dec in node.decorator_list:
                emit_range(dec.lineno, dec.end_lineno or dec.lineno)

            # Class signature: from `class Foo(...):` line through colon
            class_sig_end = node.body[0].lineno - 1 if node.body else (node.end_lineno or node.lineno)
            emit_range(node.lineno, class_sig_end)

            # Method signatures inside the class
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Method decorators
                    for dec in member.decorator_list:
                        emit_range(dec.lineno, dec.end_lineno or dec.lineno)
                    # def line(s) up to (but not including) the body
                    func_sig_end = member.body[0].lineno - 1 if member.body else (member.end_lineno or member.lineno)
                    emit_range(member.lineno, func_sig_end)
                    # Body placeholder matching the Python idiom
                    indent = " " * (member.col_offset + 4)
                    skeleton_parts.append(f"{indent}...")

            skeleton_parts.append("")

    return "\n".join(skeleton_parts).rstrip()
