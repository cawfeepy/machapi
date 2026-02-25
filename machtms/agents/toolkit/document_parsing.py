from agno.run.base import RunContext
from agno.tools import Toolkit

from machtms.backend.RateConParser.models import (
    DocumentStatus,
    ParsedRateCon,
    RateConDocument,
)


class DocumentParsingToolkit(Toolkit):
    """Toolkit for managing rate confirmation document state."""

    def __init__(self):
        super().__init__(name="document_parsing_toolkit")
        self.register(self.update_document_status)
        self.register(self.assign_load_to_parsed_ratecon)

    def update_document_status(self, run_context: RunContext, status: str) -> str:
        """Update the status of the current RateConDocument.

        The document ID is read from run_context.dependencies["ratecon_id"].

        Args:
            status: New status value (must be a valid DocumentStatus choice).

        Returns:
            Confirmation message or error string.
        """
        ratecon_id = run_context.dependencies.get("ratecon_id")
        if ratecon_id is None:
            return "Error: ratecon_id not found in run context dependencies."

        valid_statuses = [choice[0] for choice in DocumentStatus.choices]
        if status not in valid_statuses:
            return f"Error: Invalid status '{status}'. Valid options: {', '.join(valid_statuses)}"

        try:
            doc = RateConDocument.objects.get(pk=ratecon_id)
        except RateConDocument.DoesNotExist:
            return f"Error: RateConDocument with ID {ratecon_id} not found."

        doc.status = status
        doc.save(update_fields=['status', 'updated_at'])
        return f"Successfully updated RateConDocument {ratecon_id} status to '{status}'."

    def assign_load_to_parsed_ratecon(self, run_context: RunContext, load_id: int) -> str:
        """Link a created load to the ParsedRateCon record for the current document.

        The document ID is read from run_context.dependencies["ratecon_id"].

        Args:
            load_id: The Load ID to associate with the parsed content.

        Returns:
            Confirmation message or error string.
        """
        ratecon_id = run_context.dependencies.get("ratecon_id")
        if ratecon_id is None:
            return "Error: ratecon_id not found in run context dependencies."

        try:
            parsed = ParsedRateCon.objects.get(document_id=ratecon_id)
        except ParsedRateCon.DoesNotExist:
            return f"Error: No ParsedRateCon found for document ID {ratecon_id}."

        parsed.load_id = load_id
        parsed.save(update_fields=['load_id'])
        return f"Successfully linked load {load_id} to RateConDocument {ratecon_id}."
