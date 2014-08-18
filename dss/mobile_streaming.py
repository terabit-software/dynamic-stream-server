#!/usr/bin/env python
import os
import json
import struct
import tempfile
import shutil
import queue
import datetime
import traceback
import makeobj
import time

try:
    import socketserver
except ImportError:
    import SocketServer as socketserver

try:
    import fcntl
except ImportError:
    fcntl = None

if __name__ == '__main__':
    # Running standalone
    import sys
    _root = os.path.dirname(os.path.dirname(__file__))
    sys.path.insert(0, _root)

from dss.tools import buffer, thread, process, ffmpeg, show, Suppress
from dss.config import config
from dss.storage import db

rtmpconf = config['rtmp-server']
HEADER_SIZE = 5  # bytes
PIPE_SIZE = None
DEFAULT_PIPE_SIZE = 1024 * 1024
WAIT_TIMEOUT = 2


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
    # If it takes too long to retrieve data from queue,
    timeout = WAIT_TIMEOUT

    # If the queue gets too big, there is a problem with the transcoding
    # process consuming it. The process should end.
    queue_limit = 50

    def __init__(self, pipe, parent, name=None):
        super(Media, self).__init__(name=name)
        self.pipe = pipe
        self.parent = parent
        self._run = True
        self.queue = queue.Queue(self.queue_limit)
        self.lock = thread.RLock()
        self.write_lock = thread.Lock()
        self.daemon = False
        self.error = None

    def run(self):
        while True:
            with self.lock:
                if not self._run:
                    break
            try:
                data = self.queue.get(timeout=self.timeout)
            except queue.Empty as e:
                self.set_error(e)
                show('Low Bandwidth:', self.name)
                break
            if data is None:
                break

            with self.write_lock:
                os.write(self.pipe, data)

    def stop(self):
        with self.lock:
            self._run = False
        self.queue.empty()
        self.release_pipe()
        self.queue.put(None)
        self.join()
        os.close(self.pipe)

    def set_error(self, error):
        with self.lock:
            self.error = error
            self.parent.error = error
            self._run = False

    def add_data(self, data):
        try:
            self.queue.put_nowait(data)
        except queue.Full as e:
            self.set_error(e)
            raise

    def release_pipe(self):
        # Set the pipe non blocking for reading
        fcntl.fcntl(self.pipe, fcntl.F_SETFL, os.O_NONBLOCK)
        read_size = 0
        while not self.write_lock.acquire(blocking=False):
            # If acquiring is not possible, the pipe is still blocked
            try:
                read = os.read(self.pipe, PIPE_SIZE or DEFAULT_PIPE_SIZE)
                read_size += len(read)
            except IOError:
                break
        else:
            self.write_lock.release()
        show('Read {0} bytes from {1!r} pipe'.format(read_size, self.name))
        return read_size


