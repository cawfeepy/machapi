from collections.abc import Iterator

import httpx


class AgentClient:
    """HTTP client wrapper for the agent API endpoints."""

    def __init__(self, base_url: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

    def chat(self, query: str) -> dict:
        """POST to the non-streaming endpoint and return the JSON response."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/api/agents/chat/",
                json={"query": query},
            )
            response.raise_for_status()
            return response.json()

    def stream(self, query: str) -> Iterator[str]:
        """POST to the streaming endpoint and yield SSE content chunks."""
        with httpx.Client(timeout=self.timeout) as client:
            with client.stream(
                "POST",
                f"{self.base_url}/api/agents/stream/",
                json={"query": query},
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    parsed = self._parse_sse_line(line)
                    if parsed is None:
                        continue
                    if parsed == "[DONE]":
                        break
                    yield parsed

    @staticmethod
    def _parse_sse_line(line: str) -> str | None:
        """Parse a single SSE data line.

        Returns the content string, or None if the line is not a data line.
        """
        if line.startswith("data: "):
            return line[6:]
        return None
