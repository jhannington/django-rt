import json
import redis
from django.views.generic import View

from django_rt.event import ResourceEvent
from django_rt.settings import settings
from django_rt.utils import get_full_channel_name

def publish(channel, event=None, data=None, time=None, event_type=None):
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
        
    redis_channel = get_full_channel_name(channel)
    event_json = event.to_json()

    r = redis.StrictRedis(
        host=settings.RT_REDIS_HOST,
        port=settings.RT_REDIS_PORT,
        db=settings.RT_REDIS_DB,
        password=settings.RT_REDIS_PASSWORD
    )
    r.publish(redis_channel, event_json)
