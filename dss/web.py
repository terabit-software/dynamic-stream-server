import time
import tornado.ioloop
import tornado.web
import os

from .config import config, dirname
from .tools import show
from .web_handlers import stream_control, stream_stats, info, mobile_stream

STATIC_PATH = os.path.join(os.path.dirname(dirname), 'www', '')


class Server(object):
    host = config.get('local', 'addr')
    port = config.getint('local', 'port')

    application = tornado.web.Application([
        (r'/control/(.*?)/(' + stream_control.options + r')/?(\d*)',
         stream_control.StreamControlHandler),
        (r'/stats/([^/]*)/?(.*)', stream_stats.StreamStatsHandler),
        (r'/info/(' + info.options + r')/?(.*)', info.InfoHandler),
        (r'/mobile/location', mobile_stream.MobileStreamLocation),
        (r'/(.*)', tornado.web.StaticFileHandler, {'path': STATIC_PATH})
    ])

    tcp_retry = 10  # seconds
    daemon_threads = True

    def start(self):
        while True:
            try:
                self.application.listen(self.port, self.host)
            except IOError:
                show('Waiting TCP port to be used.')
                time.sleep(self.tcp_retry)
            else:
                show('Listening at {0.host}:{0.port} (http)'.format(self))
                break
        return self