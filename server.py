from dss.providers import Providers
from dss.video import Video
from dss.thumbnail import Thumbnail
from dss.web import Server
from dss.tools import show


def main():
    Providers.load()
    Video.initialize_from_stats()
    Video.auto_start()
    Thumbnail.start_download()

    server = Server()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
        show('Server Closed')

    show('Stopping streams...')
    Video.terminate_streams()
    show('Done!')

    show('Stopping thumbnail download...')
    Thumbnail.stop_download()
    show('Done!')


if __name__ == '__main__':
    main()
