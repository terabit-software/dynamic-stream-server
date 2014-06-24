#!/usr/bin/env python
from __future__ import print_function
import os
import json
import struct
import tempfile
import shutil
import random
import queue
import makeobj

try:
    import socketserver
except ImportError:
    import SocketServer as socketserver
try:
    import fcntl
except ImportError:
    fcntl = None

from .tools import buffer, thread, process, ffmpeg, show
from .config import config

rtmpconf = config['rtmp-server']
HEADER_SIZE = 5  # bytes
PIPE_SIZE = None


class DataContent(makeobj.Obj):
    metadata = 0
    video = 1
    audio = 2
    userdata = 3


def set_pipe_max_size(*pipes):
    global PIPE_SIZE
    if PIPE_SIZE is None:
        # On the first time, try to get the max pipe
        # size value. Should only work on Linux
        try:
            with open('/proc/sys/fs/pipe-max-size') as f:
                PIPE_SIZE = int(f.read())
        except IOError:
            PIPE_SIZE = False

    if not PIPE_SIZE:
        return

    F_SETPIPE_SZ = 1031
    for pipe in pipes:
        fcntl.fcntl(pipe, F_SETPIPE_SZ, PIPE_SIZE)


class Media(thread.Thread):
    timeout = 10

    def __init__(self, pipe, name=None):
        super(Media, self).__init__(name=name)
        self.pipe = pipe
        self.count = 0
        self._run = True
        self.queue = queue.Queue()
        self.lock = thread.Lock()

    def run(self):
        while True:
            with self.lock:
                if not self._run:
                    break
            data = self.queue.get(timeout=self.timeout)
            if data is None:
                break
            os.write(self.pipe, data)

    def stop(self):
        with self.lock:
            self._run = False
        self.queue.put(None)
        self.join()
        os.close(self.pipe)
        print('Thread {0!r} has ended'.format(self.name))  # TODO: Remove this

    def add_data(self, data):
        self.queue.put(data)
        self.count += 1


class MediaHandler(socketserver.BaseRequestHandler, object):
    """  Packet header description

        The packet header will provide the type of payload data, and the size.

        [ T | S | S | S | S | D | D | ... ]

        T - 1st byte              - Type of message
        S - 2nd to 5th bytes      - Size of payload
        D - Data payload

        Currently we envision just 4 types of messages:
        Metadata, Video, Audio and User generated data.
    """

    def __init__(self, *args, **kw):
        self.run = True
        self.buffer = None
        self.proc = None
        self.video = None
        self.audio = None
        self.tmpdir = tempfile.mkdtemp()
        self.__cleanup_executed = False
        self.destination_url = os.path.join(rtmpconf['addr'], rtmpconf['app'], self._get_random_name())
        print('Publish point:', self.destination_url)

        super(MediaHandler, self).__init__(*args, **kw)

    def file(self, name, open_options=None):
        """ Return the name of a file in the temp dir.
            If open_options is supplied, the file will
            be opened and returned.
        """
        fname = os.path.join(self.tmpdir, name)
        if open_options is None:
            return fname
        return open(fname, open_options)

    def cleanup(self):
        """ Close pipes, remove files and temp dir and
            kills the transcoding process.
        """
        if self.__cleanup_executed:
            return
        self.audio.stop()
        self.video.stop()

        shutil.rmtree(self.tmpdir)
        self.__cleanup_executed = True

    #__del__ = cleanup  # TODO Is this required?

    def handle(self):
        self.buffer = buffer.Buffer(self.request)
        try:
            self.handle_loop()
        finally:
            try:
                self.cleanup()
            except Exception as e:
                print('Exception while cleaning:', repr(e))

    def handle_loop(self):
        audio_filename = self.file('audio.aac')
        video_filename = self.file('video.ts')
        try:
            os.mkfifo(audio_filename)
            os.mkfifo(video_filename)
        except OSError as e:
            print('Failed to create FIFO:', e)
            return

        audio_pipe = os.open(audio_filename, os.O_RDWR)
        video_pipe = os.open(video_filename, os.O_RDWR)
        set_pipe_max_size(audio_pipe, video_pipe)

        self.audio = Media(audio_pipe).start()
        self.video = Media(video_pipe).start()

        args = ffmpeg.cmd_inputs(
            '-y -re', [audio_filename, video_filename],
            '-c:v copy -c:a libfdk_aac -b:a 64k -f flv',
            self.destination_url
        )

        with self.file('proc_output', 'w') as out:
            with self.file('proc_err', 'w') as err:
                self.handle_proc_loop(args, out, err)

    def handle_proc_loop(self, proc_args, stdout, stderr):
        """ Open transcoding process and read data from buffer
            until the client stops sending data.
        """
        with process.Popen(proc_args, stdout=stdout, stderr=stderr) as self.proc:
            while True:
                type, payload = self.read_data()
                if not self.run or type is None:
                    break
                self.handle_content(type, payload)
            try:
                self.proc.kill()
                self.proc.wait()
            except Exception as e:
                print('Proc exit:', repr(e))

    def handle_content(self, type, payload):
        try:
            type = DataContent[type]
        except KeyError:
            print('Invalid header type "%s"' % type)

        if type is DataContent.metadata:
            print('Meta:', repr(payload))
        elif type is DataContent.video:
            self.video.add_data(payload)
        elif type is DataContent.audio:
            self.audio.add_data(payload)
        else:
            print(json.loads(payload.decode()))

    def process_header(self, data):
        """ Strips out the header
            Takes away the header data and returns it as a tuple of values.
        """
        size = struct.unpack('!I', data[1:])
        return data[0], size[0]

    def read_data(self):
        """ Read next packet from buffer.
            Refer to the "MediaHandler" doc for the packet description.
        """
        buff = self.buffer.read(HEADER_SIZE)
        if not buff:
            return None, None
        typ, size = self.process_header(buff)
        payload = self.buffer.read(size)
        if not payload:
            return None, None
        return typ, payload

    def _get_random_name(self):
        # TODO change this
        return 'stream' + str(random.randint(1, 1000000))


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True


class TCPServer(object):

    def __init__(self):
        self.host = config.get('local', 'addr')
        self.port = config.getint('local', 'tcp_port')
        self.cond = thread.Condition()
        self._server = None

    def start(self):
        with self.cond:
            thread.Thread(self.run_server).start()
            self.cond.wait()
        return self

    def run_server(self):
        self._server = ThreadedTCPServer((self.host, self.port), MediaHandler)
        #server = TCPServer()
        #ip, port = server.server_address
        #server.listen(PORT, HOST)
        #server.start(0)
        show('Listening at {0.host}:{0.port} (tcp)'.format(self))
        with self.cond:
            self.cond.notify_all()
        self._server.serve_forever()

    def stop(self):
        self._server.shutdown()
        print('Mobile server stopped')


if __name__ == "__main__":
    server = TCPServer()
    server.start()
