import json

from django.http import JsonResponse, Http404
from django.views.generic import View
from django.views.generic.base import TemplateView

from django_rt.publish import publish
from django_rt.views import RtResourceView

ROOMS = (
    'main',
    'room1',
    'room2',
)

class ChatRoomView(TemplateView):
    template_name = 'chat.html'

    def get(self, request, room=None):
        # Check user has requested a valid room
        if room not in ROOMS:
            raise Http404('Room not found')

        self.room = room

        return super().get(request, room)

class ApiChatRoomMessagesView(RtResourceView):
    messages = {
        'main': [
            {
                'user': '<system>',
                'msg': 'Welcome to Django-RT chat!',
            },
        ],
        'room1': [
            {
                'user': '<system>',
                'msg': 'Welcome to #room1',
            },
        ],
        'room2': [
            {
                'user': '<system>',
                'msg': 'Welcome to #room2',
            },
        ],
    }

    def get(self, request, room=None):
        # Check user has requested a valid room
        if room not in ROOMS:
            raise Http404('Room not found')

        # Return all messages sent to the room
        return JsonResponse({
            'messages': self.messages[room]
        })

    def post(self, request, room=None):
        # Check user has requested a valid room
        if room not in ROOMS:
            raise Http404('Room not found')

        # Get JSON message object
        msgJson = request.body.decode('utf-8')
        msg = json.loads(msgJson)

        # Store message
        self.messages[room].append(msg)

        # Publish message to event queue
        publish(request.path, data=msg)

        # Return all messages sent to the room
        return JsonResponse({})

    def rt_get_permission(self, action, request):
        return True
