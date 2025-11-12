#!/usr/bin/env python3
"""
Comprehensive unit tests for ShellCommandParser.

These tests cover:
1. Simple single commands
2. Compound commands with &&, ||, ;
3. Pipes
4. Command substitution
5. Real examples from actual CSV data
6. Edge cases and error handling

Run with: python -m pytest test_shell_command_parser.py -v
Or: python test_shell_command_parser.py

Note: This test file is in the shared parsing/ module and tests the shared parser.
"""

import sys
from pathlib import Path

# Ensure we can import from the bash_parser module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from bash_parser.shell_command_parser import ShellCommandParser, BASHLEX_AVAILABLE


class TestShellCommandParserBasic(unittest.TestCase):
    """Test basic command parsing functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = ShellCommandParser()

    def test_empty_command(self):
        """Test empty command string."""
        self.assertEqual(self.parser.parse_command(""), [])
        self.assertEqual(self.parser.parse_command("   "), [])
        self.assertEqual(self.parser.parse_command("\n"), [])

    def test_simple_single_command(self):
        """Test simple single commands."""
        self.assertEqual(self.parser.parse_command("ls"), ["ls"])
        self.assertEqual(self.parser.parse_command("cat"), ["cat"])
        self.assertEqual(self.parser.parse_command("echo"), ["echo"])

    def test_command_with_arguments(self):
        """Test commands with arguments (should ignore arguments)."""
        self.assertEqual(self.parser.parse_command("ls -la /tmp"), ["ls"])
        self.assertEqual(self.parser.parse_command("cat file.txt"), ["cat"])
        self.assertEqual(self.parser.parse_command("echo hello world"), ["echo"])

    def test_two_token_commands_defects4j(self):
        """Test defects4j commands (require 2 tokens)."""
        self.assertEqual(
            self.parser.parse_command("defects4j test"),
            ["defects4j test"]
        )
        self.assertEqual(
            self.parser.parse_command("defects4j compile"),
            ["defects4j compile"]
        )
        self.assertEqual(
            self.parser.parse_command("defects4j export"),
            ["defects4j export"]
        )
        # With arguments
        self.assertEqual(
            self.parser.parse_command("defects4j test -t FooTest"),
            ["defects4j test"]
        )
        self.assertEqual(
            self.parser.parse_command("defects4j export -p cp.test"),
            ["defects4j export"]
        )

    def test_two_token_commands_git(self):
        """Test git commands (require 2 tokens)."""
        self.assertEqual(
            self.parser.parse_command("git diff"),
            ["git diff"]
        )
        self.assertEqual(
            self.parser.parse_command("git status"),
            ["git status"]
        )
        self.assertEqual(
            self.parser.parse_command("git add file.txt"),
            ["git add"]
        )
        self.assertEqual(
            self.parser.parse_command("git commit -m 'message'"),
            ["git commit"]
        )

    def test_two_token_commands_other(self):
        """Test other two-token commands."""
        self.assertEqual(
            self.parser.parse_command("npm install"),
            ["npm install"]
        )
        self.assertEqual(
            self.parser.parse_command("mvn clean"),
            ["mvn clean"]
        )
        self.assertEqual(
            self.parser.parse_command("docker run"),
            ["docker run"]
        )


class TestShellCommandParserCompound(unittest.TestCase):
    """Test compound command parsing (&&, ||, ;, |)."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = ShellCommandParser()

    def test_and_operator(self):
        """Test && operator."""
        result = self.parser.parse_command("cmd1 && cmd2")
        self.assertEqual(result, ["cmd1", "cmd2"])

        result = self.parser.parse_command("cmd1 && cmd2 && cmd3")
        self.assertEqual(result, ["cmd1", "cmd2", "cmd3"])

    def test_or_operator(self):
        """Test || operator."""
        result = self.parser.parse_command("cmd1 || cmd2")
        self.assertEqual(result, ["cmd1", "cmd2"])

        result = self.parser.parse_command("cmd1 || cmd2 || cmd3")
        self.assertEqual(result, ["cmd1", "cmd2", "cmd3"])

    def test_semicolon_operator(self):
        """Test ; operator."""
        result = self.parser.parse_command("cmd1 ; cmd2")
        self.assertEqual(result, ["cmd1", "cmd2"])

        result = self.parser.parse_command("cmd1 ; cmd2 ; cmd3")
        self.assertEqual(result, ["cmd1", "cmd2", "cmd3"])

    def test_pipe_operator(self):
        """Test | operator."""
        result = self.parser.parse_command("ls | grep foo")
        self.assertEqual(result, ["ls", "grep"])

        result = self.parser.parse_command("cat file | grep pattern | wc -l")
        self.assertEqual(result, ["cat", "grep", "wc"])

    def test_mixed_operators(self):
        """Test mixed operators."""
        result = self.parser.parse_command("cmd1 && cmd2 || cmd3")
        self.assertIn("cmd1", result)
        self.assertIn("cmd2", result)
        self.assertIn("cmd3", result)


