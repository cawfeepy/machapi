# gather.py
"""
Gather the invoice, PODs, and rate cons (if applicable)
"""
from __future__ import annotations

import io
from django.conf import settings
from operator import call
import pymupdf
from typing import Tuple
from machtms.backend.loads.serializers import LoadPDFSerializer
from machtms.backend.loads.models import Load
from machtms.backend.DocumentManager.utils import s3
from machtms.core.utils.invoicing.main import generate_invoice

import logging

L = logging. getLogger(__name__)

def to_customer_shorthand(customer_name: str) -> str:
    """Convert customer name to shorthand format."""
    # Characters to strip from the entire string:
    disallowed_chars = ".,_-!@#$%^&*()=+"
    cleaned = customer_name.translate(str.maketrans('', '', disallowed_chars))
    words = cleaned.strip().split()
    remove_keywords = {"logistics", "transportation", "trans", "group", "llc"}
    filtered_words = []
    for i, word in enumerate(words):
        if i > 0 and word.lower() in remove_keywords:
            continue
        filtered_words.append(word)
    if len(filtered_words) > 3:
        filtered_words = filtered_words[:3]
    def format_word(word: str) -> str:
        if word.isupper():
            return word
        return word.capitalize()
    return "".join(format_word(word) for word in filtered_words)


class DocumentAggregator:

    pod_documents: Tuple[str, io.BytesIO] | None # later do: <> | list[Tuple[str, BytesIO]]
    ratecon: Tuple[str, io.BytesIO] | None
    invoice: Tuple[str, io.BytesIO]

    def __init__(self, invoice_id, organization):
        self.load = Load.objects.prefetch_related('documents').get(
            organization_id=organization,
            invoice_id=invoice_id
        )

    # def __call__(self):
    #     pass

    @classmethod
    def aggregate_documents(cls, invoice_id, organization=None):
        _self: DocumentAggregator = cls(invoice_id,organization)
        _all = _self._gather_documents()
        return _all


    def _gather_documents(self) -> list[Tuple[str, io.BytesIO]]:
        """
        calls _get_pod_documents()._get_ratecon_documents()._get_invoice_documents()
        """
        callables = (
            self._get_pod_documents,
            self._get_ratecon_documents,
            self._get_invoice_document
        )
        for callable in callables:
            callable()
        gathered: list[Tuple[str, io.BytesIO]] = []
        if self.ratecon is not None:
            gathered.append(self.ratecon)
        if self.pod_documents is not None:
            gathered.append(self.pod_documents)
        gathered.append(self.invoice)
        return gathered


    def _get_from_s3(self, object_key: str, bucket_name=settings.AWS_POST_SHIPMENT_BUCKET) -> io.BytesIO:
        stream = s3.download_from_buffer(object_key, bucket_name=bucket_name)
        return stream


    def create_filename(self, document_category, default_filename):
        customer_shorthand = to_customer_shorthand(self.load.customer.company_name)
        basename = (
            f"{customer_shorthand}_"
            f"{self.load.invoice_id}_"
            f"{self.load.reference}"
        )
        if document_category == 'CUSTOMER_RATECON':
            return f"{basename}.pdf"
        elif document_category == 'INVOICE':
            return f"{basename}_invoice.pdf"
        elif document_category == 'POD' or document_category == 'LUMPER':
            return f"{basename}_POD.pdf"
        return default_filename


    def _merge_documents(self, files: list[io.BytesIO]) -> io.BytesIO:
        """ F """
        merged = pymupdf.open()
        L.debug(files)
        for stream in files:
            L.debug(stream)
            _pdf = pymupdf.open(stream=stream, filetype='pdf')
            merged.insert_pdf(_pdf)
            _pdf.close()

        merged_pdf_io = io.BytesIO()
        merged.save(merged_pdf_io)
        merged_pdf_io.seek(0)
        merged.close()
        return merged_pdf_io


    def _get_pod_documents(self) -> DocumentAggregator:
        """ get all the category:POD files, and merge them """
        _pod_documents = self.load.documents.filter(category__in=['POD', 'LUMPER']).all()
        L.debug(_pod_documents)
        if _pod_documents:
            mergeable: list[io.BytesIO] = []
            for pod in _pod_documents:
                L.debug(pod.object_key)
                stream = self._get_from_s3(pod.object_key)
                mergeable.append(stream)
            merged = self._merge_documents(mergeable)
            filename = self.create_filename('POD', None)
            self.pod_documents = (filename, merged)
        else:
            self.pod_documents = None
        return self


    def _get_ratecon_documents(self) -> DocumentAggregator:
        """ get ratecon """
        recent_ratecon = self.load.documents.order_by('-created_on').filter(category='RC').first()
        if recent_ratecon is not None:
            filename = self.create_filename(
                recent_ratecon.category,
                recent_ratecon.filename
            )
            self.ratecon = (filename, self._get_from_s3(recent_ratecon.object_key))
        else:
            self.ratecon = None
        return self


    def _get_invoice_document(self) -> DocumentAggregator:
        """ generate and return invoice data in bytes """
        load_data = LoadPDFSerializer(self.load).data
        filename = self.create_filename('INVOICE', None)
        invoice = generate_invoice(load_data)
        self.invoice = (filename, invoice)
        return self

    # TODO
    def merge_all_documents_into_pdf(self):
        # some brokers want all files in one single PDF.
        # give user that option
        pass
