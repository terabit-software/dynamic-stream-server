import re
import time
import os
try:
    # Python 3
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen
from concurrent import futures

import noxml
from config import config
import ffmpeg
import streams
import thread_tools
import process_tools


def run_proc(id, cmd, mode):
    """ Open process with error output redirected to file.
        The standart output can be read.
    """
    log = os.path.join(config.get('log', 'dir'), '{0}-{1}'.format(mode, id))
    with open(log, 'w') as f:
        return process_tools.Popen(
            cmd,
            stdout=process_tools.PIPE,
            stderr=f
        )


class HTTPClient(object):
    """ Emulate the behaviour of a RTMP client when there's an HTTP access
        for a certain camera. If no other HTTP access is made within the
        timeout period, the `Camera` instance will be decremented.
    """
    def __init__(self, parent):
        self.lock = thread_tools.Condition()
        self.stopped = True
        self.timeout = None
        self.parent = parent

    def wait(self, timeout):
        self.timeout = timeout
        if not self.stopped:
            with self.lock:
                self.stopped = True
                self.lock.notify_all()
        else:
            self.thread = thread_tools.Thread(self._wait_worker).start()
        return self

    def _wait_worker(self):
        with self.lock:
            while self.stopped:
                self.stopped = False
                self.lock.wait(self.timeout)
            self.stopped = True
            self.parent.dec(http=True)

    def __bool__(self):
        return not self.stopped
    __nonzero__ = __bool__


class Camera(object):
    run_timeout = config.getint('ffmpeg', 'timeout')
    reload_timeout = config.getint('ffmpeg', 'reload')

    def __init__(self, id, timeout=run_timeout):
        self.lock = thread_tools.Lock()
        self.id = id
        provider = streams.select_provider(id)
        self.fn = lambda self=self: run_proc(
            self.id,
            provider.make_cmd(self.id),
            'fetch'
        )
        self.cnt = 0
        self._proc_run = False
        self.proc = None
        self.thread = None
        self.timeout = timeout
        self.http_client = HTTPClient(self)

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
        print(self)
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
        print(self)
        return self

    def _proc_msg(self, pid, msg):
        return '{0} - FFmpeg[{1}] {2}'.format(self.id, pid, msg)

    def proc_start(self):
        """ Process starter on another thread.
        """
        def worker():
            self.proc_run = True
            with self.fn() as self.proc:
                pid = self.proc and self.proc.pid
                print(self._proc_msg(pid, 'started'))

                while True:
                    self.proc.wait()
                    self.proc = None
                    if self.proc_run:
                        print(self._proc_msg(pid, 'died'))
                        time.sleep(self.reload_timeout)
                        if self.proc_run:
                            # It might be killed after waiting
                            self.proc = self.fn()
                            pid = self.proc and self.proc.pid
                            print(self._proc_msg(pid, 'restarted'))
                            continue
                    print(self._proc_msg(pid, 'stopped'))
                    break

        self.thread = thread_tools.Thread(worker).start()

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

        thread_tools.Thread(stop_worker).start()


class Video(object):
    _data = {}

    @classmethod
    def start(cls, id, increment=1, http_wait=None):
        cls.get_camera(id).inc(increment, http_wait=http_wait)

    @classmethod
    def stop(cls, id):
        cls.get_camera(id).dec()

    @classmethod
    def get_camera(cls, id):
        cam = cls._data.get(id)
        if cam is None:
            cam = Camera(id)
            cls._data[id] = cam
        return cam

    @classmethod
    def get_stats(cls):
        addr = config.get('http-server', 'addr')
        stat = config.get('http-server', 'stat_url')
        data = urlopen(addr + stat).read()
        return noxml.load(data)

    @classmethod
    def initialize_from_stats(cls):
        stats = cls.get_stats()['server']['application']
        if isinstance(stats, dict): stats = [stats]
        app = config.get('rtmp-server', 'app')
        try:
            app = next(x['live'] for x in stats if x['name'] == app)
        except StopIteration:
            raise NameError('No app named %r' % app)

        # App clients
        streams = app.get('stream')
        if streams is None:
            return
        if isinstance(streams, dict):
            streams = [streams]

        for stream in streams:
            # Stream clients
            nclients = int(stream['nclients'])

            if 'publishing' in stream:
                nclients -= 1

            if nclients <= 0:
                continue

            cls.start(stream['name'], nclients)

    @classmethod
    def terminate_cameras(cls):
        for cam in cls._data.values():
            cam.proc_stop(now=True)