class TestShellCommandParserRealExamples(unittest.TestCase):
    """Test with real examples from CSV data."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = ShellCommandParser()

    def test_real_example_1_simple_defects4j(self):
        """Test: defects4j compile"""
        result = self.parser.parse_command("defects4j compile")
        self.assertEqual(result, ["defects4j compile"])

    def test_real_example_2_defects4j_with_test(self):
        """Test: defects4j test -t org.jfree.chart.plot.junit.CategoryPlotTests::testRemoveRangeMarker"""
        result = self.parser.parse_command(
            "defects4j test -t org.jfree.chart.plot.junit.CategoryPlotTests::testRemoveRangeMarker"
        )
        self.assertEqual(result, ["defects4j test"])

    def test_real_example_3_git_redirect(self):
        """Test: git diff > fix.patch"""
        result = self.parser.parse_command("git diff > fix.patch")
        self.assertEqual(result, ["git diff"])

    def test_real_example_4_git_redirect_with_path(self):
        """Test: git diff > /Users/danielding/Desktop/example_dir/Chart_22/fix.patch"""
        result = self.parser.parse_command(
            "git diff > /Users/danielding/Desktop/example_dir/Chart_22/fix.patch"
        )
        self.assertEqual(result, ["git diff"])

    def test_real_example_5_multiple_defects4j_tests(self):
        """Test: Multiple defects4j test commands chained with &&"""
        cmd = (
            "defects4j test -t org.apache.commons.cli.BasicParserTest::testPropertyOptionGroup && "
            "defects4j test -t org.apache.commons.cli.BasicParserTest::testPropertyOptionUnexpected && "
            "defects4j test -t org.apache.commons.cli.DefaultParserTest::testPropertyOptionGroup && "
            "defects4j test -t org.apache.commons.cli.DefaultParserTest::testPropertyOptionUnexpected && "
            "defects4j test -t org.apache.commons.cli.GnuParserTest::testPropertyOptionGroup && "
            "defects4j test -t org.apache.commons.cli.GnuParserTest::testPropertyOptionUnexpected && "
            "defects4j test -t org.apache.commons.cli.OptionGroupTest::testTwoOptionsFromGroupWithProperties && "
            "defects4j test -t org.apache.commons.cli.PosixParserTest::testPropertyOptionGroup && "
            "defects4j test -t org.apache.commons.cli.PosixParserTest::testPropertyOptionUnexpected"
        )
        result = self.parser.parse_command(cmd)
        # Should extract "defects4j test" once (deduplicated)
        self.assertEqual(result, ["defects4j test"])

    def test_real_example_6_ant_chain(self):
        """Test: ant clean && ant compile.test && defects4j test"""
        result = self.parser.parse_command("ant clean && ant compile.test && defects4j test")
        self.assertEqual(result, ["ant", "defects4j test"])

    def test_real_example_7_multiple_test_commands(self):
        """Test: Multiple different test commands"""
        cmd = (
            "defects4j test -t org.apache.commons.math3.distribution.GammaDistributionTest::testDistributionClone && "
            "defects4j test -t org.apache.commons.math3.distribution.LogNormalDistributionTest::testDistributionClone && "
            "defects4j test -t org.apache.commons.math3.distribution.NormalDistributionTest::testDistributionClone"
        )
        result = self.parser.parse_command(cmd)
        self.assertEqual(result, ["defects4j test"])

    def test_real_example_8_compile_and_test(self):
        """Test: defects4j compile && defects4j test"""
        result = self.parser.parse_command("defects4j compile && defects4j test")
        self.assertEqual(result, ["defects4j compile", "defects4j test"])

    def test_real_example_9_pipe_with_head(self):
        """Test: ls -t all_tests_trace.*.log | head -n 1"""
        result = self.parser.parse_command("ls -t all_tests_trace.*.log | head -n 1")
        self.assertEqual(result, ["ls", "head"])

    def test_real_example_10_git_checkout_long_path(self):
        """Test: git checkout with long paths"""
        cmd = (
            "git checkout /Users/danielding/Desktop/example_dir/Cli_16/src/java/org/apache/commons/cli2/Option.java "
            "/Users/danielding/Desktop/example_dir/Cli_16/src/java/org/apache/commons/cli2/option/OptionImpl.java"
        )
        result = self.parser.parse_command(cmd)
        self.assertEqual(result, ["git checkout"])

    def test_real_example_11_defects4j_compile_flag(self):
        """Test: defects4j compile -c"""
        result = self.parser.parse_command("defects4j compile -c")
        self.assertEqual(result, ["defects4j compile"])

    def test_real_example_12_test_scripts(self):
        """Test: ./run_bug_exposing_tests.sh"""
        result = self.parser.parse_command("./run_bug_exposing_tests.sh")
        self.assertEqual(result, ["run_bug_exposing_tests.sh"])

    def test_real_example_13_test_scripts_trace(self):
        """Test: ./run_all_tests_trace.sh"""
        result = self.parser.parse_command("./run_all_tests_trace.sh")
        self.assertEqual(result, ["run_all_tests_trace.sh"])


class TestShellCommandParserEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = ShellCommandParser()

    def test_command_substitution(self):
        """Test command substitution $(cmd) in a compound command."""
        # Standalone variable assignments are not common in our CSV data
        # Test with a more realistic compound command
        result = self.parser.parse_command("echo start && VAR=$(cat /tmp/file) && echo $VAR")
        # Should extract both echo commands (cat is inside assignment, which we may or may not extract)
        self.assertIn("echo", result)

        # Test command substitution in actual command argument
        result2 = self.parser.parse_command("echo $(cat file)")
        # This should at least extract echo
        self.assertIn("echo", result2)

    def test_environment_variable_assignment(self):
        """Test environment variable assignments."""
        result = self.parser.parse_command("VAR=value cmd")
        # Should extract 'cmd', not 'VAR=value'
        if BASHLEX_AVAILABLE:
            self.assertIn("cmd", result)
            self.assertNotIn("var=value", [r.lower() for r in result])

    def test_quoted_arguments(self):
        """Test commands with quoted arguments."""
        result = self.parser.parse_command('echo "hello world"')
        self.assertEqual(result, ["echo"])

        result = self.parser.parse_command("git commit -m 'fix bug'")
        self.assertEqual(result, ["git commit"])

    def test_background_process(self):
        """Test background process &."""
        result = self.parser.parse_command("cmd &")
        self.assertIn("cmd", result)

    def test_newline_separated_commands(self):
        """Test newline-separated commands."""
        cmd = """cmd1
