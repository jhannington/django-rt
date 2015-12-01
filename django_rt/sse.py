class SseEvent:
    def __init__(self, event=None, id=None, data=None, retry=None):
        self.event = event
        self.id = id
        self.data = data
        self.retry = retry

    def __str__(self):
        assert self.data

        lines = []
        if self.event:
            lines.append('event: ' + str(self.event).strip())
        if self.id:
            lines.append('id: ' + str(self.id).strip())
        lines.append('data: ' + str(self.data).strip())
        if self.retry:
            lines.append('retry: ' + str(int(self.retry)))

        return '\n'.join(lines) + '\n\n'

    def as_utf8(self):
        return str(self).encode('utf-8')

    @staticmethod
    def from_resource_event(event):
        return SseEvent(
            event=event.event_type,
            data=event.to_json()
        )

class SseHeartbeat:
    def __str__(self):
        return ': ping\n'

    def as_utf8(self):
        return str(self).encode('utf-8')
