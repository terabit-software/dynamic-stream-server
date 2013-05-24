import time
import subprocess
import threading
import os
try:
    # Python 3
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

import noxml
from config import config
import ffmpeg
import streams


def run_proc(id, cmd, mode):
    """ Open process with error output redirected to file.
        The standart output can be read.
    """
    log = os.path.join(config.get('log', 'dir'), '{0}-{1}'.format(mode, id))
    with open(log, 'w') as f:
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=f
        )


class Camera(object):
    run_timeout = config.getint('ffmpeg', 'timeout')
    reload_timeout = config.getint('ffmpeg', 'reload')

    def __init__(self, id, timeout=run_timeout):
        self.lock = threading.Lock()
        self.id = id
        provider = streams.select_provider(id)
        self.fn = lambda self=self: run_proc(
            self.id,
            provider.make_cmd(self.id),
            'fetch'
        )
        self.cnt = 0
        self.run = False
        self.proc = None
        self.thread = None
        self.timeout = timeout
        self.http_client = None

    def __repr__(self):
        pid = self.proc.pid if self.proc else None
        return '<{0}: Users={1} Pid={2}>'.format(self.id, self.clients, pid)

    @property
    def clients(self):
        return self.cnt + bool(self.http_client)

    @property
    def run(self):
        return self._run
    
    @run.setter
    def run(self, value):
        with self.lock:
            self._run = value 

    def inc(self, k=1):
        self.cnt += k
        if not self.proc and not self.run:
            self.proc_start()
        return self

    def dec(self):
        if self.cnt:
            self.cnt -= 1
        if not self.clients:
            self.proc_stop()
        return self

    def _proc_msg(self, pid, msg):
        return '{0} - FFmpeg[{1}] {2}'.format(self.id, pid, msg)

    def proc_start(self):
        """ Process starter on another thread.
        """
        def worker():
            self.run = True
            self.proc = self.fn()
            pid = self.proc and self.proc.pid
            print(self._proc_msg(pid, 'started'))

            while True:
                self.proc.wait()
                self.proc = None
                if self.run:
                    print(self._proc_msg(pid, 'died'))
                    time.sleep(self.reload_timeout)
                    if self.run:
                        # It might be killed after waiting
                        self.proc = self.fn()
                        pid = self.proc and self.proc.pid
                        print(self._proc_msg(pid, 'restarted'))
                        continue
                print(self._proc_msg(pid, 'stopped'))
                break

        self.thread = threading.Thread(target=worker)
        self.thread.daemon = True
        self.thread.start()

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
            self.run = False
            self._kill()
            return

        if not self.run:
            return
        self.run = False

        def stop_worker():
            time.sleep(self.timeout)
            if not self.clients:
                self._kill()
            else:
                self.run = True

        thread = threading.Thread(target=stop_worker)
        thread.daemon = True
        thread.start()


class Video(object):
    _data = {}

    @classmethod
    def start(cls, id, increment=1, http_wait=None):
        camera = cls.get_camera(id).inc(increment, http_wait=http_wait)
        print(camera)

    @classmethod
    def stop(cls, id):
        camera = cls.get_camera(id).dec()
        print(camera)

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
    lock = threading.Condition(threading.Lock())

    cam_list = None
    interval = config.getint('thumbnail', 'interval')

    class WorkerThread(threading.Thread):
        def __init__(self, id):
            super(Thumbnail.WorkerThread, self).__init__()
            self.id = id
            self.proc = self._open_proc()
            self.daemon = True

        def _open_proc(self):
            """ Select stream and open process
            """
            provider = streams.select_provider(self.id)
            source = provider.in_stream
            seek = None
            origin = None
            try:
                # Use local connection if camera is already running.
                if Video.data[self.id].run:
                    source = provider.out_stream
                    seek = 1
            except Exception:
                # If using remote server instead of local.
                self.id = provider.get_camera(self.id)
                origin = provider

            return run_proc(
                self.id,
                Thumbnail.make_cmd(self.id, source, seek, origin),
                'thumb',
            )

        def run(self):
            """ Wait until the end of the process.
            """
            self.proc.communicate()

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
            if not cls.run:
                break

            with cls.lock:
                cls.clean = False

                ths = []
                for x in cls.cam_list:
                    th = cls.WorkerThread(x)
                    th.start()
                    ths.append(th)

                cls.lock.wait(cls.interval * .75)

            error = []
            for th in ths:
                if th.proc.poll() is None:
                    error.append(th.id)
                    try:
                        th.proc.kill()
                    except OSError:
                        pass
                th.proc.wait()
            ok = len(ths) - len(error)

            if cls.run: # Show stats
                print('Finished fetching thumbnails: {0}/{1}'.format(ok, len(ths)))
                if ok != len(ths):
                    print('Could not fetch:\n' + ', '.join(error))

            with cls.lock:
                cls.clean = True
                cls.lock.notify_all()

            if not cls.run:
                break

            with cls.lock:
                cls.lock.wait(cls.interval * .25)

    @classmethod
    def make_cmd(cls, name, source, seek=None, origin=None):
        """ Generate FFmpeg command for thumbnail generation.
        """
        out_opt = config.get('thumbnail', 'output_opt')
        if seek is not None:
            out_opt += ' -ss ' + str(seek)

        # If fetching thumbnail from origin server, will need the camera
        # id that is different from camera name.
        id = name
        if origin:
            id = origin.get_id(name)

        return ffmpeg.cmd(
            config.get('thumbnail', 'input_opt'),
            source.format(name),
            out_opt,
            os.path.join(
                config.get('thumbnail', 'dir'),
                '{0}.{1}'.format(id, config.get('thumbnail', 'format'))
            )
        )

    @classmethod
    def start_download(cls):
        main_th = threading.Thread(target=cls.main_worker)
        main_th.daemon = True
        main_th.start()

    @classmethod
    def stop_download(cls):
        cls.run = False

        with cls.lock:
            cls.lock.notify_all()
            while not cls.clean:
                cls.lock.wait()
