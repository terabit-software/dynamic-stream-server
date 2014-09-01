from dss.config import config
from dss.providers import Providers
from dss.video import Video
from dss.thumbnail import Thumbnail
from dss.web import Server
from dss.tools import show_close
from dss.tornado_setup import TornadoManager
from dss.mobile import TCPServer
from dss.web_handlers.mobile_stream import MobileStreamLocation


_stop_tasks = []


def run_start(fn):
    try:
        for f in fn:
            f()
    except TypeError:
        fn()


def load(start, stop=None, desc=None, enabled=None, wait_interrupt=False):
    if enabled and not config.getboolean(enabled, 'enabled'):
        return

    if stop is None:
        obj = start
        start = obj.start
        stop = obj.stop
    _stop_tasks.append((stop, desc))

    if wait_interrupt:
        try:
            run_start(start)
        except KeyboardInterrupt:
            pass
    else:
        run_start(start)


def shutdown():
    for task, name in _stop_tasks[::-1]:
        # Close tasks in reverse order
        show_close(task, 'Stopping {}'.format(name))


def main():
    load(Providers.load, Providers.finish, desc='Stream Providers')

    load([Video.initialize_from_stats, Video.auto_start],
         Video.terminate_streams,
         desc='Video Streams',
         enabled='video_start'),

    load(Thumbnail.start_download,
         Thumbnail.stop_download,
         desc='Thumbnail Download',
         enabled='thumbnail'),

    load(TCPServer(), desc='TCP Server', enabled='mobile'),

    load(Server(), desc='HTTP Server Handlers'),

    load(MobileStreamLocation.broadcaster,
         desc='Websocket Broadcaster',
         enabled='mobile')

    load(TornadoManager(), desc='HTTP Server', wait_interrupt=True)

    shutdown()


if __name__ == '__main__':
    main()
