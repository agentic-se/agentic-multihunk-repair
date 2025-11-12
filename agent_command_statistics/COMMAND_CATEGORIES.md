# High-Level Command Categories

**Purpose:** Encompassing categories for trajectory analysis.

**Categories are data-driven** based on actual command usage.

---

## Overall Category Distribution

**Total command executions:** 64,380
**Categories:** 16

| Rank | Category | Count | % | Commands Included |
|------|----------|-------|---|-------------------|
| 1 | **WRITE** | 18,721 | 29.08% | `sed`, `replace`, `edit`, `todo_write`, `write_file` |
| 2 | **READ** | 11,985 | 18.62% | `read_file`, `head`, `tail`, `cat`, `nl` |
| 3 | **TEST** | 10,225 | 15.88% | `defects4j test`, `run_bug_exposing_tests.sh`, `run_all_tests_trace.sh`, `mvn test`, `test_runner.sh` |
| 4 | **BUILD** | 6,715 | 10.43% | `defects4j compile`, `java`, `javac`, `ant`, `javap` |
| 5 | **SEARCH_CONTENT** | 4,938 | 7.67% | `grep`, `search_file_content`, `rg`, `search_class`, `search_code` |
| 6 | **SEARCH_FILES** | 4,300 | 6.68% | `glob`, `ls`, `find`, `list_directory` |
| 7 | **NAVIGATE** | 2,567 | 3.99% | `cd`, `pwd` |
| 8 | **UTIL** | 2,002 | 3.11% | `echo`, `true`, `xargs`, `wc`, `[` |
| 9 | **VCS** | 1,822 | 2.83% | `git diff`, `git show`, `git checkout`, `git log`, `git restore` |
| 10 | **PATCH** | 457 | 0.71% | `apply_patch`, `applypatch`, `patch`, `diff`, `apply_fix.sh` |
| 11 | **FILE_OPS** | 246 | 0.38% | `rm`, `cp`, `mkdir`, `chmod`, `mv` |
| 12 | **DEFECTS4J_OTHER** | 202 | 0.31% | `defects4j export`, `defects4j info`, `defects4j checkout`, `defects4j`, `defects4j version` |
| 13 | **OTHER** | 66 | 0.10% | `\n`, `-n`, `n`, `#`, `'` |
| 14 | **SCRIPT** | 59 | 0.09% | `python`, `perl`, `jshell`, `bash`, `python3` |
| 15 | **TRANSFORM** | 41 | 0.06% | `cut`, `tr`, `sort`, `uniq` |
| 16 | **WEB** | 34 | 0.05% | `google_web_search`, `web_fetch`, `curl` |

---

## Detailed Category Breakdown

### WRITE — 18,721 executions (29.08%)

| Rank | Command | Count | % of category |
|------|---------|-------|---------------|
| 1 | `sed` | 7,612 | 40.66% |
| 2 | `replace` | 4,682 | 25.01% |
| 3 | `edit` | 3,075 | 16.43% |
| 4 | `todo_write` | 2,491 | 13.31% |
| 5 | `write_file` | 670 | 3.58% |
| 6 | `awk` | 191 | 1.02% |

### READ — 11,985 executions (18.62%)

| Rank | Command | Count | % of category |
|------|---------|-------|---------------|
| 1 | `read_file` | 8,765 | 73.13% |
| 2 | `head` | 1,646 | 13.73% |
| 3 | `tail` | 947 | 7.90% |
| 4 | `cat` | 281 | 2.34% |
| 5 | `nl` | 268 | 2.24% |
| 6 | `tee` | 41 | 0.34% |
| 7 | `read_many_files` | 21 | 0.18% |
| 8 | `od` | 6 | 0.05% |
| 9 | `hexdump` | 6 | 0.05% |
| 10 | `strings` | 4 | 0.03% |

### TEST — 10,225 executions (15.88%)

