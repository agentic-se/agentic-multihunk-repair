"""In-container runner for the MCP e2e test (test_mcp_e2e.py).

THIS FILE IS NOT INTENDED TO RUN ON THE HOST. It is `cp_in`ed into the
SWE-bench Docker container by test_mcp_e2e.py and executed there via
`conda run -n mcp-e2e python /tmp/run_mcp_e2e.py`. The host's Python does
not have `mcp[fastmcp]` installed, so importing this on the host will
fail at the `mcp` imports — that's expected.

Output conventions:
  stderr  -> progress markers, host test captures this
  stdout  -> the MCP protocol channel between client and server.
             We also print "ALL_PASSED" to stdout once everything's
             green so the host-side test can grep for it.
  exit    -> 0 on ALL_PASSED, 2 on bad setup, 3 on list_tools failure,
             4 on find_class failure, 5 on repo_structure failure,
             6 on extract_class_skeleton failure.
"""
import asyncio
import os
import sys

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession


SERVER = "/opt/progctx-mcp-swe-bench/mcp_server/python_analysis_server.py"
PROJECT_PATH = "/testbed"

EXPECTED_TOOLS = {
    "maple_find_class",
    "maple_find_class_in_file",
    "maple_find_method",
    "maple_find_method_in_class",
    "maple_find_method_in_file",
    "maple_find_code",
    "maple_find_code_in_file",
    "maple_extract_class_skeleton",
    "maple_repo_structure",
}


def log(msg: str) -> None:
    print(f"[runner] {msg}", file=sys.stderr, flush=True)


def _text(result) -> str:
    return "".join(b.text for b in result.content if hasattr(b, "text"))


async def main() -> None:
    log(f"sys.executable: {sys.executable}")
    log(f"python: {sys.version.split()[0]}")
    log(f"server file: {SERVER}")
    log(f"project path: {PROJECT_PATH}")

    if not os.path.exists(SERVER):
        log(f"FATAL: server file not found at {SERVER}")
        sys.exit(2)
    if not os.path.isdir(PROJECT_PATH):
        log(f"FATAL: project path is not a directory: {PROJECT_PATH}")
        sys.exit(2)

    params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER],
        env={
            **os.environ,
            "PYTHON_PROJECT_PATH": PROJECT_PATH,
            "PYTHONPATH": "/opt/progctx-mcp-swe-bench",
        },
    )

    log("connecting STDIO MCP client to server subprocess...")
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            log("session.initialize()...")
            await session.initialize()
            log("  ok")

            log("STEP 1/4: list_tools()")
            listing = await session.list_tools()
            names = {t.name for t in listing.tools}
            missing = EXPECTED_TOOLS - names
            if missing:
                log(f"  FAIL: missing tools: {sorted(missing)}")
                log(f"  got: {sorted(names)}")
                sys.exit(3)
            log(f"  ok ({len(names)} tools registered)")

            log("STEP 2/4: maple_find_class(Quantity)")
            r = await session.call_tool(
                "maple_find_class", {"class_name": "Quantity"}
            )
            text = _text(r)
            if "SUCCESS" not in text:
                log(f"  FAIL: no SUCCESS in response. excerpt:")
                log(text[:600])
                sys.exit(4)
            if "Quantity" not in text:
                log(f"  FAIL: 'Quantity' not in response. excerpt:")
                log(text[:600])
                sys.exit(4)
            log("  ok")

            log("STEP 3/4: maple_repo_structure(max_depth=1)")
            r = await session.call_tool(
                "maple_repo_structure", {"max_depth": 1}
            )
            text = _text(r)
            if "SUCCESS" not in text:
                log(f"  FAIL: no SUCCESS. excerpt:")
                log(text[:600])
                sys.exit(5)
            if "astropy" not in text.lower():
                log(f"  FAIL: no 'astropy' in tree. excerpt:")
                log(text[:600])
                sys.exit(5)
            log("  ok")

            log("STEP 4/4: maple_extract_class_skeleton(quantity.py)")
            r = await session.call_tool(
                "maple_extract_class_skeleton", {"file_name": "quantity.py"}
            )
            text = _text(r)
            if "SUCCESS" not in text:
                log(f"  FAIL: no SUCCESS. excerpt:")
                log(text[:600])
                sys.exit(6)
            log("  ok")

            log("ALL_PASSED")
            # Also emit to stdout so the host-side test can grep for it once
            # the protocol streams are closed.
            print("ALL_PASSED")


if __name__ == "__main__":
    asyncio.run(main())