cmd2
cmd3"""
        result = self.parser.parse_command(cmd)
        # Should extract all commands
        self.assertGreaterEqual(len(result), 1)

    def test_complex_real_world_scenario(self):
        """Test complex real-world scenario."""
        cmd = "defects4j test && cat context || echo 'testing'"
        result = self.parser.parse_command(cmd)
        self.assertIn("defects4j test", result)
        if BASHLEX_AVAILABLE:
            self.assertIn("cat", result)
            self.assertIn("echo", result)

    def test_malformed_command(self):
        """Test malformed commands don't crash."""
        # Should not raise exception
        result = self.parser.parse_command("cmd with unmatched 'quote")
        # May return empty or fallback result, but should not crash
        self.assertIsInstance(result, list)

    def test_special_characters(self):
        """Test commands with special characters."""
        result = self.parser.parse_command("grep 'foo.*bar' file.txt")
        self.assertEqual(result, ["grep"])


class TestShellCommandParserCategorization(unittest.TestCase):
    """Test command categorization."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = ShellCommandParser()

    def test_categorize_defects4j_compile(self):
        """Test categorization of defects4j compile."""
        self.assertEqual(
            self.parser.categorize_command("defects4j compile"),
            "defects4j_compile"
        )

    def test_categorize_defects4j_test(self):
        """Test categorization of defects4j test."""
        self.assertEqual(
            self.parser.categorize_command("defects4j test"),
            "defects4j_test"
        )

    def test_categorize_defects4j_other(self):
        """Test categorization of other defects4j commands."""
        self.assertEqual(
            self.parser.categorize_command("defects4j export"),
            "defects4j_export"
        )

    def test_categorize_git(self):
        """Test categorization of git commands."""
        self.assertEqual(
            self.parser.categorize_command("git diff"),
            "git_inspect"
        )
        self.assertEqual(
            self.parser.categorize_command("git status"),
            "git_inspect"
        )

    def test_categorize_build_tools(self):
        """Test categorization of build tools."""
        self.assertEqual(
            self.parser.categorize_command("mvn clean"),
            "build_clean"
        )
        self.assertEqual(
            self.parser.categorize_command("gradle build"),
            "build_compile"
        )
        self.assertEqual(
            self.parser.categorize_command("ant compile"),
            "build_compile"
        )

    def test_categorize_file_operations(self):
        """Test categorization of file operations."""
        self.assertEqual(
            self.parser.categorize_command("ls"),
            "file_list"
        )
        self.assertEqual(
            self.parser.categorize_command("rm"),
            "file_delete"
        )

    def test_categorize_other(self):
        """Test categorization of other commands."""
        self.assertEqual(
            self.parser.categorize_command("echo"),
            "shell_output"
        )
        self.assertEqual(
            self.parser.categorize_command("cat"),
            "text_view"
        )


class TestShellCommandParserFallback(unittest.TestCase):
    """Test fallback parser when bashlex is not available."""

    def setUp(self):
        """Set up test fixtures with fallback parser."""
        self.parser = ShellCommandParser(use_bashlex=False)

    def test_fallback_simple_command(self):
        """Test fallback with simple command."""
        result = self.parser.parse_command("ls -la")
        self.assertEqual(result, ["ls"])

    def test_fallback_and_operator(self):
        """Test fallback with && operator."""
        result = self.parser.parse_command("cmd1 && cmd2")
        self.assertEqual(result, ["cmd1", "cmd2"])

    def test_fallback_defects4j(self):
        """Test fallback with defects4j."""
        result = self.parser.parse_command("defects4j test")
        self.assertEqual(result, ["defects4j test"])

    def test_fallback_complex(self):
        """Test fallback with complex command."""
        result = self.parser.parse_command("defects4j compile && defects4j test")
        self.assertEqual(result, ["defects4j compile", "defects4j test"])


def run_tests():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestShellCommandParserBasic))
    suite.addTests(loader.loadTestsFromTestCase(TestShellCommandParserCompound))
    suite.addTests(loader.loadTestsFromTestCase(TestShellCommandParserRealExamples))
    suite.addTests(loader.loadTestsFromTestCase(TestShellCommandParserEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestShellCommandParserCategorization))
    suite.addTests(loader.loadTestsFromTestCase(TestShellCommandParserFallback))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print()

    if BASHLEX_AVAILABLE:
        print("✓ bashlex is available - full AST parsing enabled")
    else:
        print("⚠ bashlex not available - using fallback parser")
        print("  Install with: pip install bashlex")

    return result.wasSuccessful()


if __name__ == '__main__':
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
