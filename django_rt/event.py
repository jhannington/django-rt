from django.utils import timezone

from django_rt.utils import SerializableObject

class ResourceEvent(SerializableObject):
    def __init__(self, data=None, time=None, event_type=None):
        assert data or event_type

        self.data = data
        self.event_type = event_type

        if time:
            self.time = time
        else:
            # Default to current time
            self.time = timezone.now()

    def serialize(self):
        obj = {
            'time': self.time
        }

        if self.data:
            obj['data'] = self.data
        if self.event_type:
            obj['type'] = self.event_type

        return obj

    @classmethod
    def deserialize(cls, data):
        return cls(
            data=data.get('data', None),
            time=data.get('time', None),
            event_type=data.get('type', None),
        )
