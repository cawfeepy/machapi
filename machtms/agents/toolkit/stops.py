from agno.tools import Toolkit
from agno.run.base import RunContext

from machtms.backend.routes.models import Stop


class StopHistoryToolkit(Toolkit):
    """Toolkit for querying stop history at addresses."""

    def __init__(self):
        super().__init__(name="stop_history_toolkit")
        self.register(self.get_similar_stops_for_address)

    def get_similar_stops_for_address(
        self,
        run_context: RunContext,
        address_id: int,
        limit: int = 5,
    ) -> str:
        """Get recent stops at the same address to help infer the correct action.

        For example, if an address is always used for LIVE LOAD, the stop builder
        can infer that the next stop at that address should also be LIVE LOAD.

        Args:
            address_id: The address ID to look up.
            limit: Maximum number of recent stops to return.

        Returns:
            Formatted list of recent stops at this address with their actions.
        """
        organization = run_context.dependencies["organization"]
        stops = (
            Stop.objects
            .filter(
                organization=organization,
                address_id=address_id,
            )
            .select_related('address')
            .order_by('-timestamp')[:limit]
        )

        if not stops:
            return f"No previous stops found at address ID {address_id}."

        lines = [f"Recent stops at address ID {address_id}:"]
        for s in stops:
            lines.append(
                f"  Stop #{s.stop_number}: {s.get_action_display()} ({s.action}) "
                f"| Date: {s.start_range.strftime('%m/%d/%Y %I:%M %p')}"
            )
        return "\n".join(lines)
