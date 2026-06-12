from agno.run.base import RunContext
from agno.tools import Toolkit

from machtms.backend.RateConParser.models import RateConDocument


class DocumentParsingToolkit(Toolkit):
    """Toolkit for managing rate confirmation document state."""

    def __init__(self):
        super().__init__(name="document_parsing_toolkit")
        self.register(self.assign_load_to_document)

    def assign_load_to_document(self, run_context: RunContext, load_id: int) -> str:
        """Link a created load to the RateConDocument record for the current document.

        The document ID is read from run_context.dependencies["ratecon_id"].

        Args:
            load_id: The Load ID to associate with the document.

        Returns:
            Confirmation message or error string.
        """
        ratecon_id = run_context.dependencies.get("ratecon_id")
        if ratecon_id is None:
            return "Error: ratecon_id not found in run context dependencies."

        try:
            doc = RateConDocument.objects.get(pk=ratecon_id)
        except RateConDocument.DoesNotExist:
            return f"Error: No RateConDocument found for ID {ratecon_id}."

        doc.load_id = load_id
        doc.save(update_fields=['load_id', 'updated_at'])
        return f"Successfully linked load {load_id} to RateConDocument {ratecon_id}."
