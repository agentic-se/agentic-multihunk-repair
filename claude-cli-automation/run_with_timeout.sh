#!/bin/bash

# Shell wrapper to run automated_claude_cli.py with timeout
# Usage: ./run_with_timeout.sh <timeout_minutes> <bug_id> [additional_args...]

set -e

# Source SDKMAN! (works in non-interactive shells)
export SDKMAN_DIR="$HOME/.sdkman"
[[ -s "$HOME/.sdkman/bin/sdkman-init.sh" ]] && source "$HOME/.sdkman/bin/sdkman-init.sh"

sdk use java 8.0.412-amzn

if [ $# -lt 2 ]; then
    echo "Usage: $0 <timeout_minutes> <bug_id> [additional_args...]"
    echo "Example: $0 30 Chart_1 --verbose"
    exit 1
fi

TIMEOUT_MIN=$1
BUG_ID=$2
shift 2  # Remove first two arguments, keep the rest

echo "Running automated_claude_cli.py with ${TIMEOUT_MIN}m timeout for bug: ${BUG_ID}"

# Run the Python script with timeout and verbose logging
timeout "${TIMEOUT_MIN}m" python3 automated_claude_cli.py "${BUG_ID}" --verbose "$@"

exit_code=$?

if [ $exit_code -eq 124 ]; then
    echo "Process timed out after ${TIMEOUT_MIN} minutes"
elif [ $exit_code -eq 0 ]; then
    echo "Process completed successfully"
else
    echo "Process failed with exit code: $exit_code"
fi

exit $exit_code