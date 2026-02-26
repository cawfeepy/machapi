from agno.run.base import RunContext
from agno.tools import Toolkit

from machtms.backend.RateConParser.models import ParsedRateCon


class DocumentParsingToolkit(Toolkit):
    """Toolkit for managing rate confirmation document state."""

    def __init__(self):
        super().__init__(name="document_parsing_toolkit")
        self.register(self.assign_load_to_parsed_ratecon)

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
