import io
import logging
from operator import itemgetter
from pydoc import Doc
from typing import (List, Literal, Mapping,
    NamedTuple, TypedDict, Tuple, cast, Optional)
from celery import shared_task
from django.conf import settings
from django.db.models import QuerySet
from machtms.backend.loads.models import Load
from machtms.backend.DocumentManager.models import (
    DirectUpload, PostShipmentDocument, SessionUploadLog, UploadLog)
from machtms.backend.DocumentManager.utils import s3
from machtms.backend.DocumentManager.utils.document_actions import DocumentActions


logger = logging.getLogger(__name__)

class DirectUploadDict(TypedDict):
    file_buffer: io.BytesIO
    direct_upload: DirectUpload | None

class PostShipmentUpstream(NamedTuple):
    """
        file_buffer: io.BytesIO
        category: str
        content_type: str
        filename: str
        object_key: str
        referenced_upload: DirectUpload | List[DirectUpload]
    """
    file_buffer: io.BytesIO
    category: str
    content_type: str
    filename: str
    object_key: str
    referenced_upload: DirectUpload | List[DirectUpload]

UploadKeys = Literal['POD', 'CUSTOMER_RATECON', 'RECEIPT', 'LUMPER', 'OTHER']
DirectUploadMapping = Mapping[UploadKeys, List[DirectUploadDict]]



def process_uploads(uploaded_documents: List[DirectUploadDict]) -> List[DirectUploadDict]:
    """
    Two Inner functions specific to processing PODs
    - get_by_image: get the content_type image/{png, jpg, jpeg}
    - create PDFs from those images
    - return to those PDF memory objects
    """

    def create_pdf(upload: DirectUploadDict):
        file_buffer = upload.get('file_buffer')
        direct_upload = upload.get('direct_upload')

        if direct_upload is None:
            raise Exception("direct_upload is None")

        _,ext = direct_upload.content_type.split('/')
        # TODO: deal with exception if for some reason PDF conversion fails
        try:
            file_buffer = DocumentActions.create_pdf(file_buffer, ext)
        except Exception as e:
            pass
        return file_buffer


    def get_by_filetype(
        document_obj: DirectUploadDict,
        filetype='image/'
    ):
        direct_upload: DirectUpload | None = document_obj.get('direct_upload', None)
        if direct_upload is None:
            logger.debug("direct_upload is None")
            return False
        logger.debug(direct_upload.content_type.startswith(filetype))
        return direct_upload.content_type.startswith(filetype)


    image_uploads = list(filter(
        lambda item: get_by_filetype(item, 'image/'),
        uploaded_documents))
    logger.debug(image_uploads)
    pdf_uploads = list(filter(
        lambda item: get_by_filetype(item, 'application/pdf'),
        uploaded_documents))
    logger.debug(pdf_uploads)
    pdfs: list[DirectUploadDict] = [{
        **image,
        'file_buffer': create_pdf(image)
    } for image in image_uploads]
    combo_pdfs = pdfs + pdf_uploads
    return combo_pdfs



def prepare_post_shipment(
        load: Load,
        file_buffer: io.BytesIO,
        category: str,
        referenced_upload: Optional[DirectUpload | List[DirectUpload]]
        ) -> PostShipmentUpstream:
    if referenced_upload is None:
        raise Exception("referenced_upload must be something")
    logger.debug(load)
    fn_objkey_pair = DocumentActions.create_filename_objkey_pair(
        load, category)
    return PostShipmentUpstream(
        category=category,
        content_type='application/pdf',
        file_buffer=file_buffer,
        referenced_upload=referenced_upload,
        **fn_objkey_pair
    )


def update_upload_log_status(ref_upload: DirectUpload|List[DirectUpload], upload_logs: QuerySet[UploadLog], success=True):
    """
    Updates the status of upload logs related to the given ref_upload.

    Args:
        ref_upload (list[Upload] | DirectUpload): The upload(s) to update.
        upload_logs (QuerySet): The queryset for all upload logs.
        success (bool): Whether the operation was successful. Sets status to 'C' if True, else 'E'.
    """
    status = 'success' if success else 'error'

    if isinstance(ref_upload, list):
        upload_log_ids = [upload.upload_log.pk for upload in ref_upload]
        upload_logs.all().filter(pk__in=upload_log_ids).update(status=status)

    elif isinstance(ref_upload, DirectUpload):
        ref_upload.upload_log.status = status
        ref_upload.upload_log.save()


