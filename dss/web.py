import time
import tornado.ioloop
import tornado.web
import os
import glob
from os.path import join, basename, splitext

from .config import config, dirname
from .tools import show
from .loader import load_object
from .web_handlers import stream_control, stream_stats, info, mobile_stream


STATIC_PATH = os.path.join(os.path.dirname(dirname), 'www', '')


def build_application():
    controllers = [
        (r'/control/(.*?)/(' + stream_control.options + r')/?(\d*)',
         stream_control.StreamControlHandler),
        (r'/stats/([^/]*)/?(.*)', stream_stats.StreamStatsHandler),
        (r'/info/(' + info.options + r')/?(.*)', info.InfoHandler),
        (r'/mobile/location', mobile_stream.MobileStreamLocation),
    ]
    package = 'web_handlers_ext'

    for name in glob.glob(join(dirname, package, '*.py')):
        handler = load_object(splitext(basename(name))[0] + '.HANDLER',
                              'dss.' + package)
        if handler is not None:
            controllers.append(handler)

    controllers.append(
        (r'/(.*)', tornado.web.StaticFileHandler, {'path': STATIC_PATH})
    )
    return tornado.web.Application(controllers)


class Server(object):
    host = config.get('local', 'addr')
    port = config.getint('local', 'port')
    tcp_retry = 10  # seconds
    daemon_threads = True
    application = build_application()

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

    def stop(self):
        pass
