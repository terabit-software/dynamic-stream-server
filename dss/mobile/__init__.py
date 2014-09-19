""" TCP Server for mobile streaming
"""

try:
    import SocketServer as socketserver
except ImportError:
    import socketserver


from dss.tools import thread
from dss.tools.show import Show
from dss.config import config
from dss.storage import db
from .handler import MediaHandler

show = Show('Mobile')


# If some streams are active, the program did no close properly.
db.mobile.update({'active': True}, {'active': False})


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    is_running = False


class TCPServer(object):

    def __init__(self):
        self.host = config.get('local', 'addr')
        self.port = config.getint('local', 'tcp_port')
        self.cond = thread.Condition()
        self._server = None

    def start(self, create_thread=True):
        if not create_thread:
            self.run_server()
            return

        with self.cond:
            thread.Thread(self.run_server, name='TCP Server').start()
            self.cond.wait()
        return self

    def run_server(self):
        self._server = ThreadedTCPServer((self.host, self.port), MediaHandler)
        show('Listening at {0.host}:{0.port} (tcp)'.format(self))
        with self.cond:
            self.cond.notify_all()
        self._server.is_running = True
        self._server.serve_forever()

    def stop(self):
        self._server.is_running = False
        MediaHandler.wait_handlers()
        self._server.shutdown()
