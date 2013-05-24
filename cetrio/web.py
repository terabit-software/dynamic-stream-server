import time
import threading
try:
    # Python 3
    from http import server
    import urllib.parse as urlparse
    from urllib.request import urlopen
except ImportError:
    import BaseHTTPServer as server
    import urlparse
    from urllib2 import urlopen

import base
from config import config


class Handler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        info = urlparse.urlparse(self.path)
        print(info)
        data = info.path.strip('/').split('/')
        id, action = data[:2]

        if action == 'start':
            base.Video.start(id)
        else:
            base.Video.stop(id)

    do_POST = do_GET


class Server(server.HTTPServer):
    host = config.get('local', 'addr')
    port = config.getint('local', 'port')

    tcp_retry = 10 #seconds

    def __init__(self):
        pass

    def start(self):
        while True:
            try:
                server.HTTPServer.__init__(self, (self.host, self.port), Handler)
            except IOError:
                print('Waiting TCP port to be used.')
                time.sleep(self.tcp_retry)
            else:
                print('Connected to %s:%s' % (self.host, self.port))
                break

        self.serve_forever()

    def stop(self):
        try:
            self.server_close()
        except Exception:
            pass

