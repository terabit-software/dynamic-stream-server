import time
try:
    # Python 3
    from http import server
    import socketserver
    import urllib.parse as urlparse
    from urllib.request import urlopen
except ImportError:
    import BaseHTTPServer as server
    import SocketServer as socketserver
    import urlparse
    from urllib2 import urlopen

from . import video
from .config import config


class Handler(server.BaseHTTPRequestHandler):
    timeout = config.getint('local', 'http_client_timeout')
    max_timeout = config.getint('local', 'http_client_timeout_max')

    def handle_information(self):
        info = urlparse.urlparse(self.path)
        try:
            data = info.path.strip('/').split('/')
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

    def do_GET(self):
        try:
            code = self.handle_information()
        except Exception as e:
            print('Error on request handling: %r' % e)
            self.send_response(500)
        else:
            self.send_response(code)
        finally:
            self.end_headers()

    do_POST = do_GET


class Server(socketserver.ThreadingMixIn, server.HTTPServer):
    host = config.get('local', 'addr')
    port = config.getint('local', 'port')

    tcp_retry = 10  # seconds
    daemon_threads = True

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