# ====================
# Documents will be processed as such:
#
# firstly, documents in category::POD will be merged
# into one single PDF document
#
# Other documents will be processed individually into separate
# PDFs
# ....................
#
# ====================
# The workflow of this task will be as follows:
#
# [1] Get the SessionUploadLog.
#       - will have foreign reverse relationships with UploadLog
# get the list of upload_ids.
#
# [2.0] Create DirectUploadMapping
#   *** DirectUploadMapping has this shape:
#   { 'CATEGORY': [DirectUploadDict<{file_buffer: BytesIO, direct_upload: DirectUpload}>] }
# [2.1] Iterate through these upload_ids.
#       - Downloads the file from s3, stored as a BytesIO stream. (file_buffer=)
#       - appends(DirectUploadMapping) -> [... { [direct_upload.category]: DirectUploadMapping<...>}]
# [3.0] Given List[DirectUploadMapping] -> iterate through key:List[DirectUploadDict]
# [3.1] process these DirectUploadDict -> convert all images to PDFs
# [3.2] prepare these documents for uploading to PDF bucket with PostshipmentUpstream
#
def upload_to_shipment(
    session_id,
):
    session_log = SessionUploadLog.objects.select_related('load').prefetch_related('upload_logs').get(id=session_id)
    upload_logs = session_log.upload_logs.all()
    upload_ids = list(upload_logs.values_list("direct_upload", flat=True).order_by().distinct())
    load = session_log.load

    uploaded_documents: DirectUploadMapping = {}

    # with the direct_upload.pk, download the file stream from S3 upload bucket
    # set [direct_upload.category]:[{file_buffer, direct_upload}]
    for _id in upload_ids:
        direct_upload = DirectUpload.objects.get(pk=_id)
        file_buffer = s3.download_from_buffer(
            direct_upload.object_key,
            bucket_name=settings.AWS_UPLOAD_BUCKET
        )
        uploaded_documents.setdefault(direct_upload.category, []).append({
            'file_buffer': file_buffer,
            'direct_upload': direct_upload
        })


    prepared_documents: list[PostShipmentUpstream] = []
    # merge POD documents into one PDF file and prepare to PostShipmentUpstream object
    # Individual files will easily be prepared to PostShipmentUpstream object
    for key, fileuploads in uploaded_documents.items():
        # if it's a POD category, merge these documents
            # handle a concoction of images or pdfs and merge
        if key == 'POD':
            # POD direct_uploads will be merged
            try:
                document_uploads = process_uploads(fileuploads)
                logger.debug(document_uploads)

                pairs = map(itemgetter('file_buffer', 'direct_upload'), document_uploads)
                streams, pod_uploads = cast(Tuple[List[io.BytesIO], List[DirectUpload]], map(list, zip(*pairs)))

                logger.debug(streams)
                merged = DocumentActions.merge_streams(streams)

                # ---
                prepared: PostShipmentUpstream = prepare_post_shipment(
                    load, merged, key, pod_uploads
                )
                prepared_documents.append(prepared)
            except Exception as e: # FromProcessUploadsError
                # mark all uploads as an error?
                pairs = map(itemgetter('file_buffer', 'direct_upload'), fileuploads)
                _, uploads = cast(Tuple[List[io.BytesIO], List[DirectUpload]], map(list, zip(*pairs)))
                update_upload_log_status(uploads, upload_logs, success=False)
                logger.warning(e)
        else:
            for upload in document_uploads:
                prepared = prepare_post_shipment(
                    load, upload['file_buffer'], key, upload['direct_upload'])
                prepared_documents.append(prepared)


    for document in prepared_documents:
        try:
            object_key = s3.upload_to_post_shipment_bucket(
                document.object_key,
                document.file_buffer
            )
            obj = PostShipmentDocument(
                    load=load,
                    object_key=object_key,
                    filename=document.filename,
                    category=document.category,
                    content_type=document.content_type
                )
            obj.save()
            ref_upload = document.referenced_upload
            update_upload_log_status(ref_upload, upload_logs, success=True)
        except Exception as e:
            update_upload_log_status(ref_upload, upload_logs, success=False)
            logger.error(
                "Something happened while saving" +
                " documents to the PostShipmentDocument." +
                f"\nHere's the error: {e}"
            )


### --- TASKS
@shared_task(bind=True)
def task_upload_to_shipment(task, upload_log_id):
    pass
    # upload_to_shipment(upload_log_id)


def retry_upload_to_shipment():
    pass



# TODO: make inference of document based on text content
# Get the S3UploadImage data
# process the image(s)
# make inference to see which load it belongs to
# upload to post_shipment_bucket
# save to PostShipmentDocument
def task_shipment_process_upload():
    pass
