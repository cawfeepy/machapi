"""
Django Management Command for Test Management Tool.

This command provides an interactive interface for discovering and running
tests in the Django project. It supports both APITestCase (Django REST Framework)
and pytest test patterns.

Usage:
    python manage.py runtests

The command will:
1. Prompt for test type selection (APITestCase, pytest, or all)
2. Display available tests with keyboard shortcuts
3. Accept user input to run specific tests
4. Execute the selected test(s) and display results
"""

import os
import signal
import sys
from typing import Dict, List, Any, Optional

from django.core.management.base import BaseCommand, CommandError

# Import test tools
try:
    from test_tools.test_discovery import TestDiscovery, TestModule
    from test_tools.test_runner import TestRunner
    from test_tools.display import Display, print_test_list
except ImportError as e:
    raise CommandError(f"Could not import test tools: {e}")


class Command(BaseCommand):
    """
    Django management command for interactive test running.

    Provides a keyboard-driven interface to discover and run tests
    with minimal keystrokes using ergonomic shortcuts.
    """

    help = "Interactive test runner with keyboard shortcuts for Django and pytest tests."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.display = Display()
        self.discovery = None
        self.runner = None
        self.key_map: Dict[str, Dict[str, Any]] = {}
        self.current_framework: str = ''
        self._interrupted = False

    def add_arguments(self, parser):
        """Add command-line arguments."""
        # Note: --no-color is already provided by Django's BaseCommand
        # Note: -v/--verbosity is already provided by Django's BaseCommand
        parser.add_argument(
            '--no-clear',
            action='store_true',
            help='Disable screen clearing between operations',
        )
        parser.add_argument(
            '--path',
            type=str,
            default='machtms',
            help='Path to search for tests (relative to project root or absolute). Defaults to "machtms".',
        )

    def handle(self, *args, **options):
        """Main command handler."""
        # Set up display options (--no-color is built-in to Django's BaseCommand)
        if options.get('no_color'):
            self.display = Display(use_colors=False)

        # Django's --verbosity is 0-3, treat 2+ as verbose
        self.verbose = options.get('verbosity', 1) >= 2
        self.clear_screen = not options.get('no_clear', False)

        # Set up signal handler for graceful exit
        signal.signal(signal.SIGINT, self._handle_interrupt)

        try:
            # Initialize discovery and runner
            search_path = options.get('path')
            self.discovery = TestDiscovery(search_path=search_path)
            self.runner = TestRunner()

            # Main loop
            while not self._interrupted:
                try:
                    self._run_main_menu()
                except KeyboardInterrupt:
                    self._handle_interrupt(None, None)
                    break

        except Exception as e:
            raise CommandError(f"Error running tests: {e}")

        self.stdout.write(self.style.SUCCESS("\nExiting test runner. Goodbye!"))

    def _handle_interrupt(self, signum, frame):
        """Handle Ctrl+C gracefully."""
        self._interrupted = True
        self.stdout.write("\n")
        self.display.print_warning("Interrupted by user.")

    def _clear_if_enabled(self):
        """Clear screen if enabled."""
        if self.clear_screen:
            self.display.clear_screen()

    def _run_main_menu(self):
        """Display and handle the main menu."""
        self._clear_if_enabled()
        self.display.print_header("Test Runner")

        # Check pytest availability
        pytest_available = self.runner.is_pytest_available()

        # Display menu options
        print("\nSelect test type:")
        self.display.print_menu_option("1", "APITestCase (Django REST Framework)")

        if pytest_available:
            self.display.print_menu_option("2", "pytest (including pytest-django)")
            self.display.print_menu_option("3", "All tests")
        else:
            print(self.display._colorize(
                "  (2) pytest - not installed",
                self.display._colorize("", "\033[2m")
            ))
            self.display.print_warning(self.runner.get_pytest_install_message())

        self.display.print_menu_option("q", "Quit")

        # Get user choice
        choice = self.display.get_input("\nEnter choice")

        if choice == 'q' or choice.lower() == 'quit':
            self._interrupted = True
            return

        if choice == '1':
            self._run_apitestcase_mode()
        elif choice == '2' and pytest_available:
            self._run_pytest_mode()
        elif choice == '3' and pytest_available:
            self._run_all_mode()
        else:
            self.display.print_error("Invalid choice. Please try again.")
            self.display.wait_for_key()

    def _discover_and_display_tests(
        self,
        framework: str
    ) -> tuple[List[TestModule], Dict[str, Dict[str, Any]]]:
        """
        Discover tests and display them with shortcuts.

        Args:
            framework: 'apitestcase', 'pytest', or 'all'.

        Returns:
            Tuple of (modules, key_map).
        """
        self.discovery.reset()

        if framework == 'apitestcase':
            modules = self.discovery.discover_apitestcase_tests()
        elif framework == 'pytest':
            modules = self.discovery.discover_pytest_tests()
        else:
            api_modules, pytest_modules = self.discovery.discover_all_tests()
            modules = api_modules + pytest_modules

        if not modules:
            self.display.print_warning("No tests found.")
            return [], {}

        key_map = self.discovery.assign_keys(modules)

        # Display tests
        self._clear_if_enabled()
        self.display.print_header(f"Available Tests ({framework.upper()})")

        print_test_list(
            self.display,
            modules,
            show_db_markers=(framework == 'pytest')
        )

        # Display summary
        if framework == 'all':
            api_modules_only = [m for m in modules if any(
                c.framework in ('apitestcase', 'django') for c in m.classes
            )]
            pytest_modules_only = [m for m in modules if any(
                c.framework == 'pytest' for c in m.classes
            ) or m.standalone_functions]
            summary = self.discovery.get_test_summary(api_modules_only, pytest_modules_only)
        else:
            summary = self.discovery.get_test_summary(
                modules if framework == 'apitestcase' else [],
                modules if framework == 'pytest' else []
            )

        print()
        self.display.print_info(summary)

        return modules, key_map

    def _run_apitestcase_mode(self):
        """Run in APITestCase mode."""
        self.current_framework = 'apitestcase'
        modules, key_map = self._discover_and_display_tests('apitestcase')

        if not modules:
            self.display.wait_for_key()
            return

        self.key_map = key_map
        self._test_selection_loop('apitestcase')

    def _run_pytest_mode(self):
        """Run in pytest mode."""
        self.current_framework = 'pytest'
        modules, key_map = self._discover_and_display_tests('pytest')

        if not modules:
            self.display.wait_for_key()
            return

        self.key_map = key_map
        self._test_selection_loop('pytest')

    def _run_all_mode(self):
        """Run in all-tests mode."""
        self.current_framework = 'all'
        modules, key_map = self._discover_and_display_tests('all')

        if not modules:
            self.display.wait_for_key()
            return

        self.key_map = key_map
        self._test_selection_loop('all')

    def _test_selection_loop(self, framework: str):
        """
        Loop for selecting and running tests.

        Args:
            framework: The test framework being used.
        """
        while not self._interrupted:
            print()
            self.display.print_prompt(
                "Enter key to run test, 'a' for all, 'r' to refresh, or 'q' to quit"
            )

            user_input = self.display.get_input("Selection")

            if user_input == 'q' or user_input.lower() == 'quit':
                break

            if user_input == 'r' or user_input.lower() == 'refresh':
                # Rediscover and redisplay tests
                self._discover_and_display_tests(framework)
                continue

            if user_input == 'a' or user_input.lower() == 'all':
                self._run_all_framework_tests(framework)
                continue

            # Look up the key
            if user_input in self.key_map:
                self._run_single_test(user_input)
            else:
                self.display.print_error(f"Invalid key: '{user_input}'. Please try again.")

    def _run_single_test(self, key: str):
        """
        Run a single test by its key.

        Args:
            key: The keyboard shortcut key.
        """
        test_info = self.key_map.get(key)
        if not test_info:
            self.display.print_error(f"Key not found: {key}")
            return

        # Build display name
        if test_info['type'] == 'class':
            test_name = f"{test_info['display_path']}::{test_info['class_name']}"
        else:
            if test_info.get('class_name'):
                test_name = f"{test_info['display_path']}::{test_info['class_name']}::{test_info['function_name']}"
            else:
                test_name = f"{test_info['display_path']}::{test_info['function_name']}"

        # Generate and display command
        command = self.runner.get_test_command(test_info, verbose=self.verbose)

        print()
        self.display.print_running(command)
        self.display.print_separator()

        # Run the test
        exit_code = self.runner.run_test_interactive(command)

        # Display result
        self.display.print_separator()
        if exit_code == 0:
            self.display.print_success(f"Test passed: {test_name}")
        elif exit_code == -2:
            self.display.print_warning("Test interrupted by user")
        else:
            self.display.print_error(f"Test failed: {test_name} (exit code: {exit_code})")

        self.display.wait_for_key()

        # Redisplay test list
        self._discover_and_display_tests(self.current_framework)

    def _run_all_framework_tests(self, framework: str):
        """
        Run all tests for the given framework.

        Args:
            framework: 'apitestcase', 'pytest', or 'all'.
        """
        if framework == 'all':
            # Run both
            self.display.print_info("Running all tests (APITestCase + pytest)...")

            # Run Django tests first
            print()
            self.display.print_subheader("Running APITestCase tests...")
            command = self.runner.get_django_all_tests_command(verbose=self.verbose)
            self.display.print_running(command)
            django_exit = self.runner.run_test_interactive(command)

            # Then run pytest if available
            if self.runner.is_pytest_available():
                print()
                self.display.print_subheader("Running pytest tests...")
                command = self.runner.get_pytest_all_tests_command(verbose=self.verbose)
                self.display.print_running(command)
                pytest_exit = self.runner.run_test_interactive(command)
            else:
                pytest_exit = 0

            # Summary
            print()
            if django_exit == 0 and pytest_exit == 0:
                self.display.print_success("All tests passed!")
            else:
                if django_exit != 0:
                    self.display.print_error("Some APITestCase tests failed")
                if pytest_exit != 0:
                    self.display.print_error("Some pytest tests failed")

        else:
            # Run single framework
            command, exit_code = self.runner.run_all_tests(
                framework,
                verbose=self.verbose,
                interactive=True
            )

            print()
            self.display.print_separator()
            if exit_code == 0:
                self.display.print_success(f"All {framework} tests passed!")
            elif exit_code == -2:
                self.display.print_warning("Tests interrupted by user")
            else:
                self.display.print_error(f"Some {framework} tests failed (exit code: {exit_code})")

        self.display.wait_for_key()

        # Redisplay test list
        self._discover_and_display_tests(self.current_framework)