class DataProc(thread.Thread):
    def __init__(self, parent):
        super(DataProc, self).__init__()
        self.name = 'data'
        self.parent = parent
        self.queue = parent.data_queue
        self.latest_position = None

    def run(self):
        try:
            self.handle_data()
        except BaseException as e:
            self.parent.error = e
            show('Data processing error:', repr(e))

    def handle_data(self):
        while True:
            data = self.queue.get()
            if data is None:
                # TODO Maybe run some cleanup here
                break
            type, payload = data
            data = json.loads(payload.decode())
            content = data['content']
            action = data['type']

            if type is DataContent.userdata:
                fn = getattr(self, '_handle_' + action, None)
                if fn is None:
                    show('Warning: action not found for user content of type', repr(action))
                else:
                    fn(content)

            elif type is DataContent.metadata:
                # TODO Handle metadata
                show('Metadata:', repr(data))

    def _handle_coord(self, data):
        obj = {'time': datetime.datetime.utcnow(),
               'coord': [data['latitude'], data['longitude']]}
        self.latest_position = obj
        db.mobile.update({'_id': self.parent._id},
                         {'$push': {'position': obj}})
        show('Stream: {0} | {1} | {2}'.format(
            self.parent._id, obj['time'], obj['coord'])
        )

    def stop(self):
        self.queue.empty()
        self.queue.put(None)
        self.join()


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

    provider_prefix = 'M'
    _handlers = set()
    _handlers_lock = thread.Lock()

    def setup(self):
        self._id = None
        self.run = True
        self.buffer = None
        self.proc = None
        self.video = None
        self.audio = None
        self.destination_url = None
        self.data_processing = None
        self.data_queue = queue.Queue()
        self.tmpdir = tempfile.mkdtemp()
        self._error = []
        self.__cleanup_executed = False

    def add_handler(self):
        with self._handlers_lock:
            self._handlers.add(self)

    def remove_handler(self):
        with self._handlers_lock:
            self._handlers.remove(self)

    @property
    def error(self):
        return self._error

    @error.setter
    def error(self, value):
        self._error.append(value)

    @classmethod
    def wait_handlers(cls):
        while cls._handlers:
            time.sleep(0.1)

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

        s = Suppress(Exception)

        # Stop all threads
        with s: self.audio.stop()
        with s: self.video.stop()
        with s: self.data_processing.stop()

        # Remove entry from database
        if self._id:
            db.mobile.update({'_id': self._id}, {'$set': {'active': False}})

        # Remove temp directory and thumbnail
        with s: shutil.rmtree(self.tmpdir)

        self.__cleanup_executed = True
        if s.errors:
            show('Errors during cleanup:', *s.errors, sep='\n', end='\n\n')
        show('Mobile stream "{0}" has ended'.format(self._id))

    def finish(self):
        try:
            self.cleanup()
        except Exception as e:
            show('Exception while cleaning:', repr(e))
        finally:
            self.remove_handler()

    def handle(self):
        try:
            self._handle()
        except BaseException:
            show(traceback.format_exc())
            raise

    def _handle(self):
        self.request.settimeout(WAIT_TIMEOUT)
        self.add_handler()
        self.buffer = buffer.Buffer(self.request)
        self._id = db.mobile.insert({'start': datetime.datetime.utcnow(),
                                     'active': True})
        self.destination_url = os.path.join(
            rtmpconf['addr'], rtmpconf['app'], self._get_stream_name()
        )
        show('New mobile stream:', self.destination_url)

        audio_filename = self.file('audio.aac')
        video_filename = self.file('video.ts')
        try:
            os.mkfifo(audio_filename)
            os.mkfifo(video_filename)
        except OSError as e:
            show('Failed to create FIFO:', e)
            return

        audio_pipe = os.open(audio_filename, os.O_RDWR)
        video_pipe = os.open(video_filename, os.O_RDWR)
        set_pipe_max_size(audio_pipe, video_pipe)

        self.audio = Media(audio_pipe, self, 'audio').start()
        self.video = Media(video_pipe, self, 'video').start()
        self.data_processing = DataProc(self).start()

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
            while self.server.is_running \
                    and not self.error \
                    and self.proc.poll() is None:
                try:
                    type, payload = self.read_data()
                except Exception:
                    show('Timeout')
                    break

                if not self.run or type is None:
                    break
                try:
                    self.handle_content(type, payload)
                except Exception as e:
                    show('Content handling error:', repr(e))
                    break

            try:
                self.proc.kill()
                self.proc.wait()
            except Exception as e:
                show('Proc exit error:', repr(e))

    def handle_content(self, type, payload):
        try:
            type = DataContent[type]
        except KeyError:
            show('Invalid header type "%s"' % type)

        if type in (DataContent.metadata, DataContent.userdata):
            self.data_queue.put((type, payload))
        elif type is DataContent.video:
            self.video.add_data(payload)
        elif type is DataContent.audio:
            self.audio.add_data(payload)
        else:
            show('Unknown content received: ' +
                 'Type: {0}, Payload: {1!r}'.format(type, payload))

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

    def _get_stream_name(self):
        # TODO change this | Already changed? remove message only?
        return self.provider_prefix + '-' + str(self._id)


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    is_running = False


class TCPServer(object):

    def __init__(self):
        self.host = config.get('local', 'addr')
        self.port = config.getint('local', 'tcp_port')
        self.cond = thread.Condition()
        self._server = None

    def start(self, create_thread=True):
        if not create_thread:
            self.run_server()
            return

        with self.cond:
            thread.Thread(self.run_server, name='TCP Server').start()
            self.cond.wait()
        return self

    def run_server(self):
        self._server = ThreadedTCPServer((self.host, self.port), MediaHandler)
        show('Listening at {0.host}:{0.port} (tcp)'.format(self))
        with self.cond:
            self.cond.notify_all()
        self._server.is_running = True
        self._server.serve_forever()

    def stop(self):
        self._server.is_running = False
        self._server.shutdown()


if __name__ == "__main__":
    server = TCPServer()
    try:
        server.start(False)
    except KeyboardInterrupt:
        server.stop()
        MediaHandler.wait_handlers()
