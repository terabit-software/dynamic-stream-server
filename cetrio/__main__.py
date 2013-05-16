import time
try:
    # Python 3
    import socketserver
    from http import server
    import urllib.parse as urlparse
    from urllib.request import urlopen
except ImportError:
    import SocketServer as socketserver
    import BaseHTTPServer as server
    import urlparse
    from urllib2 import urlopen

import base
from config import config


tcp_retry = 10 #seconds


class Handler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        info = urlparse.urlparse(self.path)
        id, action = info.path.strip('/').split('/')
        if action == 'start':
            base.Video.start(id)
        else:
            base.Video.stop(id)

    do_POST = do_GET


def shutdown():
    print('Stopping cameras...')
    for cam in base.Video.data.values():
        cam.stop(now=True)
    print('Done!')
    print('Stopping thumbnail download...')
    base.Thumbnail.stop_download()
    print('Done!')


def main():
    base.Video.initialize_from_stats()
    base.Thumbnail.start_download()

    host = config.get('local', 'addr')
    port = int(config.get('local', 'port'))

    socketserver.TCPServer.allow_reuse_address = True
    ss = None
    while True:
        try:
            ss = socketserver.TCPServer((host, port), Handler)
        except IOError:
            print('Waiting TCP port to be used.')
            time.sleep(tcp_retry)
        else:
            print('Connected to %s:%s' % (host, port))
            break

    try:
        ss.serve_forever()
    except KeyboardInterrupt:
        ss.server_close()
        print('Server Closed')
        raise


try:
    main()
except KeyboardInterrupt:
    shutdown()