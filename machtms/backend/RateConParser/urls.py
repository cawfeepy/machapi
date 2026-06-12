from django.urls import path
from .views import (
    ProcessSessionView,
    ProcessSessionPdfView,
    ProcessDocumentPdfView,
    SessionListView,
    SessionDetailView,
    DocumentDetailView,
    PresignedURLEntryPointView,
    CreateSessionFromPresignedView,
    OrphanedDocumentCheckView,
    HideSessionView,
)

urlpatterns = [
    path('ratecon/sessions/list/', SessionListView.as_view(), name='ratecon-session-list'),
    path('ratecon/sessions/<int:session_id>/', SessionDetailView.as_view(), name='ratecon-session-detail'),
    path('ratecon/sessions/<int:session_id>/process/', ProcessSessionView.as_view(), name='ratecon-process-session'),
    path('ratecon/sessions/<int:session_id>/process-pdf/', ProcessSessionPdfView.as_view(), name='ratecon-process-session-pdf'),
    path('ratecon/documents/<int:document_id>/', DocumentDetailView.as_view(), name='ratecon-document-detail'),
    path('ratecon/documents/<int:document_id>/process-pdf/', ProcessDocumentPdfView.as_view(), name='ratecon-process-document-pdf'),
    # Presigned-URL entry point flow
    path('ratecon/presigned-urls/', PresignedURLEntryPointView.as_view(), name='ratecon-presigned-urls'),
    path('ratecon/sessions/from-presigned/', CreateSessionFromPresignedView.as_view(), name='ratecon-session-from-presigned'),
    path('ratecon/orphaned/pre-check/', OrphanedDocumentCheckView.as_view(), name='ratecon-orphaned-precheck'),
    path('ratecon/sessions/<int:session_id>/hide/', HideSessionView.as_view(), name='ratecon-hide-session'),
]
