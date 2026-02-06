import sys
from collections.abc import Iterator

from .controller import NonStreamingChatController, StreamingChatController


class ChatUI:
    """Minimal terminal chat interface for agent interaction."""

    def __init__(self, controller: NonStreamingChatController | StreamingChatController):
        self.controller = controller
        self.is_streaming = isinstance(controller, StreamingChatController)

    def run(self):
        """Main chat loop."""
        self._display_banner()

        while True:
            try:
                user_input = input("\nYou: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                break

            if not user_input:
                continue
            if user_input.lower() in ('quit', 'exit'):
                print("Goodbye!")
                break

            if self.is_streaming:
                self._display_ai_stream(self.controller.send(user_input))
            else:
                response = self.controller.send(user_input)
                self._display_ai_response(response)

    def _display_banner(self):
        print("=" * 50)
        print("  machTMS AI Chat")
        mode = "streaming" if self.is_streaming else "non-streaming"
        print(f"  Mode: {mode}")
        print("  Type 'quit' or 'exit' to leave.")
        print("=" * 50)

    @staticmethod
    def _display_ai_response(response: str):
        print(f"\nAI: {response}")

    @staticmethod
    def _display_ai_stream(stream: Iterator[str]):
        sys.stdout.write("\nAI: ")
        sys.stdout.flush()
        for chunk in stream:
            sys.stdout.write(chunk)
            sys.stdout.flush()
        sys.stdout.write("\n")
        sys.stdout.flush()
