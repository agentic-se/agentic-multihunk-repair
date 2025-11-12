# java_search_utils.py

import glob
import logging
import re
import javalang
from dataclasses import dataclass
from os.path import join as pjoin
from typing import Optional, List, Tuple

# Configure logger
logger = logging.getLogger(__name__)

@dataclass
class JavaSearchResult:
    """Dataclass to hold Java search results."""
    file_path: str  # this is an absolute path
    class_name: Optional[str]
    method_name: Optional[str]
    code: str

    def to_tagged_upto_file(self, project_root: str) -> str:
        """Converts the search result to a tagged string up to the file path."""
        rel_path = self.file_path[len(project_root) + 1:]
        return f"<file>{rel_path}</file>"

    def to_tagged_upto_class(self, project_root: str) -> str:
        """Converts the search result to a tagged string up to the class level."""
        return f"{self.to_tagged_upto_file(project_root)}\n<class>{self.class_name}</class>" if self.class_name else self.to_tagged_upto_file(project_root)

    def to_tagged_upto_method(self, project_root: str) -> str:
        """Converts the search result to a tagged string up to the method level."""
        method_part = f" <method>{self.method_name}</method>" if self.method_name else ""
        return f"{self.to_tagged_upto_class(project_root)}{method_part}"

    def to_tagged_str(self, project_root: str) -> str:
        """Converts the search result to a full tagged string including code."""
        return f"{self.to_tagged_upto_method(project_root)}\n<code>\n{self.code}\n</code>"

    @staticmethod
    def collapse_to_file_level(results: List['JavaSearchResult'], project_root: str) -> str:
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
    def collapse_to_method_level(results: List['JavaSearchResult'], project_root: str) -> str:
        """Collapses search results to show a summary at the method level."""
        summary_dict = {}
        for result in results:
            key = (result.file_path, result.method_name or "Not in a method")
            summary_dict[key] = summary_dict.get(key, 0) + 1
        summary = ""
        for (file_path, method_name), count in summary_dict.items():
            rel_path = file_path[len(project_root) + 1:]
            method_part = f" <method>{method_name}</method>" if method_name != "Not in a method" else method_name
            summary += f"- <file>{rel_path}</file>{method_part} ({count} matches)\n"
        return summary

def find_java_files(dir_path: str) -> List[str]:
    """Recursively finds all .java files in a directory, excluding some known non-source directories."""
    excluded_dirs = {"build", "target", "bin", "out", "test-data", "generated"}
    java_files = glob.glob(pjoin(dir_path, "**/*.java"), recursive=True)
    return [file for file in java_files if not any(part in file for part in excluded_dirs)]

def parse_java_file(file_path: str) -> Optional[Tuple[List, dict, List]]:
    """
    Parses a Java file using javalang AST parser to extract classes and methods.
    Returns: (classes, class_to_methods, top_level_methods)
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return None

    try:
        # Parse Java code using javalang
        tree = javalang.parse.parse(content)
    except Exception as e:
        # If parsing fails, try to clean up the content and retry
        try:
            # Remove package and import statements that might cause issues
            lines = content.splitlines()
            cleaned_lines = []
            for line in lines:
                if not (line.strip().startswith('package ') or line.strip().startswith('import ')):
                    cleaned_lines.append(line)
            cleaned_content = '\n'.join(cleaned_lines)
            tree = javalang.parse.parse(cleaned_content)
        except Exception as e2:
            logger.error(f"Error parsing Java file {file_path}: {e2}")
            return None

    classes = []
    class_to_methods = {}
    top_level_methods = []  # Java doesn't have top-level methods, but we keep for consistency
    
    # Get file lines for position mapping
    lines = content.splitlines()
    
    # Walk through the AST to find classes and their methods
    for path, node in tree:
        if isinstance(node, javalang.tree.ClassDeclaration):
            class_name = node.name
            class_start_line = node.position.line if node.position else 1
            
            # Find the end of the class by looking for the last method or field
            class_end_line = class_start_line
            if node.body:
                for member in node.body:
                    if hasattr(member, 'position') and member.position:
                        class_end_line = max(class_end_line, member.position.line)
            
            # If we couldn't determine the end, estimate it
            if class_end_line == class_start_line:
                class_end_line = len(lines)
            
            classes.append((class_name, class_start_line, class_end_line))
            class_to_methods[class_name] = []
            
            # Find methods in this class
            if node.body:
                for member in node.body:
                    if isinstance(member, javalang.tree.MethodDeclaration):
                        method_name = member.name
                        method_start_line = member.position.line if member.position else class_start_line
                        
                        # Estimate method end line by finding the next member or end of class
                        method_end_line = method_start_line + 10  # Default estimate
                        if member.body:
                            # Try to find the actual end by looking at the method body
                            method_end_line = method_start_line + 20  # Better estimate for methods with body
                        
                        class_to_methods[class_name].append((method_name, method_start_line, method_end_line))
                    
                    elif isinstance(member, javalang.tree.ConstructorDeclaration):
                        # Include constructors
                        method_name = member.name
                        method_start_line = member.position.line if member.position else class_start_line
                        method_end_line = method_start_line + 10  # Estimate
                        class_to_methods[class_name].append((method_name, method_start_line, method_end_line))

        elif isinstance(node, javalang.tree.InterfaceDeclaration):
            class_name = node.name
            class_start_line = node.position.line if node.position else 1
            class_end_line = len(lines)  # Estimate
            
            classes.append((class_name, class_start_line, class_end_line))
            class_to_methods[class_name] = []
            
            # Find methods in interface
            if node.body:
                for member in node.body:
                    if isinstance(member, javalang.tree.MethodDeclaration):
                        method_name = member.name
                        method_start_line = member.position.line if member.position else class_start_line
                        method_end_line = method_start_line + 5  # Interface methods are typically short
                        class_to_methods[class_name].append((method_name, method_start_line, method_end_line))

        elif isinstance(node, javalang.tree.EnumDeclaration):
            class_name = node.name
            class_start_line = node.position.line if node.position else 1
            class_end_line = len(lines)  # Estimate
            
            classes.append((class_name, class_start_line, class_end_line))
            class_to_methods[class_name] = []

    return classes, class_to_methods, top_level_methods

def get_code_region_containing_code(file_path: str, code_str: str) -> List[Tuple[int, str]]:
    """Finds regions in the file containing a specific code string with ±5 lines of context."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            file_content = f.read()
    except Exception:
        return []

    occurrences = []
    file_lines = file_content.splitlines()
    for match in re.finditer(re.escape(code_str), file_content):
        start_line = file_content.count("\n", 0, match.start())
        context = "\n".join(file_lines[max(0, start_line - 5):start_line + 6])
        occurrences.append((start_line, context))
    return occurrences

