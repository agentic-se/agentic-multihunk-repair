import subprocess, tempfile
from pathlib import Path
from typing import List


class PatchValidation:
    def __init__(self, patch_snippet: str) -> None:
        self.snippet = patch_snippet.rstrip("\n") + "\n"

    def apply_patch(
        self,
        bug_info: dict,
        buggy_file_path: str,
        encodings: List[str],
        bug_num: int,
        current_bug: str,
        linux_patches_path: str,
        mode: int | str = 4,
    ) -> None:
        src_path = Path(buggy_file_path)

        # 1) read original file
        for enc in encodings:
            try:
                lines = src_path.read_text(encoding=enc).splitlines(keepends=True)
                encoding_used = enc
                break
            except UnicodeDecodeError:
                continue
        else:
            raise RuntimeError(f"Unable to decode {src_path}")

        start = bug_info["buggy_code"][str(bug_num)]["start_line"] - 1
        end   = bug_info["buggy_code"][str(bug_num)]["end_line"]

        # 2) build new content and overwrite file
        patched_lines = (
            lines[:start] +
            self.snippet.splitlines(keepends=True) +
            lines[end:]
        )
        new_content = "".join(patched_lines)
        src_path.write_text(new_content, encoding=encoding_used)

        # 3) produce a unified diff for bookkeeping
        patch_dir = Path(linux_patches_path)
        patch_dir.mkdir(parents=True, exist_ok=True)
        diff_path = patch_dir / f"{current_bug}_bug_{bug_num}_{mode}.patch"

        tmp_orig = Path(tempfile.mkstemp(suffix=".orig")[1])
        tmp_orig.write_text("".join(lines), encoding="utf-8")

        proc = subprocess.run(
            ["diff", "-u", str(tmp_orig), "-"],           # "-" reads from stdin
            input=new_content.encode(),
            capture_output=True,
        )

        if proc.returncode not in (0, 1):                # 0 = identical, 1 = differ
            raise RuntimeError(f"`diff` failed with exit code {proc.returncode}")

        diff_path.write_bytes(proc.stdout)
        tmp_orig.unlink(missing_ok=True)
