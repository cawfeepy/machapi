from django.urls import path
from .views import (
    CreateSessionView,
    DocumentUploadView,
    DocumentUploadCompleteView,
    ProcessSessionView,
    ProcessSessionPdfView,
    ProcessDocumentPdfView,
    SessionListView,
    SessionDetailView,
    DocumentDetailView,
)

urlpatterns = [
    path('ratecon/sessions/', CreateSessionView.as_view(), name='ratecon-create-session'),
    path('ratecon/sessions/list/', SessionListView.as_view(), name='ratecon-session-list'),
    path('ratecon/sessions/<int:session_id>/', SessionDetailView.as_view(), name='ratecon-session-detail'),
    path('ratecon/sessions/<int:session_id>/process/', ProcessSessionView.as_view(), name='ratecon-process-session'),
    path('ratecon/sessions/<int:session_id>/process-pdf/', ProcessSessionPdfView.as_view(), name='ratecon-process-session-pdf'),
    path('ratecon/documents/upload/', DocumentUploadView.as_view(), name='ratecon-document-upload'),
    path('ratecon/documents/upload-complete/', DocumentUploadCompleteView.as_view(), name='ratecon-upload-complete'),
    path('ratecon/documents/<int:document_id>/', DocumentDetailView.as_view(), name='ratecon-document-detail'),
    path('ratecon/documents/<int:document_id>/process-pdf/', ProcessDocumentPdfView.as_view(), name='ratecon-process-document-pdf'),
]
