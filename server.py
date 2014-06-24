from dss.providers import Providers
from dss.video import Video
from dss.thumbnail import Thumbnail
from dss.web import Server
from dss.tools import show
from dss.tornado_setup import TornadoManager
from dss.mobile_streaming import TCPServer


def main():
    Providers.load()
    Video.initialize_from_stats()
    Video.auto_start()
    Thumbnail.start_download()
    tcp_server = TCPServer()
    tcp_server.start()

    server = Server()
    server.start()
    manager = TornadoManager()
    try:
        manager.start()
    except KeyboardInterrupt:
        manager.stop()
        show('Server Closed')

    show('Stopping streams...')
    Video.terminate_streams()
    show('Done!')

    show('Stopping thumbnail download...')
    Thumbnail.stop_download()
    show('Done!')

    tcp_server.stop()


if __name__ == '__main__':
    main()
