import json
import uuid
from datetime import datetime
from importlib import import_module
from urllib.parse import urlparse

from django.core.urlresolvers import resolve, Resolver404
from http.client import responses as REASON_PHRASES

from django_rt.settings import settings

class JsonDateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return json.JSONEncoder.default(self, obj)

class SerializableObject:
    def serialize(self):
        raise NotImplementedError('serialize() not implemented')

    @classmethod
    def deserialize(cls, data):
        raise NotImplementedError('deserialize() not implemented')

    def to_json(self):
        return json.dumps(self.serialize(), cls=JsonDateTimeEncoder)

    @classmethod
    def from_json(cls, json_data):
        return cls.deserialize(json.loads(json_data))

def get_cors_headers(origin):
    """Return dict containing the appropriate CORS headers for a courier response, given the request origin."""

    def get_allow_origin_header(origin):
        """Return the value for the Access-Control-Allow-Origin header, given the request origin."""

        RT_CORS_ALLOW_ORIGIN = settings.RT_CORS_ALLOW_ORIGIN
        if not RT_CORS_ALLOW_ORIGIN:
            # Allow any host when DEBUG is enabled
            return '*' if settings.DEBUG else None
        elif RT_CORS_ALLOW_ORIGIN == '*':
            return '*'
        else:
            if type(RT_CORS_ALLOW_ORIGIN) is str:
                allowed = (RT_CORS_ALLOW_ORIGIN,)
            else:
                allowed = RT_CORS_ALLOW_ORIGIN

            if origin and origin in allowed:
                return origin

        return None

    # Build headers
    hdrs = {}
    allow_origin = get_allow_origin_header(origin)
    if allow_origin:
        hdrs['Access-Control-Allow-Origin'] = allow_origin 

        if settings.RT_CORS_ALLOW_CREDENTIALS is not None:
            hdrs['Access-Control-Allow-Credentials'] = \
                'true' if settings.RT_CORS_ALLOW_CREDENTIALS else 'false'

    return hdrs

def get_full_channel_name(channel):
    return ':'.join((settings.RT_PREFIX, 'channel', channel))

def get_http_status_reason(status):
    if status in REASON_PHRASES:
        return REASON_PHRASES[status]
    else:
        return ''

def verify_resource_view(route):
    """Resolve the specified route with Django and verify that the view class is actually a Django-RT resource.
    Will throw either a ResourceError or NotAnRtResource exception on failure."""
    from django_rt.resource import ResourceError, NotAnRtResourceError

    # Resolve
    try:
        r = resolve(route)
    except Resolver404:
        # Route not found
        raise ResourceError(404)
        
    # Import class from its module
    module = import_module(r.func.__module__)
    view_class = getattr(module, r.func.__name__)

    # Check '_rt_is_resource' class property is True
    try:
        if not getattr(view_class, '_rt_is_resource'):
            raise NotAnRtResourceError()
    except AttributeError:
        raise NotAnRtResourceError()

def generate_subscription_id():
    return uuid.uuid4().hex

def get_subscription_key(id):
    return ':'.join((settings.RT_PREFIX, 'subscription', id))

def get_django_url(url):
    """Attempt to parse the Django server URL. If url is None, use the URL from the RT_DJANGO_URL setting instead.
    Returns parsed URL.
    """

    # Use setting if url is not given
    if not url:
        url = settings.RT_DJANGO_URL

    # URL should not have a path component, but allow a single trailing slash anyway
    if url.endswith('/'):
        url = url[:-1]

    # Parse
    p = urlparse(url)

    # URL should not have anything after the path
    if p.params or p.query or p.fragment:
        raise ValueError('Invalid Django server URL')

    if p.scheme == 'http':
        # HTTP URL should not have a path
        if p.path:
            raise ValueError('Invalid Django server URL')
    elif p.scheme == 'http+unix':
        # HTTP URL should not have a netloc fragment
        if p.netloc: 
            raise ValueError('Invalid Django server URL')
    else:
        # Unsupported scheme
        raise ValueError('Unsupported Django server URL scheme "%s"' % (p.scheme,))

    return p
