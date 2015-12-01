from django.core.signing import Signer

from django_rt.utils import SerializableObject

class NotAnRtResourceError(Exception):
    """Requested resource is not a Django-RT resource.
    Should cause a HTTP 406 response on the client request"""
    def __str__(self):
        return 'Not a Django-RT resource'

class ResourceError(Exception):
    """A non-200 status code was encountered whilst getting the resource."""
    def __init__(self, status):
        self.status = status

    def __str__(self):
        return 'Resource error'

class Resource(SerializableObject):
    CONTENT_TYPE = 'x-djangort-resource'

    def __init__(self, path, channel):
        self.path = path
        self.channel = channel

    def serialize(self):
        return {
            'path': self.path,
            'channel': self.channel
        }

    @classmethod
    def deserialize(cls, data):
        return cls(
            path=data['path'],
            channel=data['channel']
        )

    @staticmethod
    def validate_content_type(ct):
        """Throw error if HTTP CONTENT_TYPE header is not acceptable for a serialized Resource"""
        if not ct:
            raise NotAnRtResourceError()

        tok = ct.split(';', 1)
        content_type = tok[0].strip()
        charset = tok[1].strip() if len(tok) > 1 else None

        if content_type != Resource.CONTENT_TYPE:
            raise NotAnRtResourceError()

        if charset and charset.lower() != 'charset=utf-8':
            raise NotAnRtResourceError()

class ResourceRequest(SerializableObject):
    ACTIONS = ('subscribe',)
    CONTENT_TYPE = 'x-djangort-resource-request; charset=utf-8'

    def __init__(self, path=None, action=None, sub_id=None, signature=None):
        assert action in self.ACTIONS

        self.path = path
        self.action = action
        self.sub_id = sub_id
        self._signature = signature

        self._prepared = False

    def prepare(self, client_headers=None):
        """Prepare the ResourceRequest for dispatch over HTTP."""
        PASS_HEADERS = (
            'HOST',
            'COOKIE',
            'REFERER',
        )
        
        self._headers = {}

        # Pass through client headers
        if client_headers:
            for hdr in PASS_HEADERS:
                if hdr in client_headers:
                    self._headers[hdr] = client_headers[hdr]

        # Only accept serialized Resource content type
        self._headers['ACCEPT'] = Resource.CONTENT_TYPE

        self._headers['CONTENT-TYPE'] = self.CONTENT_TYPE
        self._prepared = True

    def get_headers(self):
        assert self._prepared
        return self._headers

    def _serialize_for_signing(self):
        """Serialize the ResourceRequest as a string for signing."""
        return '|'.join([
            str(self.path),
            str(self.action),
            str(self.sub_id)
        ])

    def get_signature(self):
        return Signer().signature(self._serialize_for_signing())

    def verify_signature(self):
        assert self._signature
        s = ':'.join([self._serialize_for_signing(), self._signature])
        Signer().unsign(s)

    def serialize(self):
        return {
            'action': self.action,
            'subscription_id': self.sub_id,
            'signature': self.get_signature()
        }

    @classmethod
    def deserialize(cls, data):
        return cls(
            action=data['action'],
            sub_id=data['subscription_id'],
            signature=data['signature']
        )
