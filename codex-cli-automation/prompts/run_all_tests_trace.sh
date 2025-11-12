#!/bin/bash
set -x

# Source SDKMAN! (works in non-interactive shells)
export SDKMAN_DIR="$HOME/.sdkman"
[[ -s "$HOME/.sdkman/bin/sdkman-init.sh" ]] && source "$HOME/.sdkman/bin/sdkman-init.sh"

# Enable offline mode
sdk offline enable

sdk use java 8.0.412-amzn

# Compile project
defects4j compile

# Get test classpath
CP="$(defects4j export -p cp.test)"

# Log file for all developer-written tests
# Use ISO 8601 basic format - a sortable log format
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOGFILE="all_tests_trace.${TIMESTAMP}.log"

# Clear old log
> "$LOGFILE"

# Run all test classes
for cls in $(defects4j export -p tests.all | sort -u); do
  echo "Running $cls" | tee -a "$LOGFILE"
  java -cp "$CP" org.junit.runner.JUnitCore "$cls" >> "$LOGFILE" 2>&1
done

echo "Log saved to: $LOGFILE"