def get_method_snippet_with_code_in_file(file_path: str, code_str: str) -> List[str]:
    """Finds and extracts method code containing a specified string."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            file_content = f.read()
    except Exception:
        return []
        
    file_info = parse_java_file(file_path)
    if not file_info:
        return []
        
    classes, class_to_methods, _ = file_info
    snippets = []
    
    # Check methods in classes
    for class_name, methods in class_to_methods.items():
        for method_name, start_line, end_line in methods:
            method_code = get_code_snippets(file_path, start_line, end_line)
            if code_str in method_code.replace("\n", " "):
                snippets.append(method_code)
    
    return snippets

def get_code_snippets(file_path: str, start: int, end: int) -> str:
    """Extracts lines of code from start to end in a file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return ""
    return "".join(lines[start - 1:end])

def get_class_signature(file_path: str, class_name: str) -> str:
    """Returns the class signature for a specified class name using AST parsing."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return ""
        
    try:
        tree = javalang.parse.parse(content)
    except Exception:
        return ""
        
    lines = content.splitlines()
    
    # Find the class in the AST
    for path, node in tree:
        if isinstance(node, (javalang.tree.ClassDeclaration, javalang.tree.InterfaceDeclaration, javalang.tree.EnumDeclaration)):
            if node.name == class_name:
                start_line = node.position.line if node.position else 1
                
                # Extract the class declaration line(s)
                class_lines = []
                i = start_line - 1  # Convert to 0-based indexing
                
                # Start from the line with the class declaration
                while i < len(lines):
                    line = lines[i]
                    class_lines.append(line)
                    
                    # Stop when we hit the opening brace
                    if '{' in line:
                        break
                    i += 1
                
                return '\n'.join(class_lines)
    
    return ""

def get_method_signature(file_path: str, class_name: str, method_name: str) -> str:
    """Returns the method signature for a specified method in a class."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return ""
        
    try:
        tree = javalang.parse.parse(content)
    except Exception:
        return ""
        
    lines = content.splitlines()
    
    # Find the class and method in the AST
    for path, node in tree:
        if isinstance(node, javalang.tree.ClassDeclaration) and node.name == class_name:
            if node.body:
                for member in node.body:
                    if isinstance(member, javalang.tree.MethodDeclaration) and member.name == method_name:
                        if member.position:
                            start_line = member.position.line - 1  # Convert to 0-based
                            
                            # Extract method signature lines
                            sig_lines = []
                            i = start_line
                            
                            while i < len(lines):
                                line = lines[i]
                                sig_lines.append(line)
                                
                                # Stop when we hit the opening brace or semicolon
                                if '{' in line or line.strip().endswith(';'):
                                    break
                                i += 1
                            
                            return '\n'.join(sig_lines)
    
    return ""

