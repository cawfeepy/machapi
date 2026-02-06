from django.urls import path

from .views import AgentChatView, AgentStreamView

urlpatterns = [
    path('agents/chat/', AgentChatView.as_view(), name='agent-chat'),
    path('agents/stream/', AgentStreamView.as_view(), name='agent-stream'),
]
