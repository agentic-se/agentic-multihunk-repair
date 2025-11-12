from collections import defaultdict, namedtuple
from collections.abc import MutableMapping
from typing import Union
import logging

from context.search import java_search_utils
from context.search.java_search_utils import JavaSearchResult

# Configure logger
logger = logging.getLogger(__name__)

LineRange = namedtuple("LineRange", ["start", "end"])

ClassIndexType = MutableMapping[str, list[tuple[str, LineRange]]]
ClassMethodIndexType = MutableMapping[
    str, MutableMapping[str, list[tuple[str, LineRange]]]
]
MethodIndexType = MutableMapping[str, list[tuple[str, LineRange]]]

RESULT_SHOW_LIMIT = 3


class JavaSearchManager:
    def __init__(self, project_path: str):
        self.project_path = project_path
        logger.info(f"Initializing JavaSearchManager for project: {project_path}")

        # list of all files ending with .java, which are likely not test files
        # These are all ABSOLUTE paths.
        self.parsed_files: list[str] = []

        # for file name in the indexes, assume they are absolute path
        # class name -> [(file_name, line_range)]
        self.class_index: ClassIndexType = {}

        # {class_name -> {method_name -> [(file_name, line_range)]}}
        # inner dict is a list, since we can have (1) overloaded method names,
        # and (2) multiple classes with the same name, having the same method
        self.class_method_index: ClassMethodIndexType = {}

        # method name -> [(file_name, line_range)]
        # Java doesn't have top-level methods, but we keep for consistency
        self.method_index: MethodIndexType = {}
        self._build_index()

    def _build_index(self):
        """
        With all source code of the project, build two indexes:
            1. From class name to (source file, start line, end line)
            2. From method name to (source file, start line, end line)
        Since there can be two classes/methods with the same name, the mapping
        value is a list of tuples.
        This is for fast lookup whenever we receive a query.
        """
        self._update_indices(*self._build_java_index())

    def _update_indices(
        self,
        class_index: ClassIndexType,
        class_method_index: ClassMethodIndexType,
        method_index: MethodIndexType,
        parsed_files: list[str],
    ) -> None:
        self.class_index.update(class_index)
        self.class_method_index.update(class_method_index)
        self.method_index.update(method_index)
        self.parsed_files.extend(parsed_files)

        logger.info(f"Index updated: {len(parsed_files)} files, {len(class_index)} classes, {len(method_index)} methods")

    def _build_java_index(
        self,
    ) -> tuple[ClassIndexType, ClassMethodIndexType, MethodIndexType, list[str]]:
        class_index: ClassIndexType = defaultdict(list)
        class_method_index: ClassMethodIndexType = defaultdict(lambda: defaultdict(list))
        method_index: MethodIndexType = defaultdict(list)

        java_files = java_search_utils.find_java_files(self.project_path)
        logger.info(f"Found {len(java_files)} Java files in project")

        # holds the parsable subset of all java files
        parsed_java_files = []
        failed_count = 0

        for java_file in java_files:
            file_info = java_search_utils.parse_java_file(java_file)
            if file_info is None:
                # parsing of this file failed
                failed_count += 1
                continue
            parsed_java_files.append(java_file)
            # extract from file info, and form search index
            classes, class_to_methods, top_level_methods = file_info

            # (1) build class index
            for c, start, end in classes:
                class_index[c].append((java_file, LineRange(start, end)))

            # (2) build class-method index
            for c, class_methods in class_to_methods.items():
                for m, start, end in class_methods:
                    class_method_index[c][m].append((java_file, LineRange(start, end)))

            # (3) build (top-level) method index - empty for Java but kept for consistency
            for m, start, end in top_level_methods:
                method_index[m].append((java_file, LineRange(start, end)))

        if failed_count > 0:
            logger.warning(f"Failed to parse {failed_count} Java files")

        logger.info(f"Successfully parsed {len(parsed_java_files)} Java files, found {len(class_index)} classes")

        return class_index, class_method_index, method_index, parsed_java_files

    def file_line_to_class_and_method(
        self, file_path: str, line_no: int
    ) -> tuple[Union[str, None], Union[str, None]]:
        """
        Given a file path and a line number, return the class and method name.
        If the line is not inside a class or method, return None.
        """
        # check whether this line is inside a class method
        for class_name in self.class_method_index:
            method_dict = self.class_method_index[class_name]
            for method_name, method_info in method_dict.items():
                for file_name, line_range in method_info:
                    if file_name == file_path and line_range.start <= line_no <= line_range.end:
                        return class_name, method_name

        # not in any class method; check whether this line is inside a top-level method
        # (This would be rare in Java but keeping for consistency)
        for method_name in self.method_index:
            for file_name, line_range in self.method_index[method_name]:
                if file_name == file_path and line_range.start <= line_no <= line_range.end:
                    return None, method_name

        # this file-line is not recorded in any of the indexes
        return None, None

    def _search_method_in_class(
        self, method_name: str, class_name: str
    ) -> list[JavaSearchResult]:
        """
        Search for the method name in the class.
        Args:
            method_name (str): Name of the method.
            class_name (str): Name of the class.
        Returns:
            The list of code snippets searched.
        """
        result: list[JavaSearchResult] = []
        if class_name not in self.class_method_index:
            return result
        if method_name not in self.class_method_index[class_name]:
            return result
        for fname, line_range in self.class_method_index[class_name][method_name]:
            method_code = java_search_utils.get_code_snippets(fname, line_range.start, line_range.end)
            res = JavaSearchResult(fname, class_name, method_name, method_code)
            result.append(res)
        return result

    def _search_method_in_all_classes(self, method_name: str) -> list[JavaSearchResult]:
        """
        Search for the method name in all classes.
        Args:
            method_name (str): Name of the method.
        Returns:
            The list of code snippets searched.
        """
        result: list[JavaSearchResult] = []
        for class_name in self.class_index:
            res = self._search_method_in_class(method_name, class_name)
            result.extend(res)
        return result

    def _search_top_level_method(self, method_name: str) -> list[JavaSearchResult]:
        """
        Search for top-level method name in the entire project.
        Args:
            method_name (str): Name of the method.
        Returns:
            The list of code snippets searched.
        """
        result: list[JavaSearchResult] = []
        if method_name not in self.method_index:
            return result

        for fname, line_range in self.method_index[method_name]:
            method_code = java_search_utils.get_code_snippets(fname, line_range.start, line_range.end)
            res = JavaSearchResult(fname, None, method_name, method_code)
            result.append(res)
        return result

    def _search_method_in_code_base(self, method_name: str) -> list[JavaSearchResult]:
        """
        Search for this method, from both top-level and all class definitions.
        """
        result: list[JavaSearchResult] = []  # list of (file_name, method_code)
        # (1) search in top level (rare in Java)
        top_level_res = self._search_top_level_method(method_name)
        class_res = self._search_method_in_all_classes(method_name)
        result.extend(top_level_res)
        result.extend(class_res)
        return result

    ###############################
    ### API Interfaces ############
    ###############################

    def search_class(self, class_name: str) -> tuple[str, str, bool]:
        """Search for class cls in the codebase. Signature of the class."""
        logger.debug(f"Searching for class: {class_name}")

        # initialize them to error case
        summary = f"Class {class_name} did not appear in the codebase."
        tool_result = f"Could not find class {class_name} in the codebase."

        if class_name not in self.class_index:
            logger.debug(f"Class {class_name} not found in index")
            return tool_result, summary, False

        search_res: list[JavaSearchResult] = []
        for fname, _ in self.class_index[class_name]:
            # there are some classes; we return their signatures
            code = java_search_utils.get_class_signature(fname, class_name)
            res = JavaSearchResult(fname, class_name, None, code)
            search_res.append(res)

        if not search_res:
            # this should not happen, but just in case
            return tool_result, summary, False

        # the good path
        # for all the searched result, append them and form the final result
        tool_result = f"Found {len(search_res)} classes with name {class_name} in the codebase:\n\n"
        if len(search_res) > RESULT_SHOW_LIMIT:
            tool_result += "They appeared in the following files:\n"
            tool_result += JavaSearchResult.collapse_to_file_level(
                search_res, self.project_path
            )
        else:
            for idx, res in enumerate(search_res):
                res_str = res.to_tagged_str(self.project_path)
                tool_result += f"- Search result {idx + 1}:\n```\n{res_str}\n```\n"
        summary = f"The tool returned information about class `{class_name}`."
        return tool_result, summary, True

    def search_class_in_file(self, class_name: str, file_name: str) -> tuple[str, str, bool]:
        """Search for class cls in file f. Signature of the class."""
        # (1) check whether we can get the file
        candidate_java_abs_paths = [f for f in self.parsed_files if f.endswith(file_name)]
        if not candidate_java_abs_paths:
            tool_output = f"Could not find file {file_name} in the codebase."
            summary = tool_output
            return tool_output, summary, False

        # (2) search for this class in the entire code base (we do filtering later)
        if class_name not in self.class_index:
            tool_output = f"Could not find class {class_name} in the codebase."
            summary = tool_output
            return tool_output, summary, False

        # (3) class is there, check whether it exists in the file specified.
        search_res: list[JavaSearchResult] = []
        for fname, line_range in self.class_index[class_name]:
            if fname in candidate_java_abs_paths:
                class_code = java_search_utils.get_class_signature(fname, class_name)
                res = JavaSearchResult(fname, class_name, None, class_code)
                search_res.append(res)

        if not search_res:
            tool_output = f"Could not find class {class_name} in file {file_name}."
            summary = tool_output
            return tool_output, summary, False

        # good path; we have result, now just form a response
        tool_output = f"Found {len(search_res)} classes with name {class_name} in file {file_name}:\n\n"
        summary = tool_output
        for idx, res in enumerate(search_res):
            res_str = res.to_tagged_str(self.project_path)
            tool_output += f"- Search result {idx + 1}:\n```\n{res_str}\n```\n"
        return tool_output, summary, True

    def search_method(self, method_name: str) -> tuple[str, str, bool]:
        """Search for method m in the codebase. Full implementation of the method."""
        search_res: list[JavaSearchResult] = self._search_method_in_code_base(method_name)
        if not search_res:
            tool_output = f"Could not find method {method_name} in the codebase."
            summary = tool_output
            return tool_output, summary, False

        tool_output = f"Found {len(search_res)} methods with name {method_name} in the codebase:\n\n"
        summary = tool_output

        if len(search_res) > RESULT_SHOW_LIMIT:
            tool_output += "They appeared in the following files:\n"
            tool_output += JavaSearchResult.collapse_to_file_level(
                search_res, self.project_path
            )
        else:
            for idx, res in enumerate(search_res):
                res_str = res.to_tagged_str(self.project_path)
                tool_output += f"- Search result {idx + 1}:\n```\n{res_str}\n```\n"

        return tool_output, summary, True

    def search_method_in_class(self, method_name: str, class_name: str) -> tuple[str, str, bool]:
        """Search for method m in class cls. Full implementation of the method."""
        if class_name not in self.class_index:
            tool_output = f"Could not find class {class_name} in the codebase."
            summary = tool_output
            return tool_output, summary, False

        # has this class, check its methods
        search_res: list[JavaSearchResult] = self._search_method_in_class(
            method_name, class_name
        )
        if not search_res:
            tool_output = f"Could not find method {method_name} in class {class_name}."
            summary = tool_output
            return tool_output, summary, False

        # found some methods, prepare the result
        tool_output = f"Found {len(search_res)} methods with name {method_name} in class {class_name}:\n\n"
        summary = tool_output

        # There can be multiple classes defined in multiple files, which contain the same method
        # still trim the result, just in case
        if len(search_res) > RESULT_SHOW_LIMIT:
            tool_output += f"Too many results, showing full code for {RESULT_SHOW_LIMIT} of them, and the rest just file names:\n"
        first_few = search_res[:RESULT_SHOW_LIMIT]
        for idx, res in enumerate(first_few):
            res_str = res.to_tagged_str(self.project_path)
            tool_output += f"- Search result {idx + 1}:\n```\n{res_str}\n```\n"
        # for the rest, collect the file names into a set
        if rest := search_res[RESULT_SHOW_LIMIT:]:
            tool_output += "Other results are in these files:\n"
            tool_output += JavaSearchResult.collapse_to_file_level(rest, self.project_path)
        return tool_output, summary, True

    def search_method_in_file(self, method_name: str, file_name: str) -> tuple[str, str, bool]:
        """Search for method m in file f. Full implementation of the method."""
        # (1) check whether we can get the file
        # supports both when file_name is relative to project root, and when
        # it is just a short name
        candidate_java_abs_paths = [f for f in self.parsed_files if f.endswith(file_name)]
        if not candidate_java_abs_paths:
            tool_output = f"Could not find file {file_name} in the codebase."
            summary = tool_output
            return tool_output, summary, False

        # (2) search for this method in the entire code base (we do filtering later)
        search_res: list[JavaSearchResult] = self._search_method_in_code_base(method_name)
        if not search_res:
            tool_output = f"The method {method_name} does not appear in the codebase."
            summary = tool_output
            return tool_output, summary, False

        # (3) filter the search result => they need to be in one of the files!
        filtered_res: list[JavaSearchResult] = [
            res for res in search_res if res.file_path in candidate_java_abs_paths
        ]

        # (4) done with search, now prepare result
        if not filtered_res:
            tool_output = (
                f"There is no method with name `{method_name}` in file {file_name}."
            )
            summary = tool_output
            return tool_output, summary, False

        tool_output = f"Found {len(filtered_res)} methods with name `{method_name}` in file {file_name}:\n\n"
        summary = tool_output

        # when searching for a method in one file, it's rare that there are
        # many candidates, so we do not trim the result
        for idx, res in enumerate(filtered_res):
            res_str = res.to_tagged_str(self.project_path)
            tool_output += f"- Search result {idx + 1}:\n```\n{res_str}\n```\n"
        return tool_output, summary, True

    def search_code(self, code_str: str) -> tuple[str, str, bool]:
        """Search for snippet c in the codebase. ±5 lines around the snippet."""
        # attempt to search for this code string in all java files
        all_search_results: list[JavaSearchResult] = []
        for file_path in self.parsed_files:
            searched_line_and_code: list[tuple[int, str]] = (
                java_search_utils.get_code_region_containing_code(file_path, code_str)
            )
            if not searched_line_and_code:
                continue
            for searched in searched_line_and_code:
                line_no, code_region = searched
                # from line_no, check which method and class we are in
                class_name, method_name = self.file_line_to_class_and_method(
                    file_path, line_no
                )
                res = JavaSearchResult(file_path, class_name, method_name, code_region)
                all_search_results.append(res)

        if not all_search_results:
            tool_output = f"Could not find code {code_str} in the codebase."
            summary = tool_output
            return tool_output, summary, False

        # good path
        tool_output = f"Found {len(all_search_results)} snippets containing `{code_str}` in the codebase:\n\n"
        summary = tool_output

        if len(all_search_results) > RESULT_SHOW_LIMIT:
            tool_output += "They appeared in the following files:\n"
            tool_output += JavaSearchResult.collapse_to_file_level(
                all_search_results, self.project_path
            )
        else:
            for idx, res in enumerate(all_search_results):
                res_str = res.to_tagged_str(self.project_path)
                tool_output += f"- Search result {idx + 1}:\n```\n{res_str}\n```\n"
        return tool_output, summary, True

    def search_code_in_file(self, code_str: str, file_name: str) -> tuple[str, str, bool]:
        """Search for snippet c in file f."""
        code_str = code_str.removesuffix(")")

        candidate_java_files = [f for f in self.parsed_files if f.endswith(file_name)]
        if not candidate_java_files:
            tool_output = f"Could not find file {file_name} in the codebase."
            summary = tool_output
            return tool_output, summary, False

        # start searching for code in the filtered files
        all_search_results: list[JavaSearchResult] = []
        for file_path in candidate_java_files:
            searched_line_and_code: list[tuple[int, str]] = (
                java_search_utils.get_code_region_containing_code(file_path, code_str)
            )
            if not searched_line_and_code:
                continue
            for searched in searched_line_and_code:
                line_no, code_region = searched
                # from line_no, check which method and class we are in
                class_name, method_name = self.file_line_to_class_and_method(
                    file_path, line_no
                )
                res = JavaSearchResult(file_path, class_name, method_name, code_region)
                all_search_results.append(res)

        if not all_search_results:
            tool_output = f"Could not find code {code_str} in file {file_name}."
            summary = tool_output
            return tool_output, summary, False

        # good path
        # There can be a lot of results, from multiple files.
        tool_output = f"Found {len(all_search_results)} snippets with code {code_str} in file {file_name}:\n\n"
        summary = tool_output
        if len(all_search_results) > RESULT_SHOW_LIMIT:
            tool_output += "They appeared in the following methods:\n"
            tool_output += JavaSearchResult.collapse_to_method_level(
                all_search_results, self.project_path
            )
        else:
            for idx, res in enumerate(all_search_results):
                res_str = res.to_tagged_str(self.project_path)
                tool_output += f"- Search result {idx + 1}:\n```\n{res_str}\n```\n"
        return tool_output, summary, True

    def retrieve_code_snippet(
        self, file_path: str, start_line: int, end_line: int
    ) -> str:
        return java_search_utils.get_code_snippets(file_path, start_line, end_line)

    def extract_class_skeleton(self, file_name: str) -> tuple[str, str, bool]:
        """Extracts the class skeleton and method signatures for all classes from file f."""
        # Find the file by name
        candidate_java_abs_paths = [f for f in self.parsed_files if f.endswith(file_name)]
        if not candidate_java_abs_paths:
            tool_output = f"Could not find file {file_name} in the codebase."
            summary = tool_output
            return tool_output, summary, False
        
        # Use the first matching file
        file_path = candidate_java_abs_paths[0]
        
        # Extract skeleton
        skeleton = java_search_utils.extract_class_skeleton(file_path)
        
        if skeleton.startswith("Error"):
            tool_output = f"Failed to extract skeleton from {file_name}: {skeleton}"
            summary = tool_output
            return tool_output, summary, False
        
        tool_output = f"Class skeleton extracted from {file_name}:\n\n```java\n{skeleton}\n```"
        summary = f"Successfully extracted class skeleton from {file_name}"
        return tool_output, summary, True

    def get_repo_structure(self, max_depth: int = 100) -> tuple[str, str, bool]:
        """
        Generate a tree-like view of the repository structure showing Java files.

        Args:
            max_depth: Maximum depth to display in the tree (default: 100)

        Returns:
            Tuple of (result_string, summary, success_boolean)
        """
        import os
        from pathlib import Path

        try:
            # Build a tree structure
            root_path = Path(self.project_path)

            def build_tree(path: Path, prefix: str = "", depth: int = 0) -> list[str]:
                """Recursively build tree structure."""
                if depth > max_depth:
                    return []

                lines = []
                try:
                    # Get all items in directory
                    items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))

                    # Filter out common non-source directories
                    excluded = {'.git', '.idea', '.vscode', 'build', 'target', 'bin', 'out',
                               'node_modules', '.gradle', '__pycache__', 'test-data', 'generated'}
                    items = [item for item in items if item.name not in excluded]

                    for i, item in enumerate(items):
                        is_last = i == len(items) - 1
                        current_prefix = "└── " if is_last else "├── "
                        next_prefix = prefix + ("    " if is_last else "│   ")

                        if item.is_dir():
                            lines.append(f"{prefix}{current_prefix}{item.name}/")
                            # Recurse into directory
                            lines.extend(build_tree(item, next_prefix, depth + 1))
                        elif item.suffix == '.java':
                            lines.append(f"{prefix}{current_prefix}{item.name}")

                except PermissionError:
                    pass

                return lines

            # Build the tree starting from root
            tree_lines = [f"{root_path.name}/"]
            tree_lines.extend(build_tree(root_path, "", 0))

            result = "\n".join(tree_lines)

            # Count statistics
            java_file_count = len(self.parsed_files)
            class_count = len(self.class_index)

            summary = f"Repository structure with {java_file_count} Java files and {class_count} classes"

            return result, summary, True

        except Exception as e:
            error_msg = f"Error generating repository structure: {str(e)}"
            return error_msg, error_msg, False

    # Additional helper method for getting full class snippet
    def get_class_full_snippet(self, class_name: str) -> tuple[str, str, bool]:
        summary = f"Class {class_name} did not appear in the codebase."
        tool_result = f"Could not find class {class_name} in the codebase."

        if class_name not in self.class_index:
            return tool_result, summary, False
        # class name -> [(file_name, start_line, end_line)]
        search_res: list[JavaSearchResult] = []
        for fname, line_range in self.class_index[class_name]:
            code = java_search_utils.get_code_snippets(fname, line_range.start, line_range.end)
            res = JavaSearchResult(fname, class_name, None, code)
            search_res.append(res)

        if not search_res:
            return tool_result, summary, False

        # the good path
        # for all the searched result, append them and form the final result
        tool_result = f"Found {len(search_res)} classes with name {class_name} in the codebase:\n\n"
        summary = tool_result
        if len(search_res) > 2:
            tool_result += "Too many results, showing full code for 2 of them:\n"
        for idx, res in enumerate(search_res[:2]):
            res_str = res.to_tagged_str(self.project_path)
            tool_result += f"- Search result {idx + 1}:\n```\n{res_str}\n```"
        return tool_result, summary, True