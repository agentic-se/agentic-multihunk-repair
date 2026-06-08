#!/bin/bash -l
# Run the canonical SWE-bench test command, then report ONLY on the
# FAIL_TO_PASS tests (the bug-exposing subset). The full log is preserved
# alongside a per-FTP summary so the agent can drill in if needed.
#
# We can't pass FAIL_TO_PASS names directly to the runner: some are docstring
# titles (e.g. Django) which aren't valid CLI selectors. Instead we run the
# canonical test_cmd over the modules touched by test_patch, then grep the
# log -- same approach the official SWE-bench grader uses.
set -x
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
FULL_LOG="bug_triggering_tests.${TIMESTAMP}.log"
SUMMARY_LOG="bug_triggering_tests.${TIMESTAMP}.summary.log"

cd "$(cat /testbed/.swebench/test_cwd)"
TEST_CMD=$(cat /testbed/.swebench/test_cmd)
DIRECTIVES=$(cat /testbed/.swebench/test_directives)

echo "Running canonical SWE-bench test command:" | tee "$FULL_LOG"
echo "  cwd: $(pwd)"                              | tee -a "$FULL_LOG"
echo "  cmd: $TEST_CMD $DIRECTIVES"               | tee -a "$FULL_LOG"
echo                                              | tee -a "$FULL_LOG"

eval "$TEST_CMD $DIRECTIVES" 2>&1 | tee -a "$FULL_LOG"

{ set +x; } 2>/dev/null
{
  echo
  echo "=== FAIL_TO_PASS results ==="
  TOTAL=0
  FAILS=0
  MISSING=0
  while IFS= read -r tname; do
    TOTAL=$((TOTAL+1))
    line=$(grep -F -- "$tname" "$FULL_LOG" \
           | grep -E ' \.\.\. (ok|FAIL|ERROR|skipped)| (PASSED|FAILED|ERROR|SKIPPED)' \
           | head -1)
    if [ -z "$line" ]; then
      echo "  [MISSING] $tname"
      MISSING=$((MISSING+1))
    elif echo "$line" | grep -qE '\.\.\. ok|PASSED'; then
      echo "  [PASS]    $tname"
    else
      verdict=$(echo "$line" | grep -oE '\.\.\. (FAIL|ERROR|skipped[^ ]*)|(FAILED|ERROR|SKIPPED)' | head -1)
      echo "  [FAIL]    $tname  --  $verdict"
      FAILS=$((FAILS+1))
    fi
  done < <(jq -r '.[]' /testbed/.swebench/FAIL_TO_PASS.json)
  echo
  echo "FAIL_TO_PASS summary: $((TOTAL-FAILS-MISSING))/$TOTAL passed, $FAILS failed, $MISSING not found in log"
} | tee "$SUMMARY_LOG"

echo "Full log:    $FULL_LOG"
echo "Summary log: $SUMMARY_LOG"
