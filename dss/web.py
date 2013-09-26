import time
import tornado.ioloop
import tornado.web

from . import video
from .config import config
from .tools import show


class VideoStreamHandler(tornado.web.RequestHandler):
    timeout = config.getint('local', 'http_client_timeout')
    max_timeout = config.getint('local', 'http_client_timeout_max')

    def handle_information(self):
        try:
            data = self.path_args[0].strip('/').split('/')
            id, action = data[:2]
        except Exception:
            return 404

        if action == 'start':
            try:
                video.Video.start(id)
            except KeyError:
                return 404
        elif action == 'http':
            try:
                timeout = int(data[2])
            except (IndexError, ValueError):
                timeout = self.timeout
            timeout = min(timeout, self.max_timeout)

            try:
                video.Video.start(id, http_wait=timeout)
            except KeyError:
                return 404
        else:
            video.Video.stop(id)
        return 200

    def get(self, *args, **kw):
        try:
            code = self.handle_information()
        except Exception as e:
            show('Error on request handling: %r' % e)
            self.set_status(500)
        else:
            self.set_status(code)
        finally:
            self.finish()

    post = get


class Server(object):
    host = config.get('local', 'addr')
    port = config.getint('local', 'port')

    application = tornado.web.Application([
        (r"/stream/(.*)", VideoStreamHandler),
    ])

    tcp_retry = 10  # seconds
    daemon_threads = True

    def __init__(self):
        self._instance = tornado.ioloop.IOLoop.instance()

    def start(self):
        while True:
            try:
                self.application.listen(self.port, self.host)
            except IOError:
                print('Waiting TCP port to be used.')
                time.sleep(self.tcp_retry)
            else:
                print('Connected to %s:%s' % (self.host, self.port))
                break

        self._instance.start()

    def stop(self):
        try:
            self._instance.stop()
        except Exception:
            pass
