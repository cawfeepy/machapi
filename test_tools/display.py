"""
Display Utilities for Test Management Tool.

This module provides terminal display utilities for the test management tool,
including colored output and screen management.

Example Usage:
    >>> from machtms.test_tools.display import Display
    >>>
    >>> display = Display()
    >>> display.clear_screen()
    >>> display.print_header("Test Results")
    >>> display.print_success("All tests passed!")
    >>> display.print_error("Test failed!")
"""

import os
import sys
from typing import Optional


class Colors:
    """ANSI color codes for terminal output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'

    # Foreground colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # Bright foreground colors
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'

    # Background colors
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'


class Display:
    """
    Terminal display utilities for the test management tool.

    Provides methods for colored output, screen management, and
    consistent formatting throughout the application.

    Attributes:
        use_colors: Whether to use ANSI color codes in output.
        width: Terminal width for formatting (auto-detected if not specified).
    """

    def __init__(
        self,
        use_colors: Optional[bool] = None,
        width: Optional[int] = None
    ):
        """
        Initialize the Display utility.

        Args:
            use_colors: Whether to use colors. If None, auto-detects.
            width: Terminal width. If None, auto-detects.
        """
        if use_colors is None:
            # Auto-detect: use colors if stdout is a TTY and not on Windows CMD
            self.use_colors = (
                hasattr(sys.stdout, 'isatty') and
                sys.stdout.isatty() and
                os.name != 'nt'
            )
        else:
            self.use_colors = use_colors

        if width is None:
            try:
                self.width = os.get_terminal_size().columns
            except OSError:
                self.width = 80
        else:
            self.width = width

    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled."""
        if self.use_colors:
            return f"{color}{text}{Colors.RESET}"
        return text

    def clear_screen(self) -> None:
        """Clear the terminal screen."""
        if os.name == 'nt':
            os.system('cls')
        else:
            os.system('clear')

    def print_header(self, text: str) -> None:
        """Print a styled header."""
        styled = self._colorize(f"\n{'=' * self.width}", Colors.CYAN)
        print(styled)
        print(self._colorize(f" {text}", Colors.BOLD + Colors.CYAN))
        print(styled)

    def print_subheader(self, text: str) -> None:
        """Print a styled subheader."""
        print(self._colorize(f"\n{text}", Colors.BOLD + Colors.WHITE))
        print(self._colorize('-' * len(text), Colors.DIM))

    def print_success(self, text: str) -> None:
        """Print success message in green."""
        print(self._colorize(f"[PASS] {text}", Colors.GREEN))

    def print_error(self, text: str) -> None:
        """Print error message in red."""
        print(self._colorize(f"[FAIL] {text}", Colors.RED))

    def print_warning(self, text: str) -> None:
        """Print warning message in yellow."""
        print(self._colorize(f"[WARN] {text}", Colors.YELLOW))

    def print_info(self, text: str) -> None:
        """Print info message in blue."""
        print(self._colorize(f"[INFO] {text}", Colors.BLUE))

    def print_key(self, key: str, text: str, is_class: bool = False) -> None:
        """
        Print a test item with its shortcut key.

        Args:
            key: The keyboard shortcut.
            text: The test name.
            is_class: Whether this is a class (uses []) or function (uses <>).
        """
        if is_class:
            key_format = f"[{key}]"
            indent = ""
        else:
            key_format = f"<{key}>"
            indent = "    "

        key_styled = self._colorize(key_format, Colors.BRIGHT_CYAN)
        text_styled = self._colorize(text, Colors.WHITE)
        print(f"{indent}{key_styled} {text_styled}")

    def print_module_header(self, path: str) -> None:
        """Print a module path header."""
        print(self._colorize(f"\n{path}:", Colors.BRIGHT_YELLOW))

    def print_menu_option(self, key: str, text: str) -> None:
        """Print a menu option."""
        key_styled = self._colorize(f"({key})", Colors.BRIGHT_CYAN)
        print(f"  {key_styled} {text}")

    def print_prompt(self, text: str) -> None:
        """Print a prompt message."""
        print(self._colorize(f"\n{text}", Colors.BOLD))

    def print_running(self, command: str) -> None:
        """Print a message showing the command being run."""
        print(self._colorize("\nRunning:", Colors.BOLD + Colors.WHITE))
        print(self._colorize(f"  {command}", Colors.DIM))
        print()

    def print_separator(self) -> None:
        """Print a horizontal separator line."""
        print(self._colorize('-' * self.width, Colors.DIM))

    def format_test_result(self, success: bool, name: str) -> str:
        """
        Format a test result line.

        Args:
            success: Whether the test passed.
            name: The test name.

        Returns:
            Formatted string with color-coded result.
        """
        if success:
            status = self._colorize("[PASS]", Colors.GREEN)
        else:
            status = self._colorize("[FAIL]", Colors.RED)
        return f"{status} {name}"

    def wait_for_key(self, message: str = "Press Enter to continue...") -> None:
        """Wait for user to press Enter."""
        try:
            input(self._colorize(f"\n{message}", Colors.DIM))
        except (EOFError, KeyboardInterrupt):
            print()

    def get_input(self, prompt: str) -> str:
        """
        Get user input with styled prompt.

        Args:
            prompt: The prompt message.

        Returns:
            User input string.
        """
        styled_prompt = self._colorize(f"{prompt}: ", Colors.BOLD)
        try:
            return input(styled_prompt).strip()
        except (EOFError, KeyboardInterrupt):
            return 'q'


def print_test_list(
    display: Display,
    modules: list,
    show_db_markers: bool = False
) -> None:
    """
    Print a formatted test list using the Display utility.

    Args:
        display: The Display instance to use.
        modules: List of TestModule objects.
        show_db_markers: Whether to show [db] markers.
    """
    for module in modules:
        display.print_module_header(module.display_path)

        # Classes and their methods
        for test_class in module.classes:
            display.print_key(test_class.key, test_class.name, is_class=True)

            for method in test_class.methods:
                name = method.name
                if show_db_markers and method.has_django_db_marker:
                    name += " [db]"
                display.print_key(method.key, name, is_class=False)

        # Standalone functions
        for func in module.standalone_functions:
            name = func.name
            if show_db_markers and func.has_django_db_marker:
                name += " [db]"
            display.print_key(func.key, name, is_class=False)
