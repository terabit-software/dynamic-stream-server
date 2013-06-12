from dss.streams import Providers
from dss.base import Video, Thumbnail
from dss.web import Server


def main():
    Providers.load()
    Video.initialize_from_stats()
    Thumbnail.start_download()

    server = Server()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
        print('Server Closed')

    print('Stopping streams...')
    Video.terminate_streams()
    print('Done!')

    print('Stopping thumbnail download...')
    Thumbnail.stop_download()
    print('Done!')


if __name__ == '__main__':
    main()