class Thumbnail(object):
    run = True
    clean = True
    lock = thread_tools.Condition()

    cam_list = None
    interval = config.getint('thumbnail', 'interval')
    workers = config.getint('thumbnail', 'workers')
    timeout = config.getint('thumbnail', 'timeout')

    class Worker(object):
        def __init__(self, id, timeout):
            self.id = id
            self.timeout = timeout
            self.proc = None
            self.lock = None

        def _open_proc(self):
            """ Select stream and open process
            """
            provider = streams.select_provider(self.id)
            source = provider.in_stream
            seek = None
            origin = None
            id = self.id

            # Use local connection if camera is already running.
            if Video.get_camera(self.id).alive:
                source = provider.out_stream
                seek = 1
            else:
                # If using remote server identifier instead of local.
                id = provider.get_camera(self.id)
                origin = provider

            return run_proc(
                self.id,
                Thumbnail.make_cmd(id, source, seek, origin),
                'thumb',
            )

        def _close_proc(self):
            """ Kill the open process.
            """
            if self.proc.poll() is not None:
                return
            try:
                self.proc.kill()
                self.proc.wait()
            except OSError:
                pass

        def __call__(self):
            """ Wait until the first of these events :
                    - End of the process;
                    - Timeout (on a separeted thread);
                    - User request for termination (on the same separeted
                      thread as the timeout).
                Returns the process output code.
            """
            self.lock = thread_tools.Condition.from_condition(Thumbnail.lock)
            with self.lock:
                if not Thumbnail.run:
                    return

                self.proc = self._open_proc()
                def waiter():
                    with Thumbnail.lock:
                        thread_tools.Condition.wait_for_any(
                            [Thumbnail.lock, self.lock], self.timeout
                        )
                        self._close_proc()
                thread_tools.Thread(waiter).start()

            self.proc.communicate()
            with self.lock:
                self.lock.notify_all()

            return self.proc.poll()

    @classmethod
    def main_worker(cls):
        cams = [p.cameras() for p in streams.providers.values()]
        cls.cam_list = [item for sublist in cams for item in sublist]

        try:
            delay = config.getint('thumbnail', 'start_after')
        except Exception:
            delay = 0
        with cls.lock:
            cls.lock.wait(delay)

        while True:
            with cls.lock:
                if not cls.run:
                    break
                cls.clean = False
            t = time.time()
            with futures.ThreadPoolExecutor(cls.workers) as executor:
                map = dict(
                    (executor.submit(cls.Worker(x, cls.timeout)), x)
                    for x in cls.cam_list
                )
                done = {}
                for future in futures.as_completed(map):
                    done[map[future]] = future.result()
                error = [x for x in cls.cam_list if done[x] != 0]

                if cls.run: # Show stats
                    cams = len(cls.cam_list)
                    print('Finished fetching thumbnails: {0}/{1}'.format(cams - len(error), cams))
                    if error:
                        print('Could not fetch:\n' + ', '.join(error))

            t = time.time() - t
            interval = cls.interval - t
            with cls.lock:
                cls.clean = True
                cls.lock.notify_all()

                if interval >= 0:
                    cls.lock.wait(interval)
                elif cls.run:
                    print('Thumbnail round delayed by {0:.2f} seconds'.format(-interval))


    @classmethod
    def make_cmd(cls, name, source, seek=None, origin=None):
        """ Generate FFmpeg command for thumbnail generation.
        """
        out_opt = config.get('thumbnail', 'output_opt')
        if seek is not None:
            out_opt += ' -ss ' + str(seek)

        resize_opt = config.get('thumbnail', 'resize_opt')
        sizes = config.get('thumbnail', 'sizes')
        sizes = re.findall(r'(\w+):(\w+)', sizes)

        resize = [''] + [resize_opt.format(s[1]) for s in sizes]
        names = [''] + ['-' + s[0] for s in sizes]

        # If fetching thumbnail from origin server, will need the camera
        # id that is different from camera name.
        id = name
        if origin:
            id = origin.get_id(name)

        dir = config.get('thumbnail', 'dir')
        format = config.get('thumbnail', 'format')

        outputs = [
            os.path.join(dir,'{0}{1}.{2}'.format(id, _name, format))
            for _name in names
        ]

        return ffmpeg.cmd_outputs(
            config.get('thumbnail', 'input_opt'),
            source.format(name),
            out_opt,
            resize,
            outputs
        )

    @classmethod
    def start_download(cls):
        thread_tools.Thread(cls.main_worker).start()

    @classmethod
    def stop_download(cls):
        with cls.lock:
            cls.run = False
            cls.lock.notify_all()
            while not cls.clean:
                cls.lock.wait()
