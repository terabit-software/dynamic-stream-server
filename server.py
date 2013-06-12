from dss.streams import Providers
from dss.video import Video
from dss.thumbnail import Thumbnail
from dss.web import Server


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
        print('Server Closed')

    print('Stopping streams...')
    Video.terminate_streams()
    print('Done!')

    print('Stopping thumbnail download...')
    Thumbnail.stop_download()
    print('Done!')


if __name__ == '__main__':
    main()