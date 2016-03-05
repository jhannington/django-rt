import redis
from django.views.generic import View
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.utils.crypto import get_random_string

from django_rt.utils import get_subscription_key
from django_rt.resource import Resource, ResourceRequest
from django_rt.settings import settings

class RtResourceView(View):
    _rt_is_resource = True

    def rt_get_permission(self, action, request):
        raise NotImplementedError('Classes deriving from RtResourceView must implement rt_get_permission()')

    def rt_get_resource(self, request):
        """Return a Resource object describing this resource.
        Safe to block."""
        return Resource(
            path=self.rt_get_path(request),
            channel=self.rt_get_channel(request)
        )

    def rt_request(self, request):
        """Handle a Django-RT internal API request."""

        # Check client IP is allowed
        if not settings.DEBUG and settings.RT_COURIER_IPS: 
            if request.META['REMOTE_ADDR'] not in settings.RT_COURIER_IPS:
                return HttpResponseForbidden()

        # Deserialize ResourceRequest from body and verify signature
        #! TODO since the request is still considered unauthorized at this point, add exception handling here for bad data:
        #! * utf-8 errors
        #! * json errors
        #! * data errors
        #! * bad signature
        body = request.body.decode('utf-8')
        res_req = ResourceRequest.from_json(body)
        res_req.path = self.rt_get_path(request)
        res_req.verify_signature()

        # Open Redis connection
        redis_conn = redis.StrictRedis(
            host=settings.RT_REDIS_HOST,
            port=settings.RT_REDIS_PORT,
            db=settings.RT_REDIS_DB,
            password=settings.RT_REDIS_PASSWORD
        )

        # Get subscription status
        sub_key = get_subscription_key(res_req.sub_id)
        sub_status = redis_conn.get(sub_key).decode('utf-8')
        if not sub_status:
            return HttpResponseBadRequest('Invalid subscription ID')

        if res_req.action == 'subscribe':
            # Handle subscription request

            # Check subscription has 'requested' status
            if sub_status != 'requested':
                return HttpResponseBadRequest('Invalid subscription ID')

            # Check subscription is allowed
            if self.rt_get_permission('subscribe', request) is not True:
                return HttpResponseForbidden()

            # Set subscription status to 'granted'
            result = redis_conn.set(sub_key, 'granted')
            assert result

            # Return Resource object
            res = self.rt_get_resource(request)
            return JsonResponse(res.serialize(),
                content_type=Resource.CONTENT_TYPE+'; charset=utf-8'
            )
        else:
            # Shouldn't ever land here
            assert False

    def rt_dispatch(self, request):
        # Catch resource requests
        if request.method.lower() == 'post':
            accept = request.META.get('HTTP_ACCEPT', None)
            if accept == Resource.CONTENT_TYPE and \
                request.META['CONTENT_TYPE'] == ResourceRequest.CONTENT_TYPE \
            :
                return self.rt_request(request)

        return None
        
    def dispatch(self, request, *args, **kwargs):
        return self.rt_dispatch(request) or \
            super().dispatch(request, *args, **kwargs)

    def rt_get_path(self, request):
        """Return the path to this resource.
        Safe to block."""
        return request.path

    def rt_get_channel(self, request):
        """Return this resource's pubsub channel name.
        Safe to block."""
        return self.rt_get_path(request)
