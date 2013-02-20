import os
import time
import subprocess
import BaseHTTPServer
import SocketServer
import urlparse
import socket
import thread
import threading


data = {}
run_timeout = 10
in_stream = 'rtmp://200.141.78.68:1935/cet-rio/{0}.stream ' + \
            'pageUrl=http://transito.rio.rj.gov.br/transito.html'
out_stream = 'rtmp://localhost:1935/cetrio/{0}'

class Camera(object):
    def __init__(self, fn, timeout=run_timeout):
        self.lock = threading.Lock()
        self.fn = fn
        self.cnt = 0
        self.run = True
        self.proc = None
        self.thread = None
        self.timeout = timeout

    def __repr__(self):
        pid = self.proc.pid if self.proc else 0
        return '<Camera: {0} Usuarios, FFMPEG pid: {1}>'.format(self.cnt, pid)

    @property
    def run(self):
        return self._run
    
    @run.setter
    def run(self, value):
        with self.lock:
            self._run = value 

    def inc(self):
        self.cnt += 1
        return self

    def dec(self):
        if self.cnt:
            self.cnt -= 1
        return self

    def start(self):
        def worker():
            self.run = True
            self.proc = self.fn()
            
            while True:
                self.proc.wait()
                print('FFMPEG died!')
                break
                if self.run:
                    time.sleep(self.timeout)
                    self.proc = self.fn()

        self.thread = threading.Thread(target=worker)
        self.thread.setDaemon(True)
        self.thread.start()

    def stop(self):
        if not self.run:
            return
        self.run = False

        time.sleep(run_timeout)
        if not self.cnt:
            self.proc.kill()
            self.proc.wait()
            self.proc = None
        else:
            self.run = True

def make_cmd(num):
    return ['/usr/local/bin/ffmpeg', '-probesize', '200K', '-re', '-i', 
            in_stream.format(num), '-vcodec', 'libx264', 
            '-b:v', '100k', '-an', '-f', 'flv', out_stream.format(num)]

def run_proc(num):
    cmd = make_cmd(num)
    print(' '.join(cmd))
    return subprocess.Popen(cmd, 
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)

def start(num, data):
    try:
        camera = data[num]
    except KeyError:
        camera = Camera(lambda: run_proc(num))
        data[num] = camera

    if not camera.cnt:
        camera.start()
    camera.inc()
    print(data)

def stop(num, data):
    try:
        camera = data[num].dec()
    except KeyError:
        return

    if not camera.cnt:
        camera.stop()
    print(data)

class Handler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
        info = urlparse.urlparse(self.path)
        print info
        id, action = info.path.strip('/').split('/')
        if action == 'start':
            start(id, data)
        else:
            stop(id, data)

    do_POST = do_GET

        
ss = SocketServer.TCPServer(("", 8000), Handler)
ss.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
ss.serve_forever()
