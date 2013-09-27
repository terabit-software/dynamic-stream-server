import time
import tornado.ioloop
import tornado.web

from .config import config
from .web_handlers import stream_control


class Server(object):
    host = config.get('local', 'addr')
    port = config.getint('local', 'port')

    application = tornado.web.Application([
        (r"/stream/(.*?)/(start|stop|http)/?(\d*)", stream_control.StreamControl),
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