| Rank | Command | Count | % of category |
|------|---------|-------|---------------|
| 1 | `defects4j test` | 7,345 | 71.83% |
| 2 | `run_bug_exposing_tests.sh` | 2,288 | 22.38% |
| 3 | `run_all_tests_trace.sh` | 561 | 5.49% |
| 4 | `mvn test` | 22 | 0.22% |
| 5 | `test_runner.sh` | 3 | 0.03% |
| 6 | `test_bug.sh` | 1 | 0.01% |
| 7 | `debug.sh` | 1 | 0.01% |
| 8 | `debug_test.sh` | 1 | 0.01% |
| 9 | `run.sh` | 1 | 0.01% |
| 10 | `run_single_test.sh` | 1 | 0.01% |
| 11 | `run_test.sh` | 1 | 0.01% |

### BUILD — 6,715 executions (10.43%)

| Rank | Command | Count | % of category |
|------|---------|-------|---------------|
| 1 | `defects4j compile` | 4,300 | 64.04% |
| 2 | `java` | 1,259 | 18.75% |
| 3 | `javac` | 661 | 9.84% |
| 4 | `ant` | 410 | 6.11% |
| 5 | `javap` | 39 | 0.58% |
| 6 | `mvn` | 15 | 0.22% |
| 7 | `mvn compile` | 10 | 0.15% |
| 8 | `gradlew` | 10 | 0.15% |
| 9 | `jar` | 6 | 0.09% |
| 10 | `mvn clean` | 4 | 0.06% |
| 11 | `gradle` | 1 | 0.01% |

### SEARCH_CONTENT — 4,938 executions (7.67%)

| Rank | Command | Count | % of category |
|------|---------|-------|---------------|
| 1 | `grep` | 3,747 | 75.88% |
| 2 | `search_file_content` | 1,175 | 23.80% |
| 3 | `rg` | 13 | 0.26% |
| 4 | `search_class` | 1 | 0.02% |
| 5 | `search_code` | 1 | 0.02% |
| 6 | `egrep` | 1 | 0.02% |

### SEARCH_FILES — 4,300 executions (6.68%)

| Rank | Command | Count | % of category |
|------|---------|-------|---------------|
| 1 | `glob` | 1,703 | 39.60% |
| 2 | `ls` | 1,412 | 32.84% |
| 3 | `find` | 721 | 16.77% |
| 4 | `list_directory` | 464 | 10.79% |

### NAVIGATE — 2,567 executions (3.99%)

| Rank | Command | Count | % of category |
|------|---------|-------|---------------|
| 1 | `cd` | 2,537 | 98.83% |
| 2 | `pwd` | 30 | 1.17% |

### UTIL — 2,002 executions (3.11%)

| Rank | Command | Count | % of category |
|------|---------|-------|---------------|
| 1 | `echo` | 1,213 | 60.59% |
| 2 | `true` | 455 | 22.73% |
| 3 | `xargs` | 163 | 8.14% |
| 4 | `wc` | 74 | 3.70% |
| 5 | `[` | 22 | 1.10% |
| 6 | `timeout` | 17 | 0.85% |
| 7 | `exit_plan_mode` | 12 | 0.60% |
| 8 | `task` | 7 | 0.35% |
| 9 | `sleep` | 7 | 0.35% |
| 10 | `printf` | 4 | 0.20% |
| 11 | `md5sum` | 3 | 0.15% |
| 12 | `seq` | 3 | 0.15% |
| 13 | `export` | 3 | 0.15% |
| 14 | `if` | 2 | 0.10% |
| 15 | `do` | 2 | 0.10% |
| 16 | `done` | 2 | 0.10% |
| 17 | `return` | 1 | 0.05% |
| 18 | `read` | 1 | 0.05% |
| 19 | `exit` | 1 | 0.05% |
| 20 | `break` | 1 | 0.05% |
| 21 | `case` | 1 | 0.05% |
| 22 | `set` | 1 | 0.05% |
| 23 | `for` | 1 | 0.05% |
| 24 | `while` | 1 | 0.05% |
| 25 | `then` | 1 | 0.05% |
| 26 | `else` | 1 | 0.05% |
| 27 | `fi` | 1 | 0.05% |
| 28 | `create-test-report.sh` | 1 | 0.05% |
| 29 | `iconv` | 1 | 0.05% |

