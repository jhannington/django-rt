from django.conf import settings as dj_settings

DEFAULTS = {
    'RT_CORS_ALLOW_ORIGIN': None,
    'RT_CORS_ALLOW_CREDENTIALS': None,
    'RT_PREFIX': 'rt',
    'RT_SSE_HEARTBEAT': 30, # in seconds
    'RT_REDIS_HOST': 'localhost',
    'RT_REDIS_PORT': 6379,
    'RT_REDIS_DB': 0,
    'RT_REDIS_PASSWORD': None,
    'RT_SSE_RETRY': 2*1000, # in milliseconds
    'RT_COURIER_IPS': ['127.0.0.1'],
}

class RtSettings:
    def __getattr__(self, name):
        if name in DEFAULTS:
            return getattr(dj_settings, name, DEFAULTS[name])
        else:
            return getattr(dj_settings, name)
 
settings = RtSettings()
