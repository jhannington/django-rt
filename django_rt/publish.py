import json
import redis
from django.views.generic import View

from django_rt.event import ResourceEvent
from django_rt.settings import settings
from django_rt.utils import get_full_channel_name, verify_resource_view

def publish(resource, event=None, data=None, time=None, event_type=None):
    # Use request path as resource if a View instance is given
    if isinstance(resource, View):
        resource = resource.request.path

    # Check route resolves to an RT resource View
    verify_resource_view(resource)

    if data or time or event_type:
        if event:
            raise RuntimeError("publish() cannot accept 'data', 'time', or 'event_type' arguments if 'event' is specified")
        # Create ResourceEvent
        event = ResourceEvent(
            data=data,
            time=time,
            event_type=event_type
        )
    else:
        if not event:
            raise RuntimeError("publish() called with no event or event data")
        
    channel = get_full_channel_name(resource)
    event_json = event.to_json()

    r = redis.StrictRedis(
        host=settings.RT_REDIS_HOST,
        port=settings.RT_REDIS_PORT,
        db=settings.RT_REDIS_DB
    )
    r.publish(channel, event_json)