### VCS — 1,822 executions (2.83%)

| Rank | Command | Count | % of category |
|------|---------|-------|---------------|
| 1 | `git diff` | 702 | 38.53% |
| 2 | `git show` | 339 | 18.61% |
| 3 | `git checkout` | 237 | 13.01% |
| 4 | `git log` | 175 | 9.60% |
| 5 | `git restore` | 143 | 7.85% |
| 6 | `git status` | 102 | 5.60% |
| 7 | `git stash` | 78 | 4.28% |
| 8 | `git add` | 15 | 0.82% |
| 9 | `git commit` | 11 | 0.60% |
| 10 | `git reset` | 10 | 0.55% |
| 11 | `git rev-parse` | 3 | 0.16% |
| 12 | `git ls-files` | 3 | 0.16% |
| 13 | `git apply` | 2 | 0.11% |
| 14 | `git clone` | 2 | 0.11% |

### PATCH — 457 executions (0.71%)

| Rank | Command | Count | % of category |
|------|---------|-------|---------------|
| 1 | `apply_patch` | 382 | 83.59% |
| 2 | `applypatch` | 28 | 6.13% |
| 3 | `patch` | 27 | 5.91% |
| 4 | `diff` | 18 | 3.94% |
| 5 | `apply_fix.sh` | 1 | 0.22% |
| 6 | `gnuapply` | 1 | 0.22% |

### FILE_OPS — 246 executions (0.38%)

| Rank | Command | Count | % of category |
|------|---------|-------|---------------|
| 1 | `rm` | 117 | 47.56% |
| 2 | `cp` | 80 | 32.52% |
| 3 | `mkdir` | 20 | 8.13% |
| 4 | `chmod` | 11 | 4.47% |
| 5 | `mv` | 11 | 4.47% |
| 6 | `file` | 4 | 1.63% |
| 7 | `touch` | 2 | 0.81% |
| 8 | `git rm` | 1 | 0.41% |

### DEFECTS4J_OTHER — 202 executions (0.31%)

| Rank | Command | Count | % of category |
|------|---------|-------|---------------|
| 1 | `defects4j export` | 172 | 85.15% |
| 2 | `defects4j info` | 21 | 10.40% |
| 3 | `defects4j checkout` | 4 | 1.98% |
| 4 | `defects4j` | 1 | 0.50% |
| 5 | `defects4j version` | 1 | 0.50% |
| 6 | `defects4j clean` | 1 | 0.50% |
| 7 | `defects4j query` | 1 | 0.50% |
| 8 | `choosedepedencyversion.sh` | 1 | 0.50% |

### OTHER — 66 executions (0.10%)

