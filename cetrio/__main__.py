import base
import web


def main():
    base.Video.initialize_from_stats()
    base.Thumbnail.start_download()

    server = web.Server()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
        print('Server Closed')

    print('Stopping cameras...')
    base.Video.terminate_cameras()
    print('Done!')

    print('Stopping thumbnail download...')
    base.Thumbnail.stop_download()
    print('Done!')


main()
