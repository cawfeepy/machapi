import base64
import mimetypes
from pathlib import Path
from email import encoders
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from machtms.backend.loads.models import Load

from typing import TypeAlias, Tuple, List
from io import BufferedReader, BytesIO

from django.conf import settings

FileName: TypeAlias = str
FileDataList: TypeAlias = List[Tuple[FileName, BytesIO]]
FilePathList: TypeAlias = List[Tuple[FileName, Path]]


class MessageBuilder:
    def __init__(self,
                 load: Load,
                 sender: str,
                 to: str,
                 files: FileDataList | FilePathList
                 ):
        self.load = load
        self.sender = sender
        if settings.DEBUG:
            self.to = 'dev@machtms.com'
        else:
            self.to = to
        self.files = files


    def _get_content_type(self, filename) -> Tuple[str, str]:
        content_type, encoding = mimetypes.guess_type(filename)
        if content_type is None or encoding is not None:
            content_type = 'application/octet-stream'
        main_type, sub_type = content_type.split('/', 1)
        return main_type, sub_type


    def _create_subject(self):
        customer_name = self.load.customer.company_name
        load_number = self.load.reference
        subject = f"{customer_name} / Shipment# {load_number} [Invoice]"
        self.subject = subject
        return self


    def _create_body(self):
        M = (
                "Hello,\n\n"
                f"Attached you'll find the documents for shipment# {self.load.reference}"
                )
        self.body_message = M
        return self


    def _attach_bytes_to_message(self, message, file_data: Tuple[FileName, BufferedReader|BytesIO]):
        filename, fb = file_data
        main_type, sub_type = self._get_content_type(filename)

        if main_type == 'application':
            msg = MIMEBase(main_type, sub_type)
            msg.set_payload(fb.read())
            msg.add_header('Content-Disposition', 'attachment', filename=filename)
            encoders.encode_base64(msg)
            message.attach(msg)
        else:
            raise ValueError(f"Invalid file type for {filename}: must be a .pdf or other valid application/* type")


    def _create_multipart_email(self):
        message = MIMEMultipart()
        message['to'] = self.to # type: ignore
        message['from'] = self.sender # type: ignore

        self._create_subject()._create_body()
        message['subject'] = self.subject # type: ignore
        msg = MIMEText(self.body_message) # type: ignore
        message.attach(msg)
        return message


    def construct_email(self):
        _email = self._create_multipart_email()
        for filename, file in self.files:
            if isinstance(file, BytesIO):
                self._attach_bytes_to_message(_email, (filename, file))
            elif isinstance(file, Path):
                with open(file, 'rb') as fb:
                    self._attach_bytes_to_message(_email, (filename, fb))
            else:
                raise TypeError("file is not a valid type")
        raw = base64.urlsafe_b64encode(_email.as_bytes()).decode()
        return {'raw': raw}