| Rank | Command | Count | % of category |
|------|---------|-------|---------------|
| 1 | `\n` | 8 | 12.12% |
| 2 | `-n` | 5 | 7.58% |
| 3 | `n` | 4 | 6.06% |
| 4 | `#` | 4 | 6.06% |
| 5 | `'` | 3 | 4.55% |
| 6 | `-t` | 3 | 4.55% |
| 7 | `***` | 3 | 4.55% |
| 8 | `i’ll` | 3 | 4.55% |
| 9 | `+` | 2 | 3.03% |
| 10 | `next}` | 1 | 1.52% |
| 11 | `')` | 1 | 1.52% |
| 12 | `throw` | 1 | 1.52% |
| 13 | `ed` | 1 | 1.52% |
| 14 | `
perl` | 1 | 1.52% |
| 15 | `$1){n` | 1 | 1.52% |
| 16 | `infinity.equals(text)` | 1 | 1.52% |
| 17 | `-infinity.equals(text))` | 1 | 1.52% |
| 18 | `g'` | 1 | 1.52% |
| 19 | `field` | 1 | 1.52% |
| 20 | `second` | 1 | 1.52% |
| 21 | `millisecond` | 1 | 1.52% |
| 22 | `
log=$(ls` | 1 | 1.52% |
| 23 | `
grep` | 1 | 1.52% |
| 24 | `
awk` | 1 | 1.52% |
| 25 | `
start=$(grep` | 1 | 1.52% |
| 26 | `
end=$((start+400))` | 1 | 1.52% |
| 27 | `
range_start=$(grep` | 1 | 1.52% |
| 28 | `
sed` | 1 | 1.52% |
| 29 | `!knownconstants.contains(n.getstring())` | 1 | 1.52% |
| 30 | `@@` | 1 | 1.52% |
| 31 | `compiling` | 1 | 1.52% |
| 32 | `scope` | 1 | 1.52% |
| 33 | `isdeclared("` | 1 | 1.52% |
| 34 | `sort)` | 1 | 1.52% |
| 35 | `-c` | 1 | 1.52% |
| 36 | `compiling,` | 1 | 1.52% |
| 37 | `nextelementsibling:` | 1 | 1.52% |
| 38 | `exit}'` | 1 | 1.52% |
| 39 | `+import` | 1 | 1.52% |
| 40 | `t` | 1 | 1.52% |

### SCRIPT — 59 executions (0.09%)

| Rank | Command | Count | % of category |
|------|---------|-------|---------------|
| 1 | `python` | 32 | 54.24% |
| 2 | `perl` | 14 | 23.73% |
| 3 | `jshell` | 7 | 11.86% |
| 4 | `bash` | 4 | 6.78% |
| 5 | `python3` | 2 | 3.39% |

### TRANSFORM — 41 executions (0.06%)

| Rank | Command | Count | % of category |
|------|---------|-------|---------------|
| 1 | `cut` | 28 | 68.29% |
| 2 | `tr` | 6 | 14.63% |
| 3 | `sort` | 4 | 9.76% |
| 4 | `uniq` | 3 | 7.32% |

### WEB — 34 executions (0.05%)

| Rank | Command | Count | % of category |
|------|---------|-------|---------------|
| 1 | `google_web_search` | 24 | 70.59% |
| 2 | `web_fetch` | 7 | 20.59% |
| 3 | `curl` | 3 | 8.82% |

---

## Per-Agent Category Distribution

### Qwen

**Total commands:** 15,074

| Rank | Category | Count | % |
|------|----------|-------|---|
| 1 | **READ** | 3,558 | 23.60% |
| 2 | **NAVIGATE** | 2,394 | 15.88% |
| 3 | **TEST** | 2,391 | 15.86% |
| 4 | **WRITE** | 2,249 | 14.92% |
| 5 | **BUILD** | 1,549 | 10.28% |
| 6 | **SEARCH_CONTENT** | 1,268 | 8.41% |
| 7 | **SEARCH_FILES** | 963 | 6.39% |
| 8 | **VCS** | 394 | 2.61% |
| 9 | **FILE_OPS** | 143 | 0.95% |
| 10 | **UTIL** | 72 | 0.48% |
| 11 | **OTHER** | 30 | 0.20% |
| 12 | **PATCH** | 29 | 0.19% |
| 13 | **DEFECTS4J_OTHER** | 19 | 0.13% |
| 14 | **SCRIPT** | 11 | 0.07% |
| 15 | **WEB** | 3 | 0.02% |
| 16 | **TRANSFORM** | 1 | 0.01% |

### Gemini

**Total commands:** 13,149

| Rank | Category | Count | % |
|------|----------|-------|---|
| 1 | **WRITE** | 4,858 | 36.95% |
| 2 | **READ** | 3,106 | 23.62% |
| 3 | **TEST** | 2,458 | 18.69% |
| 4 | **BUILD** | 1,620 | 12.32% |
| 5 | **VCS** | 415 | 3.16% |
| 6 | **SEARCH_FILES** | 373 | 2.84% |
| 7 | **SEARCH_CONTENT** | 236 | 1.79% |
| 8 | **DEFECTS4J_OTHER** | 33 | 0.25% |
| 9 | **WEB** | 29 | 0.22% |
| 10 | **FILE_OPS** | 21 | 0.16% |

