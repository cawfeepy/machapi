import json

from agno.tools import Toolkit
from agno.run.base import RunContext
from django.db.models import Count

from machtms.backend.routes.models import Stop


class StopHistoryToolkit(Toolkit):
    """Toolkit for querying stop history at addresses."""

    def __init__(self):
        super().__init__(name="stop_history_toolkit")
        self.register(self.get_similar_stops_for_address)
        self.register(self.get_action_code_frequency)

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

    def get_action_code_frequency(
        self,
        run_context: RunContext,
        address_id: int,
        limit: int = 10,
    ) -> str:
        """Get the frequency of action codes used at an address to suggest the most common one.

        Args:
            address_id: The address ID to look up.
            limit: Maximum number of recent stops to consider.

        Returns:
            JSON string with address_id, has_history, suggested_action, and action_counts.
        """
        organization = run_context.dependencies["organization"]
        # Get the PKs of recent stops first (slicing), then aggregate on them
        recent_pks = list(
            Stop.objects
            .filter(
                organization=organization,
                address_id=address_id,
            )
            .order_by('-timestamp')
            .values_list('pk', flat=True)[:limit]
        )
        action_counts = (
            Stop.objects
            .filter(pk__in=recent_pks)
            .values('action')
            .annotate(count=Count('action'))
            .order_by('-count')
        )

        counts_dict = {row['action']: row['count'] for row in action_counts}
        has_history = len(counts_dict) > 0
        suggested_action = next(iter(counts_dict), None) if has_history else None

        return json.dumps({
            "address_id": address_id,
            "has_history": has_history,
            "suggested_action": suggested_action,
            "action_counts": counts_dict,
        })
