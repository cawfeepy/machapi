import io
import os
import pymupdf
import logging
from pathlib import Path
from unittest.mock import patch
from rest_framework.test import APIClient, APITestCase
from PIL import Image, ImageDraw, ImageFont
from machtms.core.envctrl import env
from machtms.backend.DocumentManager.models import PostShipmentDocument
from machtms.backend.DocumentManager.tasks import upload_to_shipment
from machtms.core.utils import s3_utils as s3
from machtms.backend.GmailAPI.utils.gather import DocumentAggregator
from machtms.core.factories.document_manager import DirectUploadFactory, SessionUploadLogFactory 
from machtms.core.factories.loads import LoadFactory
from machtms.backend.GmailAPI.utils.service import GmailService
from machtms.backend.GmailAPI.utils.send import MessageBuilder

logger = logging.getLogger(__name__)

_download_from_buffer = s3.__name__ + ".download_from_buffer"
_upload_to_post = s3.__name__ + ".upload_to_post_shipment_bucket"
test_documents = Path(env.BASE_DIR) / 'test_documents'


class DocumentFactory:
    def __init__(self, load):
        self.load = load
        self.files = []


    def cleanUp(self):
        print("Cleaning up DocumentFactory")
        for file in self.files:
            os.remove(file)


    def create_image_upload(self, fp, category):
        """ create a DirectUpload factory for images"""
        self.generate_image(fp)
        self.files.append(fp)
        return DirectUploadFactory(
            filename=os.path.basename(fp),
            object_key=fp,
            content_type="image/",
            category=category,
            load=self.load
        )


    def create_pdf_upload(self, fp, category):
        """ create a DirectUpload factory for pdfs"""
        self.generate_pdf(fp)
        self.files.append(fp)
        return DirectUploadFactory(
            filename=os.path.basename(fp),
            object_key=fp,
            content_type="application/pdf",
            category=category,
            load=self.load
        )


    def generate_pdf(self, fp:str, text_content:str="hello"):
        LETTER_SIZE = (612, 792)

        doc = pymupdf.open()
        page = doc.new_page(width=LETTER_SIZE[0], height=LETTER_SIZE[1])

        text = text_content
        position = (72, 72)  # 1 inch from top-left
        page.insert_text(position, text, fontsize=12)
        doc.save(fp)
        doc.close()


    def generate_image(self, fp:str):
        img = Image.new('RGB', (800, 400), color='white')
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except:
            font = ImageFont.load_default()
        draw.text((50, 50), "Hello, this is a test image!", fill='black', font=font)
        img.save(fp)


def mock_download_from_buffer(object_key, *args, **kwargs):
    logger.debug(object_key)
    with open(object_key, 'rb') as inf:
        stream = io.BytesIO(inf.read())
        return stream
    return stream


def mock_upload_to_buffer(object_key, file_buffer):
    to_path = test_documents / object_key
    logger.debug(to_path)
    with open(to_path, 'wb') as inf:
        inf.write(file_buffer.read())
    return to_path


class TestDocumentManager(APITestCase):
    """
        To mock files from the uploads bucket,
        begin each file with:
            DM_RC_1.pdf
            DM_POD_1.jpeg
            DM_POD_1[1].pdf
            DM_POD_2.jpeg

        Test out uploading/conversion
            DM_RC_1.pdf
            DM_POD_1.jpeg

        Test out upload/conversion/merging
        different formats:
            DM_POD_1.jpeg
            DM_POD_1[1].pdf

        Test out renaming with duplicate
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # Manually create and start the patchers.
        cls.patcher_upload = patch(_upload_to_post, side_effect=mock_upload_to_buffer)
        cls.patcher_download = patch(_download_from_buffer, side_effect=mock_download_from_buffer)
        cls.mock_upload = cls.patcher_upload.start()
        cls.mock_download = cls.patcher_download.start()
 

    @classmethod
    def tearDownClass(cls) -> None:
        cls.patcher_upload.stop()
        cls.patcher_download.stop()
        super().tearDownClass()

    def setUp(self):
        """
        We will need to create a SessionUploadLog.
        We will attach a load to it. The task
        will work with that load when needed

        Create sample DirectUpload models for each
        test_document we are testing
        """
        self.load = LoadFactory()
        self.session = SessionUploadLogFactory(load=self.load)
        self.document_factory = DocumentFactory(load=self.load)


    def tearDown(self):
        print(f'Tearing down: {self._testMethodName}')
        self.mock_upload.assert_called()
        self.mock_download.assert_called()
        self.document_factory.cleanUp()


    def test_one_pod_pdf(self):
        print(f"TESTING: {self._testMethodName}")
        # scenario-1: upload a POD pdf
        dm_pod = test_documents / "DM_POD_1.pdf"
        upload = self.document_factory.create_pdf_upload(dm_pod, 'POD')
        upload_to_shipment(
            self.session.pk,
            [upload.pk]
        )
        PostShipmentDocument.objects.all().count == 1


    def test_two_pod_jpeg(self):
        print(f"TESTING: {self._testMethodName}")
        # scenario-2: upload 2 POD jpegs
        dm_pod_1 = test_documents / "DM_POD_1.jpeg"
        dm_pod_2 = test_documents / "DM_POD_2.jpeg"
        U1 = self.document_factory.create_image_upload(dm_pod_1, 'POD')
        U2 = self.document_factory.create_image_upload(dm_pod_2, 'POD')
        upload_to_shipment(
            self.session.pk,
            [U1.pk, U2.pk]
        )
        PostShipmentDocument.objects.all().count == 1


    def test_one_rc(self):
        print(f"TESTING: {self._testMethodName}")
        # scenario-3: upload 1 rate con
        dm_rc_1 = test_documents / "DM_RC_1.pdf"
        U1 = self.document_factory.create_pdf_upload(dm_rc_1, 'RC')
        upload_to_shipment(
            self.session.pk,
            [U1.pk]
        )
        PostShipmentDocument.objects.all().count == 1


    def test_with_gmail(self):
        dm_rc_1 = test_documents / "DM_RC_1.pdf"
        dm_pod_1 = test_documents / "DM_POD_1.jpeg"
        dm_pod_2 = test_documents / "DM_POD_2.jpeg"
        U1 = self.document_factory.create_pdf_upload(dm_rc_1, 'RC')
        U2 = self.document_factory.create_image_upload(dm_pod_1, 'POD')
        U3 = self.document_factory.create_image_upload(dm_pod_2, 'POD')
        upload_to_shipment(
            self.session.pk,
        )
        documents = DocumentAggregator.aggregate_documents(
            self.load.invoice_id
        )
        service = GmailService.setup_installed_flow()
        message = MessageBuilder(
            self.load,
            'lpt.cm01@gmail.com',
            'dev@machtms.com',
            documents
        ).construct_email()
        service.send_email(message)


