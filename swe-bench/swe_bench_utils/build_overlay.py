"""
Build per-instance overlay images: SWE-bench base + Node.js + a coding-agent
CLI (gemini-cli, qwen-code, ...). The defaults below are the canonical pins.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

from .docker_env import (
    DEFAULT_IMAGE_BASE,
    DEFAULT_IMAGE_TAG,
    image_digest,
    image_exists,
    instance_image_name,
    overlay_image_name,
    pull_image,
)

log = logging.getLogger(__name__)

DOCKERFILE = Path(__file__).resolve().parent / "Dockerfile.overlay"

# Pinned versions -- referenced by every other layer (CLI defaults,
# function defaults, manifest entries). Bump here to bump everywhere.
DEFAULT_NODE_MAJOR = "20"          # NodeSource setup_<N>.x

# Gemini CLI: matches the host version used for Defects4J runs.
DEFAULT_GEMINI_NPM_PACKAGE = "@google/gemini-cli"
DEFAULT_GEMINI_VERSION = "0.10.0"
DEFAULT_GEMINI_BINARY = "gemini"

# Qwen Code: upgraded to latest stable version for better agentic behavior.
DEFAULT_QWEN_NPM_PACKAGE = "@qwen-code/qwen-code"
DEFAULT_QWEN_VERSION = "0.15.6"
DEFAULT_QWEN_BINARY = "qwen"

# OpenAI Codex CLI: matches the host version used for Defects4J runs.
# Default underlying model in codex-cli 0.21.0 is gpt-5.
DEFAULT_CODEX_NPM_PACKAGE = "@openai/codex"
DEFAULT_CODEX_VERSION = "0.21.0"
DEFAULT_CODEX_BINARY = "codex"
DEFAULT_CODEX_MODEL = "gpt-5"

# Claude Code CLI: matches the host version used for Defects4J runs.
DEFAULT_CLAUDE_NPM_PACKAGE = "@anthropic-ai/claude-code"
DEFAULT_CLAUDE_VERSION = "2.0.13"
DEFAULT_CLAUDE_BINARY = "claude"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-5-20250929"


def build_overlay(
    instance_id: str,
    *,
    image_base: str = DEFAULT_IMAGE_BASE,
    image_tag: str = DEFAULT_IMAGE_TAG,
    overlay_prefix: str = "gemini-eval",
    node_major: str = DEFAULT_NODE_MAJOR,
    cli_npm_package: str = DEFAULT_GEMINI_NPM_PACKAGE,
    cli_version: str = DEFAULT_GEMINI_VERSION,
    cli_binary: str = DEFAULT_GEMINI_BINARY,
    force: bool = False,
    executable: str = "docker",
) -> str:
    """Build (or reuse) the overlay image for one instance; return its tag."""
    base = instance_image_name(instance_id, image_base=image_base, tag=image_tag)
    overlay = overlay_image_name(instance_id, prefix=overlay_prefix, image_base=image_base)

    if not force and image_exists(overlay, executable=executable):
        log.info("[%s] overlay present, skipping build (%s)", instance_id, overlay)
        return overlay

    pull_image(base, executable=executable)
    log.info("[%s] building overlay: %s (%s@%s)",
             instance_id, overlay, cli_npm_package, cli_version)
    result = subprocess.run([
        executable, "build", "-t", overlay, "-f", str(DOCKERFILE),
        "--build-arg", f"BASE_IMAGE={base}",
        "--build-arg", f"NODE_MAJOR={node_major}",
        "--build-arg", f"CLI_NPM_PACKAGE={cli_npm_package}",
        "--build-arg", f"CLI_VERSION={cli_version}",
        "--build-arg", f"CLI_BINARY={cli_binary}",
        str(DOCKERFILE.parent),
    ], check=False)
    if result.returncode != 0:
        raise RuntimeError(f"overlay build failed for {instance_id}")
    return overlay


def write_image_manifest(manifest_path: Path, entries: list[dict]) -> None:
    """Write a JSON manifest of image digests for reproducibility."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def collect_manifest_entry(
    instance_id: str,
    base: str,
    overlay: str,
    *,
    node_major: str,
    cli_npm_package: str,
    cli_version: str,
    executable: str = "docker",
) -> dict:
    return {
        "instance_id": instance_id,
        "base_image": base,
        "base_digest": image_digest(base, executable=executable),
        "overlay_image": overlay,
        "overlay_digest": image_digest(overlay, executable=executable),
        "node_major": node_major,
        "cli_npm_package": cli_npm_package,
        "cli_version": cli_version,
    }
