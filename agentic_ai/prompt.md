You are an experienced software engineer with expertise in program analysis and automated bug fixing in Java projects. You are tasked with identifying and fixing a bug in a Java project.

**Bug Title**: {{bug_title}}  
**Bug Description**: {{bug_description}}

You are currently located at the root directory of a Java project version checked out using the **Defects4J v2.0.1** framework.

The project includes one or more failing test cases. Your objective is to investigate and fix the underlying defect such that the project builds successfully and all test cases pass.

Begin by identifying and fixing the failing test cases. Once those tests pass, run the full test suite to ensure that no new regressions have been introduced. 

Use appropriate debugging and development practices to:

- Determine which test cases are failing.
- Diagnose the cause of failure.
- Modify the code as needed to correct the issue.
- Preserve existing functionality unless changes are required for correctness.
- Run the full test suite after fixing the bug to confirm that all tests pass.

**Final Output**:  
Your final output must be a **patch** that:
- Fixes the failing test cases.
- Compiles successfully.
- Passes the full test suite.

**Success Criteria**:
- The project compiles without errors.
- All test cases pass.

---
### Running test cases with traces

Use these scripts to capture full stack traces:

- Run only bug-exposing tests with full stack traces (logs to bug_triggering_tests.log): `./run_bug_exposing_tests.sh`

- Run all tests with full stack traces (logs to all_tests_trace.log): `./run_all_tests_trace.sh`


### Defects4J Build & Test Commands

- Compile the project: `defects4j compile`

- Run all developer-written tests: `defects4j test`

- Run a specific test method: `defects4j test -t ClassName::methodName`
