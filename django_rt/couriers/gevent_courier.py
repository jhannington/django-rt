# Monkey-patch all synchronous functions
from gevent import monkey
monkey.patch_all()

import re
import urllib3
from gevent.pywsgi import WSGIServer
import redis
import django
from urllib.parse import urlunparse

import logging
logger = logging.getLogger(__name__)

from django_rt.event import ResourceEvent
from django_rt.utils import get_full_channel_name, get_http_status_reason, verify_resource_view, generate_subscription_id, get_subscription_key, get_django_url, get_cors_headers
from django_rt.resource import NotAnRtResourceError, Resource, ResourceError, ResourceRequest
from django_rt.settings import settings
from django_rt.sse import SseEvent, SseHeartbeat

class GeventCourier:
    def __init__(self):
        self._wsgi_server = None

    @staticmethod
    def full_status(code):
        reason = get_http_status_reason(code)
        if reason != '':
            return ' '.join((str(code), reason))
        else:
            return str(code)

    @staticmethod
    def get_headers(env):
        """Get HTTP headers from environment"""
        hdrs = {}
        for k in [k for k in env if k.startswith('HTTP_')]:
            hdrs[k[5:]] = env[k]
        return hdrs

    def request_resource(self, path, sub_id, req_hdrs):
        # Prepare resource request
        res_req = ResourceRequest(path, 'subscribe',
            sub_id=sub_id
        )
        url = urlunparse((self._django_url.scheme, self._django_url.netloc, res_req.path, '', '', ''))
        res_req.prepare(client_headers=req_hdrs)
        http = urllib3.PoolManager()
        resp = http.urlopen('POST', url,
            body=res_req.to_json(),
            headers=res_req.get_headers()
        )

        if resp.status == 200:
            # Check returned data has the requested content type
            Resource.validate_content_type(resp.headers.get('Content-Type', None))

            # Return Resource object
            res_json = resp.data.decode('utf-8')
            return Resource.from_json(res_json)
        else:
            raise ResourceError(resp.status)

    def handle_sse(self, path, suffix, env, start_response):
        res_path = path

        # Append slash to resource path if URL ends with slash
        if suffix.endswith('/'):
            res_path += '/'

        req_hdrs = self.get_headers(env)

        # Check route is a Django-RT resource
        try:
            logger.debug('Verifying %s is an RT resource' % (res_path,))
            verify_resource_view(res_path)
        except NotAnRtResourceError:
            logger.debug('Not an RT resource; aborting')
            start_response(self.full_status(406), [])
            return [b'']
        except ResourceError as e:
            logger.debug('Caught ResourceError; aborting')
            start_response(self.full_status(e.status), [])
            return [b'']

        # Connect to Redis server
        redis_conn = redis.StrictRedis(
            host=settings.RT_REDIS_HOST,
            port=settings.RT_REDIS_PORT,
            db=settings.RT_REDIS_DB,
            password=settings.RT_REDIS_PASSWORD
        )

        # Create subscription
        while True:
            sub_id = generate_subscription_id()
            result = redis_conn.setnx(get_subscription_key(sub_id), 'requested')
            if result:
                break
        logger.debug('Created subscription ID: %s' % (sub_id,))

        # Request resource from Django API
        try:
            logger.debug('Requesting subscription for %s' % (res_path,))
            res = self.request_resource(path, sub_id, req_hdrs)
        except NotAnRtResourceError:
            logger.debug("Subscription denied: not an rt resource. This shouldn't happen...")
            start_response(self.full_status(406), [])
            return [b'']
        except ResourceError as e:
            logger.debug('Subscription denied: HTTP error %d' % (e.status,))
            start_response(self.full_status(e.status), [])
            return [b'']

        # Check subscription status and change to 'subscribed'
        sub_key = get_subscription_key(sub_id)
        sub_status = redis_conn.get(sub_key).decode('utf-8')
        assert sub_status == 'granted'
        logger.debug('Subscription granted')
        if redis_conn.set(sub_key, 'subscribed'):
            logger.debug('Subscription %s status changed to "subscribed"' % (sub_id,))

        # Delete subscription key (not currently used for anything else)
        redis_conn.delete(sub_key)

        # Subscribe to Redis channel
        pubsub = redis_conn.pubsub()
        pubsub.subscribe(get_full_channel_name(res.channel))

        # Prepare response
        hdrs = {
            'Content-Type': 'text/event-stream'
        }
        cors_hdrs = get_cors_headers(req_hdrs.get('ORIGIN', None))
        hdrs.update(cors_hdrs)
        start_response('200 OK', [hdr for hdr in hdrs.items()])

        # Loop
        first_event = True
        while True:
            # Wait for event on channel
            msg = pubsub.get_message(
                timeout=settings.RT_SSE_HEARTBEAT if settings.RT_SSE_HEARTBEAT else (10*60.0)
            )
            if msg:
                if msg['type'] == 'message':
                    # Deserialize ResourceEvent
                    event_json = msg['data'].decode('utf-8')
                    event = ResourceEvent.from_json(event_json)

                    # Create SSE event
                    sse_evt = SseEvent.from_resource_event(event)

                    # Send 'retry' field on first SSE event delivered
                    if first_event:
                        sse_evt.retry = settings.RT_SSE_RETRY
                        first_event = False

                    # Send SSE event to client
                    yield sse_evt.as_utf8()
            else:
                # Timeout, send SSE heartbeat if necessary
                if settings.RT_SSE_HEARTBEAT:
                    yield SseHeartbeat().as_utf8()

    def application(self, env, start_response):
        m = re.match(r'^(.+)\.(.+)$', env['PATH_INFO'])
        if not m:
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b'Not found']

        path = m.group(1)
        suffix = m.group(2)

        if suffix == 'sse' or suffix == 'sse/':
            return self.handle_sse(path, suffix, env, start_response)
        else:
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b'Not found']

    def run(self, addr=None, port=None, unix_socket=None, django_url=None):
        assert (addr and port) or unix_socket

        self._django_url = get_django_url(django_url)
        if self._django_url.scheme == 'http+unix':
            raise ValueError('http+unix scheme not currently supported with the gevent courier')

        # Initialize Django
        django.setup()

        logger.info('Django-RT gevent courier server running on '+':'.join([str(addr), str(port)]))

        self._wsgi_server = server = WSGIServer((addr, port), self.application)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

    def stop(self):
        # Stop WSGI server
        self._wsgi_server.stop()

if __name__ == '__main__':
    GeventCourier().run('0.0.0.0', 15000)
