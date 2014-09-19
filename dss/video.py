from __future__ import division
import time
import warnings

try:
    # Python 3
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

from .config import config
from .providers import Providers
from .tools import process, thread, noxml
from .tools.show import show
from .stats import StreamStats


class StreamHTTPClient(object):
    """ Emulate the behaviour of a RTMP client when there's an HTTP access
        for a certain Stream. If no other HTTP access is made within the
        timeout period, the `Stream` instance will be decremented.
    """
    def __init__(self, parent):
        self.lock = thread.Condition()
        self.timeout = None
        self.parent = parent
        self._stop()

    def wait(self, timeout):
        self.timeout = timeout
        if not self._stopped:
            with self.lock:
                self._stop(restart=True)
                self.lock.notify_all()
        else:
            self.thread = thread.Thread(self._wait_worker).start()
        return self

    def _wait_worker(self):
        with self.lock:
            while self._stopped:
                self._start()
                self.lock.wait(self.timeout)
            self._stop()
            self.parent.dec(http=True)

    def _stop(self, restart=False, data=True):
        self._stopped = data
        if not restart:
            self._stopped_info = data

    def _start(self):
        self._stop(data=False)

    def __bool__(self):
        return not self._stopped_info
    __nonzero__ = __bool__


class Stream(object):
    _ffmpeg = config['ffmpeg']
    run_timeout = _ffmpeg.getint('timeout')
    reload_timeout = _ffmpeg.getint('reload')

    def __init__(self, id, timeout=run_timeout):
        self.lock = thread.Lock()
        self.id = id
        provider = Providers.select(id)
        try:
            provider.get_stream(id)
        except Exception:
            # The prefix match but the id is not real
            raise KeyError('Invalid id for {0.identifier!r} ({0.name}) provider'.format(provider))

        self.fn = lambda self=self: process.run_proc(
            self.id,
            provider.make_cmd(self.id),
            'fetch'
        )
        self.cnt = 0
        self._proc_run = False
        self.proc = None
        self.thread = None
        self.timeout = timeout
        self.http_client = StreamHTTPClient(self)
        self.stats = StreamStats()

    def __repr__(self):
        pid = self.proc.pid if self.proc else None
        return '<{0}: Users={1} Pid={2}>'.format(self.id, self.clients, pid)

    @property
    def clients(self):
        return self.cnt + bool(self.http_client)

    @property
    def alive(self):
        return self.proc or self.proc_run

    @property
    def proc_run(self):
        return self._proc_run
    
    @proc_run.setter
    def proc_run(self, value):
        with self.lock:
            self._proc_run = value

    def inc(self, k=1, http_wait=None):
        """ Increment user count unless it is a http user (then http_wait
            must be set). If so, it should wait a period of time on another
            thread and the clients property will be indirectly incremented.

            If there is no process running and it should be, a new process
            will be started.
        """
        if http_wait:
            self.http_client.wait(http_wait)
        else:
            self.cnt += k
        if not self.proc and not self.proc_run:
            self.proc_start()
        show(self)
        return self

    def dec(self, http=False):
        """ Decrement the user count unless it is a http user. If there are no
            new clients, the process is scheduled to shutdown.
        """
        if not http:
            if self.cnt:
                self.cnt -= 1
        if not self.clients:
            self.proc_stop()
        show(self)
        return self

    def _proc_msg(self, pid, msg):
        return '{0} - FFmpeg[{1}] {2}'.format(self.id, pid, msg)

    def proc_start(self):
        """ Process starter on another thread.
        """
        def worker():
            self.proc_run = True
            start_msg = 'started'
            while True:
                with self.fn() as self.proc:
                    self.stats.timed.started()
                    pid = self.proc and self.proc.pid
                    show(self._proc_msg(pid, start_msg))
                    self.proc.wait()
                    self.proc = None

                    if self.proc_run:  # Should be running, but isn't
                        self.stats.timed.died()
                        show(self._proc_msg(pid, 'died'))
                        time.sleep(self.reload_timeout)
                        if self.proc_run:  # It might have been stopped after waiting
                            start_msg = 'restarted'
                            continue
                    show(self._proc_msg(pid, 'stopped'))
                    break

        self.thread = thread.Thread(worker).start()

    def _kill(self):
        """ Kill the FFmpeg process. Don't call this function directly,
            otherwise the process may be restarted. Call `proc_stop` instead.
        """
        try:
            self.proc.kill()
            self.proc.wait()
        except (OSError, AttributeError):
            pass
        finally:
            self.proc = None

    def proc_stop(self, now=False):
        if now:
            self.proc_run = False
            self._kill()
            return

        if not self.proc_run:
            return
        self.proc_run = False

        def stop_worker():
            time.sleep(self.timeout)
            if not self.clients:
                self._kill()
            else:
                self.proc_run = True

        thread.Thread(stop_worker).start()


class Video(object):
    _data = {}
    _data_lock = thread.Lock()
    run = True

    @classmethod
    def start(cls, id, increment=1, http_wait=None):
        if cls.run:
            cls.get_stream(id).inc(increment, http_wait=http_wait)

    @classmethod
    def stop(cls, id):
        cls.get_stream(id).dec()

    @classmethod
    def get_stream(cls, id):
        with cls._data_lock:
            stream = cls._data.get(id)
            if stream is None:
                stream = Stream(id)
                cls._data[id] = stream
            return stream

    @classmethod
    def get_stats(cls):
        http = config['http-server']
        addr = http['addr']
        stat = http['stat_url']
        data = urlopen(addr + stat).read()
        return noxml.load(data, ('stream', 'application'))

    @classmethod
    def initialize_from_stats(cls):
        try:
            stats = cls.get_stats()['server']['application']
        except IOError:
            return

        app = config['rtmp-server']['app']
        try:
            app = next(x['live'] for x in stats if x['name'] == app)
        except StopIteration:
            raise RuntimeError('No app named %r' % app)

        # App clients
        stream_list = app.get('stream')
        if stream_list is None:
            return

        for stream in stream_list:
            # Stream clients
            nclients = int(stream['nclients'])

            if 'publishing' in stream:
                nclients -= 1

            if nclients <= 0:
                continue

            try:
                cls.start(stream['name'], nclients)
            except KeyError:
                warnings.warn('Invalid stream name: %r' % stream['name'])

    @classmethod
    def auto_start(cls):
        for id in config['general'].get_list('auto_start'):
            cls.start(id)

        for p in config['general'].get_list('auto_start_provider'):
            streams = Providers.select(p).streams()
            for id in streams:
                cls.start(id)

    @classmethod
    def terminate_streams(cls):
        with cls._data_lock:
            cls.run = False
            for strm in cls._data.values():
                strm.proc_stop(now=True)
