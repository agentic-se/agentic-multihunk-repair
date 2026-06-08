#!/bin/bash -l
# Run the full canonical test suite for this SWE-bench instance: every
# test in the test files touched by test_patch. Matches what the official
# grader runs and is the right command for post-fix regression checking.
#
# Login shell (-l) is required so the SWE-bench image's `testbed` conda
# env activates -- otherwise python won't find django/pytest/etc.
set -x
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOGFILE="all_tests_trace.${TIMESTAMP}.log"

cd "$(cat /testbed/.swebench/test_cwd)"
TEST_CMD=$(cat /testbed/.swebench/test_cmd)
DIRECTIVES=$(cat /testbed/.swebench/test_directives)

echo "Running canonical SWE-bench test command:" | tee "$LOGFILE"
echo "  cwd: $(pwd)" | tee -a "$LOGFILE"
echo "  cmd: $TEST_CMD $DIRECTIVES" | tee -a "$LOGFILE"
echo | tee -a "$LOGFILE"

eval "$TEST_CMD $DIRECTIVES" 2>&1 | tee -a "$LOGFILE"
echo "Log saved to: $LOGFILE"
