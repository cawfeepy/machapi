from django.urls import path
from .views import generate_queue_hash, get_presigned_url, list_shipment_documents, notify_upload_complete, poll_postshipment_complete, post_upload_document, start_session, register_upload

urlpatterns = [
    path('generate-queue-hash/',
         generate_queue_hash,
         name='api^generate_queue_hash'),

    path('start_session/<int:invoice_id>/',
         start_session,
         name='api.start_session'),

    # path('start_session/',
    #      start_session,
    #      name='api.start_session'),

    path('register_upload/',
         register_upload,
         name='api.register_upload'
         ),

    path('get-presigned-url/',
         get_presigned_url,
         name='api.get_presigned_url'),

    path('upload-document/',
         post_upload_document,
         name='api.post_upload_document'),

    path('notify_upload_complete',
         notify_upload_complete,
         name='api.notify_upload_complete'),

    path('poll_postshipment_complete/<int:session_id>/',
         poll_postshipment_complete,
         name='api.poll_shipment_complete'),

    path('list_shipment_documents/<int:load_id>/',
         list_shipment_documents,
         name='api.list_shipment_documents')
]
