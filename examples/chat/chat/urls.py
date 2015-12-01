from django.conf.urls import include, url
from django.contrib.auth.decorators import login_required

from .views import ChatRoomView, ApiChatRoomMessagesView

urlpatterns = [
    url(r'^(?P<room>[a-z0-9]+)$', ChatRoomView.as_view()),
    url(r'^(?P<room>[a-z0-9]+)/messages$', ApiChatRoomMessagesView.as_view()),
]
