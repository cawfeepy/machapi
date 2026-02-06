from collections.abc import Iterator

from .client import AgentClient


class NonStreamingChatController:
    """Controller that sends queries via the non-streaming endpoint."""

    def __init__(self, base_url: str):
        self.client = AgentClient(base_url)

    def send(self, query: str) -> str:
        """Send a query and return the full response text."""
        try:
            data = self.client.chat(query)
            return data.get('response', '')
        except Exception as exc:
            return f"[Error] {exc}"


class StreamingChatController:
    """Controller that sends queries via the SSE streaming endpoint."""

    def __init__(self, base_url: str):
        self.client = AgentClient(base_url)

    def send(self, query: str) -> Iterator[str]:
        """Send a query and yield response chunks as they arrive."""
        try:
            yield from self.client.stream(query)
        except Exception as exc:
            yield f"[Error] {exc}"
