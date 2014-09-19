#!/usr/bin/env python
import os
import json
import struct
import tempfile
import shutil
import datetime
import traceback
import time
from bson.objectid import ObjectId

try:
    import Queue as queue
except ImportError:
    import queue

try:
    import SocketServer as socketserver
except ImportError:
    import socketserver


from dss.tools import buffer, thread, process, ffmpeg, Suppress
from dss.tools.os import set_pipe_max_size
from dss.tools.show import show
from dss.config import config
from dss.storage import db
from dss.websocket import WebsocketBroadcast

from .enum import ContentType, DataContent
from .const import WAIT_TIMEOUT, HEADER_SIZE
from .processing.media import Media
from .processing.data import DataProc


rtmpconf = config['rtmp-server']


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
    _time_limit = config.getint('mobile', 'time_limit')

    def setup(self):
        self._id = None
        self.run = True
        self.proc = None
        self.video = None
        self.audio = None
        self.destination_url = None
        self.data_processing = None
        self.thumbnail_path = None
        self.buffer = buffer.Buffer(self.request)
        self.data_queue = queue.Queue()
        self.tmpdir = tempfile.mkdtemp(dir=config['mobile']['dir'])
        self._timer_alarm = False
        self.timer = thread.Timer(self._time_limit, self.timer_alarm) \
            if self._time_limit else None
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

    def timer_alarm(self):
        self._timer_alarm = True

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

        # Stop timer if any
        if self.timer is not None:
            self.timer.cancel()

        # Stop all threads
        with s: self.audio.stop()
        with s: self.video.stop()
        with s: self.data_processing.stop()

        # Remove entry from database
        if self._id:
            db.mobile.update({'_id': self._id}, {'$set': {'active': False}})

        # Remove temp directory and thumbnail
        with s: shutil.rmtree(self.tmpdir)
        with s: os.remove(self.thumbnail_path)

        WebsocketBroadcast.select('mobile_location').cls.broadcast_message({
            'name': self.get_stream_name(),
            'info': 'finished'
        })

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
        db_data = {'start': datetime.datetime.utcnow(),
                   'active': True}

        # Read the first data block.
        # It should have complete metadata information with at least the
        # provided id, if it is known (or falsy value otherwise)
        typ, payload = self.read_data()
        typ = DataContent[typ]
        if typ is DataContent.metadata:
            action, payload = DataProc.decode_data(payload)
            try:
                self._id = ObjectId(payload['id'])
            except Exception:
                pass
        else:
            show('Received first data block of type {0.name!r}({0.value}).\n'
                 'Expected {1.name!r}({1.value})', typ, DataContent.metadata)
            return

        response = db.mobile.update({'_id': self._id}, db_data, upsert=True)
        self._id = response.get('upserted', self._id)
        self.send_data(ContentType.meta, {'id': str(self._id)})
        self.destination_url = os.path.join(
            rtmpconf['addr'], rtmpconf['app'], self.get_stream_name()
        )
        show('New mobile stream:', self.destination_url)

        audio_filename = self.file('audio.ts')
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

        thumb = config['thumbnail']
        self.thumbnail_path = os.path.join(
            thumb['dir'], self.get_stream_name()
        ) + '.' + thumb['format']

        thumb_rate = str(1 / int(thumb['mobile_interval']))

        args = ffmpeg.cmd_inputs_outputs(
            '-y -re', [audio_filename, video_filename], '',
            ['-c:v copy -c:a copy -bsf:a aac_adtstoasc -f flv',
             '-r ' + thumb_rate + ' -update 1 -an'],
            [self.destination_url, self.thumbnail_path]
        )

        # Start the timer for alarm
        if self.timer is not None:
            self.timer.start()

        with self.file('proc_output', 'w') as out:
            with self.file('proc_err', 'w') as err:
                self.handle_proc_loop(args, out, err)

    def handle_proc_loop(self, proc_args, stdout, stderr):
        """ Open transcoding process and read data from buffer
            until the client stops sending data.
        """
        with process.Popen(proc_args, stdout=stdout, stderr=stderr) as self.proc:
            while self.server.is_running \
                    and not self._timer_alarm \
                    and not self.error \
                    and self.proc.poll() is None:
                try:
                    type, payload = self.read_data()
                except Exception:
                    show('Timeout')
                    break

                if not self.run or type is None:
                    break

                self.handle_content(type, payload)

            if self._timer_alarm:
                show('Stream finished due to time limit: {0} seconds'.format(self._time_limit))

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

    @classmethod
    def build_metadata(cls, type, content):
        data = {'type': type.name, 'content': content}
        return json.dumps(data).encode('utf-8')

    def send_data(self, type, content):
        # Deprecated. Use write_data directly
        self.write_data(type, content, as_metadata=True)

    def write_data(self, data_type, data, as_metadata=False):
        if as_metadata:
            data = self.build_metadata(data_type, data)
            data_type = DataContent.metadata

        header = struct.pack('!BI', data_type.value, len(data))
        self.request.sendall(header + data)

    def get_stream_name(self):
        return self.stream_name(self._id)

    @classmethod
    def stream_name(cls, id):
        return cls.provider_prefix + '_' + str(id)
