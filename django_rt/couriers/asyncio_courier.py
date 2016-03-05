import asyncio
import asyncio_redis
import aiohttp
from aiohttp import web
import django
from urllib.parse import urlunparse

import logging
logger = logging.getLogger(__name__)

from django_rt.event import ResourceEvent
from django_rt.utils import get_cors_headers, get_full_channel_name, verify_resource_view, generate_subscription_id, get_subscription_key, get_django_url
from django_rt.resource import NotAnRtResourceError, Resource, ResourceError, ResourceRequest
from django_rt.settings import settings
from django_rt.sse import SseEvent, SseHeartbeat

class AsyncioCourier:
    _django_url = None

    def __init__(self):
        self._ev_loop = None

    @asyncio.coroutine
    def request_resource(self, path, request, sub_id):
        # Prepare resource request
        res_req = ResourceRequest(path, 'subscribe',
            sub_id=sub_id
        )
        res_req.prepare(client_headers=request.headers)

        # Build resource URL
        if self._django_url.scheme == 'http+unix':
            conn = aiohttp.UnixConnector(path=self._django_url.path)
            # aiohttp expects a hostname in the URL, even when requesting over a domain socket; correct host should be present in header
            url = urlunparse(('http', 'unknown', res_req.path, '', '', ''))
        else:
            conn = None
            url = urlunparse((self._django_url.scheme, self._django_url.netloc, res_req.path, '', '', ''))

        # Make request
        logger.debug('Requesting subscription from %s%s' % (url,
            ' over Unix socket %s' % (self._django_url.path,) if conn else '')
        )
        resp = yield from aiohttp.post(url,
            data=res_req.to_json().encode('utf-8'),
            headers=res_req.get_headers(),
            connector=conn
        )
        try:
            if resp.status == 200:
                # Check returned data has the requested content type
                Resource.validate_content_type(resp.headers.get('Content-Type', None))

                # Return Resource object
                res_json = yield from resp.text()
                return Resource.from_json(res_json)
            else:
                raise ResourceError(resp.status)
        finally:
            # Ensure response is closed
            yield from resp.release()

    @asyncio.coroutine
    def cleanup_request(self, sub_id, redis_conn, redis_subscription):
        logger.debug('Connection closed; cleaning up')

        # Close existing Redis connection
        if redis_conn:
            redis_conn.close()

        # Ensure subscription key is removed
        if sub_id:
            # Open new connection (this is necessary as asyncio_redis won't allow the DEL command to run after a subscription)
            redis_conn = yield from asyncio_redis.Connection.create(
                host=settings.RT_REDIS_HOST,
                port=settings.RT_REDIS_PORT,
                db=settings.RT_REDIS_DB,
                password=settings.RT_REDIS_PASSWORD
            )

            # Remove key
            res = yield from redis_conn.delete([get_subscription_key(sub_id)])
            if res:
                logger.debug('Removed subscription %s' % (sub_id,))

            # Close connection
            redis_conn.close()

    @asyncio.coroutine
    def handle_sse(self, request):
        res_path = request.match_info.get('resource')
        res_path = '/' + res_path

        # Append slash to resource path if URL ends with slash
        suffix = request.match_info.get('suffix')
        if suffix.endswith('/'):
            res_path += '/'

        redis_conn = None
        redis_subscription = None
        sub_id = None
        try:
            # Check route is a Django-RT resource
            try:
                logger.debug('Verifying %s is an RT resource' % (res_path,))
                verify_resource_view(res_path)
            except NotAnRtResourceError:
                logger.debug('Not an RT resource; aborting')
                return web.Response(status=406)
            except ResourceError as e:
                logger.debug('Caught ResourceError; aborting')
                return web.Response(status=e.status)

            # Connect to Redis server
            redis_conn = yield from asyncio_redis.Connection.create(
                host=settings.RT_REDIS_HOST,
                port=settings.RT_REDIS_PORT,
                db=settings.RT_REDIS_DB,
                password=settings.RT_REDIS_PASSWORD
            )

            # Create subscription
            while True:
                sub_id = generate_subscription_id()
                result = yield from redis_conn.setnx(get_subscription_key(sub_id), 'requested')
                if result:
                    break
            logger.debug('Created subscription ID: %s' % (sub_id,))

            # Request resource from Django API
            try:
                logger.debug('Requesting subscription for %s' % (res_path,))
                res = yield from self.request_resource(res_path, request, sub_id)
            except NotAnRtResourceError:
                logger.debug("Subscription denied: not an rt resource. This shouldn't happen...")
                return web.Response(status=406)
            except ResourceError as e:
                logger.debug('Subscription denied: HTTP error %d' % (e.status,))
                return web.Response(status=e.status)

            # Check subscription status and change to 'subscribed'
            sub_key = get_subscription_key(sub_id)
            sub_status = yield from redis_conn.get(sub_key)
            assert sub_status == 'granted'
            logger.debug('Subscription granted')
            result = yield from redis_conn.set(sub_key, 'subscribed')
            if result:
                logger.debug('Subscription %s status changed to "subscribed"' % (sub_id,))

            # Delete subscription key (not currently used for anything else)
            yield from redis_conn.delete([sub_key])

            # Subscribe to Redis channel
            chan = get_full_channel_name(res.channel)
            logger.debug('Subscribing to Redis channel %s' % (chan,))
            redis_subscription = yield from redis_conn.start_subscribe()
            yield from redis_subscription.subscribe([ chan ])

            # Prepare response
            response = web.StreamResponse()
            response.content_type = 'text/event-stream'
            cors_hdrs = get_cors_headers(request.headers.get('Origin', None))
            response.headers.update(cors_hdrs)
            yield from response.prepare(request)

            # Loop
            first_event = True
            while True:
                # Wait for event on channel
                try:
                    reply = yield from asyncio.wait_for(
                        redis_subscription.next_published(),
                        settings.RT_SSE_HEARTBEAT
                    )
                except asyncio.TimeoutError:
                    # Timeout, send SSE heartbeat
                    response.write(SseHeartbeat().as_utf8()) 
                    yield from response.drain()
                else:
                    # Deserialize ResourceEvent
                    event = ResourceEvent.from_json(reply.value)

                    # Create SSE event
                    sse_evt = SseEvent.from_resource_event(event)

                    # Send 'retry' field on first SSE event delivered
                    if first_event:
                        sse_evt.retry = settings.RT_SSE_RETRY
                        first_event = False

                    # Send SSE event to client
                    response.write(sse_evt.as_utf8())
                    yield from response.drain()

            yield from response.write_eof()
            return response
        finally:
            # Cleanup
            asyncio.async(self.cleanup_request(sub_id, redis_conn, redis_subscription))

    def create_app(self, loop):
        app = web.Application(loop=loop)
        app.router.add_route('GET', r'/{resource:.+}{suffix:\.sse/?}', self.handle_sse)
        return app

    def run(self, addr=None, port=None, unix_socket=None, django_url=None):
        assert (addr and port) or unix_socket

        self._django_url = get_django_url(django_url)

        # Initialize Django
        django.setup()

        # Suppress the spammy asyncio logging
        logging.getLogger('asyncio').setLevel(logging.WARNING)

        # Run server
        loop = asyncio.get_event_loop()
        app = self.create_app(loop)
        handler = app.make_handler()
        if unix_socket:
            f = loop.create_unix_server(handler, unix_socket)
            listen_str = unix_socket
        else:
            f = loop.create_server(handler, addr, port)
            listen_str = ':'.join([str(addr), str(port)])
        logger.info('Django-RT asyncio courier server running on '+listen_str)
        srv = loop.run_until_complete(f)

        self._ev_loop = loop
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            # Shutdown
            self._ev_loop = None
            logger.info('Closing connections...')
            loop.run_until_complete(handler.finish_connections(1.0))
            srv.close()
            loop.run_until_complete(srv.wait_closed())
            loop.run_until_complete(app.finish())
            loop.close()

    def stop(self):
        # Stop event loop from running
        if self._ev_loop:
            self._ev_loop.stop()

if __name__ == '__main__':
    AsyncioCourier().run('0.0.0.0', 8080, django_url='http://localhost:10000')
