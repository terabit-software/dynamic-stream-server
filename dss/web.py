import time
import tornado.ioloop
import tornado.web

from .config import config
from .tools import show
from .web_handlers import stream_control, stream_stats, info


class Server(object):
    host = config.get('local', 'addr')
    port = config.getint('local', 'port')

    application = tornado.web.Application([
        (r'/control/(.*?)/(start|stop|http)/?(\d*)', stream_control.StreamControlHandler),
        (r'/stats/([^/]*)/?(.*)', stream_stats.StreamStatsHandler),
        (r'/info/(provider|stream)/?(.*)', info.InfoHandler),
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
                show('Waiting TCP port to be used.')
                time.sleep(self.tcp_retry)
            else:
                show('Connected to %s:%s' % (self.host, self.port))
                break

        self._instance.start()

    def stop(self):
        try:
            self._instance.stop()
        except Exception:
            pass