### Claude

**Total commands:** 19,089

| Rank | Category | Count | % |
|------|----------|-------|---|
| 1 | **READ** | 4,388 | 22.99% |
| 2 | **WRITE** | 4,109 | 21.53% |
| 3 | **TEST** | 2,844 | 14.90% |
| 4 | **BUILD** | 2,357 | 12.35% |
| 5 | **SEARCH_FILES** | 2,025 | 10.61% |
| 6 | **SEARCH_CONTENT** | 1,804 | 9.45% |
| 7 | **VCS** | 994 | 5.21% |
| 8 | **UTIL** | 209 | 1.09% |
| 9 | **NAVIGATE** | 173 | 0.91% |
| 10 | **DEFECTS4J_OTHER** | 99 | 0.52% |
| 11 | **FILE_OPS** | 64 | 0.34% |
| 12 | **PATCH** | 16 | 0.08% |
| 13 | **TRANSFORM** | 3 | 0.02% |
| 14 | **WEB** | 2 | 0.01% |
| 15 | **SCRIPT** | 2 | 0.01% |

### Codex

**Total commands:** 17,068

| Rank | Category | Count | % |
|------|----------|-------|---|
| 1 | **WRITE** | 7,505 | 43.97% |
| 2 | **TEST** | 2,532 | 14.83% |
| 3 | **UTIL** | 1,721 | 10.08% |
| 4 | **SEARCH_CONTENT** | 1,630 | 9.55% |
| 5 | **BUILD** | 1,189 | 6.97% |
| 6 | **SEARCH_FILES** | 939 | 5.50% |
| 7 | **READ** | 933 | 5.47% |
| 8 | **PATCH** | 412 | 2.41% |
| 9 | **DEFECTS4J_OTHER** | 51 | 0.30% |
| 10 | **SCRIPT** | 46 | 0.27% |
| 11 | **TRANSFORM** | 37 | 0.22% |
| 12 | **OTHER** | 36 | 0.21% |
| 13 | **VCS** | 19 | 0.11% |
| 14 | **FILE_OPS** | 18 | 0.11% |

---

## Category Distribution Across Agents

| Rank | Category | Qwen | Gemini | Claude | Codex | Total |
|------|----------|------|--------|--------|-------|-------|
| 1 | **WRITE** | 2,249 | 4,858 | 4,109 | 7,505 | 18,721 |
| 2 | **READ** | 3,558 | 3,106 | 4,388 | 933 | 11,985 |
| 3 | **TEST** | 2,391 | 2,458 | 2,844 | 2,532 | 10,225 |
| 4 | **BUILD** | 1,549 | 1,620 | 2,357 | 1,189 | 6,715 |
| 5 | **SEARCH_CONTENT** | 1,268 | 236 | 1,804 | 1,630 | 4,938 |
| 6 | **SEARCH_FILES** | 963 | 373 | 2,025 | 939 | 4,300 |
| 7 | **NAVIGATE** | 2,394 | 0 | 173 | 0 | 2,567 |
| 8 | **UTIL** | 72 | 0 | 209 | 1,721 | 2,002 |
| 9 | **VCS** | 394 | 415 | 994 | 19 | 1,822 |
| 10 | **PATCH** | 29 | 0 | 16 | 412 | 457 |
| 11 | **FILE_OPS** | 143 | 21 | 64 | 18 | 246 |
| 12 | **DEFECTS4J_OTHER** | 19 | 33 | 99 | 51 | 202 |
| 13 | **OTHER** | 30 | 0 | 0 | 36 | 66 |
| 14 | **SCRIPT** | 11 | 0 | 2 | 46 | 59 |
| 15 | **TRANSFORM** | 1 | 0 | 3 | 37 | 41 |
| 16 | **WEB** | 3 | 29 | 2 | 0 | 34 |

---

*Generated by `categorize_commands.py`*
