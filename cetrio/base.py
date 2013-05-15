import time
import subprocess
import threading
import os
import shlex
try:
    # Python 3
    import socketserver
    from http import server
    import urllib.parse as urlparse
    from urllib.request import urlopen
except ImportError:
    import SocketServer as socketserver
    import BaseHTTPServer as server
    import urlparse
    from urllib2 import urlopen

import noxml
from config import config
import cameras

data = {}
run_timeout = int(config.get('ffmpeg', 'timeout'))
reload_timeout = int(config.get('ffmpeg', 'reload'))

in_stream = '{0}{1}/{2} {3}'.format(
    config.get('remote-rtmp-server', 'addr'),
    config.get('remote-rtmp-server', 'app'),
    config.get('remote-rtmp-server', 'stream'),
    config.get('remote-rtmp-server', 'data'),
)

out_stream = '{0}{1}/'.format(
    config.get('rtmp-server', 'addr'),
    config.get('rtmp-server', 'app')
) + '{0}'


def get_stats():
    addr = config.get('http-server', 'addr')
    stat = config.get('http-server', 'stat_url')
    data = urlopen(addr + stat).read()
    return noxml.load(data)


class Camera(object):
    def __init__(self, fn, timeout=run_timeout):
        self.lock = threading.Lock()
        self.fn = fn
        self.cnt = 0
        self.run = False
        self.proc = None
        self.thread = None
        self.timeout = timeout

    def __repr__(self):
        pid = self.proc.pid if self.proc else 0
        return '<Camera: {0} Usuarios, FFmpeg pid: {1}>'.format(self.cnt, pid)

    @property
    def run(self):
        return self._run
    
    @run.setter
    def run(self, value):
        with self.lock:
            self._run = value 

    def inc(self, k=1):
        self.cnt += k
        return self

    def dec(self):
        if self.cnt:
            self.cnt -= 1
        return self

    def start(self):
        def worker():
            self.run = True
            self.proc = self.fn()
            print('Starting FFmpeg')
            
            while True:
                self.proc.wait()
                print('FFmpeg from pid {0} died!'.format(self.proc and self.proc.pid))
                self.proc = None
                if self.run:
                    time.sleep(reload_timeout)
                    if self.run:
                        # It might be killed after waiting
                        self.proc = self.fn()
                        print('Restarting FFmpeg')
                        continue
                break

        self.thread = threading.Thread(target=worker)
        self.thread.daemon = True
        self.thread.start()

    def _kill(self):
        """ Kill the FFmpeg process. Don't call this function directly,
            otherwise the process may be restarted. Call `stop` instead.
        """
        try:
            self.proc.kill()
            self.proc.wait()
        except OSError:
            pass
        finally:
            self.proc = None

    def stop(self, now=False):
        if not self.run:
            return
        self.run = False

        if now:
            self._kill()
            return

        def stop_worker():
            time.sleep(self.timeout)
            if not self.cnt:
                self._kill()
            else:
                self.run = True

        thread = threading.Thread(target=stop_worker)
        thread.daemon = True
        thread.start()


def make_cmd(num):
    """ Generate FFmpeg command to fetch video from
        remote source.
    """
    inp = config.get('ffmpeg', 'input_opt')
    out = config.get('ffmpeg', 'output_opt')

    args = [config.get('ffmpeg', 'bin')]
    args += shlex.split(inp)
    args += ['-probesize', config.get('ffmpeg', 'probe')]
    args += ['-i',  in_stream.format(num)]
    args += shlex.split(out)
    args.append(out_stream.format(num))
    return args


def make_thumb_cmd(num, source=None):
    """ Generate FFmpeg command for thumbnail generation.
    """
    inp = config.get('thumbnail', 'input_opt')
    out = config.get('thumbnail', 'output_opt')

    args = [config.get('ffmpeg', 'bin')]
    args += shlex.split(inp)
    args += ['-probesize', config.get('ffmpeg', 'probe')]
    if source is None:
        source = in_stream
    args += ['-i', source.format(num)]
    args += shlex.split(out)
    out = os.path.join(
        config.get('thumbnail', 'dir'),
        '{0}.{1}'.format(num, config.get('thumbnail', 'format'))
    )
    args.append(out)
    return args


class LockSleepThread(threading.Thread):
    def __init__(self, seconds, lock):
        super(LockSleepThread, self).__init__()
        self.seconds = seconds
        self.lock = lock
        self.lock.acquire()
        self.daemon = True

    def run(self):
        time.sleep(self.seconds)
        try:
            self.lock.release()
        except Exception:
            pass


def lock_sleep(seconds, lock):
    LockSleepThread(seconds, lock).start()
    lock.acquire()
    try:
        lock.release()
    except Exception:
        pass


THUMBNAIL_RUN = True
THUMBNAIL_LOCK = threading.Lock()
THUMBNAIL_CLEANUP = False

def start_thumbnail_download():
    cam_list = [x['id'] for x in cameras.get_cameras()]
    interval = int(config.get('thumbnail', 'interval'))

    class WorkerThread(threading.Thread):
        def __init__(self, id):
            super(WorkerThread, self).__init__()
            self.id = str(id)
            self.proc = self._open_proc()
            self.daemon = True

        def _open_proc(self):
            """ Select stream and open process
            """
            source = in_stream
            try:
                # Use local connection if camera is already running
                if data[self.id].run:
                    source = out_stream
            except Exception:
                pass

            return run_proc(self.id, lambda x: make_thumb_cmd(x, source), 'thumb')

        def run(self):
            """ Wait until the end of the process.
            """
            self.proc.communicate()

    def main_worker():
        global THUMBNAIL_CLEANUP
        while True:
            if not THUMBNAIL_RUN:
                break
            THUMBNAIL_CLEANUP = False
            ths = []
            for x in cam_list:
                th = WorkerThread(x)
                th.start()
                ths.append(th)
        
            lock_sleep(interval * .75, THUMBNAIL_LOCK)
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

            if THUMBNAIL_RUN: # Show stats
                print('Finished fetching thumbnails: {0}/{1}'.format(ok, len(ths)))
                if ok != len(ths):
                    print('Could not fetch:\n' + ', '.join(error))

            THUMBNAIL_CLEANUP = True

            if not THUMBNAIL_RUN:
                break
            lock_sleep(interval * .25, THUMBNAIL_LOCK)

    main_th = threading.Thread(target=main_worker)
    main_th.daemon = True
    main_th.start()


def run_proc(num, cmd_maker, mode):
    cmd = cmd_maker(num)
    #print(cmd, ''.join(cmd), sep='\n')
    #print('Starting FFmpeg')

    log = os.path.join(config.get('log', 'dir'), '{0}-{1}'.format(mode, num))
    with open(log, 'w') as f:
        return subprocess.Popen(cmd, 
                                stdout=subprocess.PIPE,
                                stderr=f)


def start(num, data, increment=1):
    try:
        camera = data[num]
    except KeyError:
        camera = Camera(lambda: run_proc(num, make_cmd, 'fetch'))
        data[num] = camera

    if not camera.proc and not camera.run:
        camera.start()
    camera.inc(increment)
    print(data)


def stop(num, data):
    try:
        camera = data[num].dec()
    except KeyError:
        return

    if not camera.cnt:
        camera.stop()
    print(data)


def initialize_from_stats():
    stats = get_stats()['server']['application']
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

        start(stream['name'], data, nclients)