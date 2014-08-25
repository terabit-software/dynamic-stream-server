from dss.providers import Providers
from dss.video import Video
from dss.thumbnail import Thumbnail
from dss.web import Server
from dss.tools import show_close
from dss.tornado_setup import TornadoManager
from dss.mobile_streaming import TCPServer
from dss.web_handlers.mobile_stream import MobileStreamLocation


_stop_tasks = []


def load(start, stop=None, desc=None, wait_interrupt=False):
    if stop is None:
        obj = start
        start = obj.start
        stop = obj.stop
    _stop_tasks.append((stop, desc))

    if wait_interrupt:
        try:
            start()
        except KeyboardInterrupt:
            pass
    else:
        start()


def shutdown():
    for task, name in _stop_tasks[::-1]:
        # Close tasks in reverse order
        show_close(task, 'Stopping {}'.format(name))


def main():
    Providers.load()
    Video.initialize_from_stats()
    load(Thumbnail.start_download, Thumbnail.stop_download, desc='Thumbnail Download'),
    load(Video.auto_start, Video.terminate_streams, desc='Video Streams'),
    load(TCPServer(), desc='TCP Server'),
    load(Server(), desc='HTTP Server Handlers'),
    load(MobileStreamLocation.broadcaster, desc='Websocket Broadcaster')
    load(TornadoManager(), desc='HTTP Server', wait_interrupt=True)

    shutdown()


if __name__ == '__main__':
    main()
