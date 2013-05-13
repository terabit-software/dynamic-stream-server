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

    def stop(self):
        if not self.run:
            return
        self.run = False

        def stop_worker():
            time.sleep(self.timeout)
            if not self.cnt:
                try:
                    self.proc.kill()
                    self.proc.wait()
                except OSError:
                    pass
                self.proc = None
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


def start_thumbnail_download():
    cam_list = [x['id'] for x in cameras.get_cameras()]
    interval = int(config.get('thumbnail', 'interval'))


    class WorkerThread(threading.Thread):
        def __init__(self, id):
            super(WorkerThread, self).__init__()
            self.id = str(id)
            self.proc = None

        def run(self):
            source = in_stream
            try:
                # Use local connection if camera is already running
                if data[self.id].run:
                    source = out_stream
            except Exception:
                pass

            self.proc = run_proc(self.id, lambda x: make_thumb_cmd(x, source), 'thumb')
            self.proc.communicate()

    def main_worker():
        while True:
            ths = []
            for x in cam_list:
                th = WorkerThread(x)
                th.daemon = True
                th.start()
                ths.append(th)
        
            time.sleep(interval * .75)
            error = []
            for th in ths:
                while not th.proc:
                    print('No proc on ' + th.id)
                    sleep(0.1)
                if th.proc.poll() is None:
                    error.append(th.id)
                    th.proc.kill()
                th.proc.wait()
            ok = len(ths) - len(error)
            print('Finished fetching thumbnails: {0}/{1}'.format(ok, len(ths)))
            print('Could not fetch:\n' + ', '.join(error))
            ths = []

            time.sleep(interval * .25)

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


class Handler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        info = urlparse.urlparse(self.path)
        id, action = info.path.strip('/').split('/')
        if action == 'start':
            start(id, data)
        else:
            stop(id, data)

    do_POST = do_GET


def initialize_from_stats():
    stats = get_stats()['server']['application']
    if isinstance(stats, dict): stats = [stats]
    app = config.get('rtmp-server', 'app')
    try:
        app = next(x['live'] for x in stats if x['name'] == app)
    except StopIteration:
        raise NameError('No app named %r' % app)

    # App clients
    streams = app['stream']
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


if __name__ == '__main__':

    initialize_from_stats()
    start_thumbnail_download()

    host = config.get('local', 'addr')
    port = int(config.get('local', 'port'))

    socketserver.TCPServer.allow_reuse_address = True
    ss = None
    while True:
        try:
            ss = socketserver.TCPServer((host, port), Handler)
        except IOError:
            print('Waiting TCP port to be used.')
            time.sleep(run_timeout)
        else:
            print('Connected to %s:%s' % (host, port))
            break

    try:
        ss.serve_forever()
    except KeyboardInterrupt:
        ss.server_close()
        print('Server Closed')

