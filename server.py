from dss.providers import Providers
from dss.video import Video
from dss.thumbnail import Thumbnail
from dss.web import Server
from dss.tools import show_close
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
        pass

    show_close(manager.stop, 'Stopping HTTP Server', True)
    show_close(Video.terminate_streams, 'Stopping streams')
    show_close(Thumbnail.stop_download, 'Stopping thumbnail download')
    show_close(tcp_server.stop, 'Stopping TCP Server')


if __name__ == '__main__':
    main()
