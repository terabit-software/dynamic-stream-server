import tornado.web

from .. import video
from ..tools import show

from ..config import config


options = '|'.join([
    'start', 'stop', 'http', 'publish_start', 'publish_stop',
])


class StreamControlHandler(tornado.web.RequestHandler):
    timeout = config.getint('local', 'http_client_timeout')
    max_timeout = config.getint('local', 'http_client_timeout_max')
    min_timeout = config.getint('local', 'http_client_timeout_min')

    def handle_start(self, id):
        try:
            video.Video.start(id)
        except KeyError:
            return 404

    def handle_http(self, id):
        try:
            timeout = int(self.path_args[2])
        except (IndexError, ValueError):
            timeout = self.timeout

        timeout = max(timeout, self.min_timeout)
        timeout = min(timeout, self.max_timeout)

        try:
            video.Video.start(id, http_wait=timeout)
        except KeyError:
            return 404

    def handle_stop(self, id):
        video.Video.stop(id)

    def handle_publish_start(self, id):
        try:
            stream = video.Video.get_stream(id)
        except KeyError:
            return 404
        if not stream.alive:
            return 403  # Should not be running

        #show('Nginx reported {START}:', stream)
        # Measure the amount of time since process start
        # to RTMP stream publication.
        stream.stats.timed.warmup()

    def handle_publish_stop(self, id):
        try:
            stream = video.Video.get_stream(id)
        except KeyError:
            return 404

        # Acount for camera uptime
        stream.stats.timed.uptime()

        #show('Nginx reported {STOP}:', stream)

    def get(self, id, action, *args, **kw):

        try:
            handle = getattr(self, 'handle_' + action)
            code = handle(id)
        except Exception as e:
            show('Error on request handling: %r' % e)
            self.set_status(500)
        else:
            self.set_status(code or 200)
        finally:
            self.finish()

    post = get
