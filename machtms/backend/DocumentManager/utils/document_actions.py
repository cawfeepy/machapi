import logging
from machtms.backend.DocumentManager.utils import generate_truncated_hash
from machtms.backend.loads.models import Load
logger = logging.getLogger(__name__)
import io
from typing import Literal, TypedDict
from django.utils.timezone import activate
import pymupdf


AcceptedMimeTypes = Literal[
    'jpeg',
    'jpg',
    'png'
]

class FilenameObjectKeyMeta(TypedDict):
    filename: str
    object_key: str

class DocumentActions:
    def __init__(self):
        pass


    @staticmethod
    def format_customer_name(customer_name: str) -> str:
        """
        Rename a file according to the following rules:
        1. Remove any occurrence (except in the first word) of these keywords (case-insensitive):
            "Logistics", "Transportation", "Trans", "Group", "LLC".
        2. Remove disallowed punctuation characters:
            . , _ - ! @ # $ % ^ & * ( ) = +
        3. If the resulting name contains more than three words, keep only the first three.
        4. Convert the remaining words to PascalCase.
            - For words that are entirely uppercase (e.g. "JB"), preserve their casing.
            - Otherwise, capitalize the first letter and lowercase the rest.

        Args:
            filename (str): The original file name.

        Returns:
            str: The renamed file string in PascalCase.
        """
        # Characters to strip from the entire string:
        disallowed_chars = ".,_-!@#$%^&*()=+"

        # Remove the disallowed characters using str.translate.
        cleaned = customer_name.translate(str.maketrans('', '', disallowed_chars))

        # Remove extra spaces and split the string into individual words.
        words = cleaned.strip().split()

        # Keywords to remove (if they are not the first word). Comparison is case-insensitive.
        remove_keywords = {"logistics", "transportation", "trans", "group", "llc"}

        # Process words: Keep the word if it's the first word,
        # or if it's not one of the disallowed keywords.
        filtered_words = []
        for i, word in enumerate(words):
            if i > 0 and word.lower() in remove_keywords:
                continue  # skip this word
            filtered_words.append(word)

        # If there are more than three words after filtering, only keep the first three.
        if len(filtered_words) > 3:
            filtered_words = filtered_words[:3]

        # Helper function for converting a single word into the proper Pascal format.
        # If a word is already all-uppercase, return it as is; else, capitalize.
        def format_word(word: str) -> str:
            if word.isupper():
                return word
            return word.capitalize()

        # Join the processed words into the final PascalCase string.
        new_name = "".join(format_word(word) for word in filtered_words)
        return new_name


    @staticmethod
    def create_pdf(image_stream, filetype: AcceptedMimeTypes) -> io.BytesIO:
        image = pymupdf.open(stream=image_stream, filetype=filetype)
        # rect = image[0].rect
        imgPDF = pymupdf.open('pdf', image.convert_to_pdf())
        pdf_stream = io.BytesIO()
        imgPDF.save(pdf_stream)
        pdf_stream.seek(0)

        imgPDF.close()
        return pdf_stream


    @staticmethod
    def merge_streams(streams: list[io.BytesIO]) -> io.BytesIO:
        """ F """
        merged = pymupdf.open()
        logger.debug(streams)
        for stream in streams:
            logger.debug(stream)
            _pdf = pymupdf.open(stream=stream, filetype='pdf')
            merged.insert_pdf(_pdf)
            _pdf.close()

        merged_pdf_io = io.BytesIO()
        merged.save(merged_pdf_io)
        merged_pdf_io.seek(0)
        merged.close()
        return merged_pdf_io


    @staticmethod
    def rename_document_for_load(load: Load, category: str|None = None) -> str:
        """ returns a formatted filename without an extension """
        if load.customer is None:
            raise ValueError("Customer name is None")
        pdf_documents = load.documents.filter(category=category)
        document_count = pdf_documents.count()
        suffix: str|None = None

        if document_count > 1:
            document_count += 1
            suffix = f"[{document_count}]"

        fmt_customer = DocumentActions.format_customer_name(load.customer.company_name)
        document_name = f"{fmt_customer}_{load.invoice_id}_{load.reference}" + (f"_{category}" if category else "")
        if suffix is not None:
            document_name += suffix
        return document_name


    @staticmethod
    def create_filename_objkey_pair(load, category, ext='pdf') -> FilenameObjectKeyMeta:
        filename = DocumentActions.rename_document_for_load(load, category)
        hash_id = generate_truncated_hash()
        object_key = f"{filename}-{hash_id}.{ext}"
        return {
            "filename": filename + f".{ext}",
            "object_key": object_key
        }