def extract_class_skeleton(file_path: str) -> str:
    """
    Extracts the class skeleton and method signatures for all classes from file f.
    This is a new API requirement from CLAUDE.md.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        return f"Error reading file: {e}"
        
    try:
        tree = javalang.parse.parse(content)
    except Exception as e:
        return f"Error parsing Java file: {e}"
        
    lines = content.splitlines()
    skeleton_parts = []
    
    # Extract package and imports
    if tree.package:
        skeleton_parts.append(f"package {tree.package.name};")
        skeleton_parts.append("")
    
    if tree.imports:
        for imp in tree.imports:
            static_part = "static " if imp.static else ""
            wildcard_part = ".*" if imp.wildcard else ""
            skeleton_parts.append(f"import {static_part}{imp.path}{wildcard_part};")
        skeleton_parts.append("")
    
    # Extract classes, interfaces, and enums with their method signatures
    for path, node in tree:
        if isinstance(node, javalang.tree.ClassDeclaration):
            # Class declaration
            modifiers = " ".join(node.modifiers) if node.modifiers else ""
            extends_part = f" extends {node.extends.name}" if node.extends else ""
            implements_part = ""
            if node.implements:
                implements_list = [impl.name for impl in node.implements]
                implements_part = f" implements {', '.join(implements_list)}"
            
            class_declaration = f"{modifiers} class {node.name}{extends_part}{implements_part} {{".strip()
            skeleton_parts.append(class_declaration)
            
            # Extract method signatures
            if node.body:
                for member in node.body:
                    if isinstance(member, javalang.tree.MethodDeclaration):
                        # Method signature
                        modifiers = " ".join(member.modifiers) if member.modifiers else ""
                        return_type = member.return_type.name if member.return_type else "void"
                        params = []
                        if member.parameters:
                            for param in member.parameters:
                                param_type = param.type.name if param.type else "Object"
                                params.append(f"{param_type} {param.name}")
                        params_str = ", ".join(params)
                        
                        throws_part = ""
                        if member.throws:
                            throws_list = [throw.name for throw in member.throws]
                            throws_part = f" throws {', '.join(throws_list)}"
                        
                        method_sig = f"    {modifiers} {return_type} {member.name}({params_str}){throws_part};".strip()
                        skeleton_parts.append(method_sig)
                    
                    elif isinstance(member, javalang.tree.ConstructorDeclaration):
                        # Constructor signature
                        modifiers = " ".join(member.modifiers) if member.modifiers else ""
                        params = []
                        if member.parameters:
                            for param in member.parameters:
                                param_type = param.type.name if param.type else "Object"
                                params.append(f"{param_type} {param.name}")
                        params_str = ", ".join(params)
                        
                        throws_part = ""
                        if member.throws:
                            throws_list = [throw.name for throw in member.throws]
                            throws_part = f" throws {', '.join(throws_list)}"
                        
                        constructor_sig = f"    {modifiers} {member.name}({params_str}){throws_part};".strip()
                        skeleton_parts.append(constructor_sig)
                    
                    elif isinstance(member, javalang.tree.FieldDeclaration):
                        # Field declaration
                        modifiers = " ".join(member.modifiers) if member.modifiers else ""
                        field_type = member.type.name if member.type else "Object"
                        for declarator in member.declarators:
                            field_sig = f"    {modifiers} {field_type} {declarator.name};".strip()
                            skeleton_parts.append(field_sig)
            
            skeleton_parts.append("}")
            skeleton_parts.append("")
            
        elif isinstance(node, javalang.tree.InterfaceDeclaration):
            # Interface declaration
            modifiers = " ".join(node.modifiers) if node.modifiers else ""
            extends_part = ""
            if node.extends:
                extends_list = [ext.name for ext in node.extends]
                extends_part = f" extends {', '.join(extends_list)}"
            
            interface_declaration = f"{modifiers} interface {node.name}{extends_part} {{".strip()
            skeleton_parts.append(interface_declaration)
            
            # Extract method signatures
            if node.body:
                for member in node.body:
                    if isinstance(member, javalang.tree.MethodDeclaration):
                        # Interface method signature
                        modifiers = " ".join(member.modifiers) if member.modifiers else ""
                        return_type = member.return_type.name if member.return_type else "void"
                        params = []
                        if member.parameters:
                            for param in member.parameters:
                                param_type = param.type.name if param.type else "Object"
                                params.append(f"{param_type} {param.name}")
                        params_str = ", ".join(params)
                        
                        method_sig = f"    {modifiers} {return_type} {member.name}({params_str});".strip()
                        skeleton_parts.append(method_sig)
            
            skeleton_parts.append("}")
            skeleton_parts.append("")
            
        elif isinstance(node, javalang.tree.EnumDeclaration):
            # Enum declaration
            modifiers = " ".join(node.modifiers) if node.modifiers else ""
            enum_declaration = f"{modifiers} enum {node.name} {{".strip()
            skeleton_parts.append(enum_declaration)
            
            # Extract enum constants
            if node.body and node.body.constants:
                constants = [const.name for const in node.body.constants]
                skeleton_parts.append(f"    {', '.join(constants)};")
            
            skeleton_parts.append("}")
            skeleton_parts.append("")
    
    return "\n".join(skeleton_parts)