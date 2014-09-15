"""
    Reference implementation for sending data to the "mobile" part of DSS.

    Open video file/stream and send to 'mobile_streaming' the same way
    it is implemented on an Android system.

    Requires FFmpeg (with libx264 libfdk_aac).
    Might use FFprobe to send metadata

"""
import sys
import re
import socket
import time
import tempfile
import queue
import pymongo
from os.path import join

try:
    import _python_base
except ImportError:
    from . import _python_base

from dss import storage
from dss.config import config
from dss.tools import ffmpeg, process, thread
from dss.mobile.handler import MediaHandler
from dss.mobile.enum import DataContent, ContentType
from dss.mobile.processing.data import DataProc


class Watcher(thread.Thread):
    status = False

    def __init__(self, cmd, *args, **kw):
        super(Watcher, self).__init__(*args, **kw)
        self.cmd = cmd
        self.proc = None
        self.cond = thread.Condition()

    def run(self):
        self.status = True
        self.name = 'Process Watcher'
        try:
            self.watch_proc()
        except Exception:
            self.status = False
            raise

    def watch_proc(self):
        with process.Popen(self.cmd, stderr=process.PIPE,
                           universal_newlines=True) as self.proc:
            while self.proc.poll() is None:
                line = self.proc.stderr.readline().rstrip()
                content = None
                try:
                    data = re.findall(r'(\w+)=\s*(\S+)\s', line)
                    if len(data) > 2:
                        content = dict(data)
                except ValueError:
                    pass
                # TODO: use `content` to show percentage of processing.

        with self.cond:
            self.cond.notify_all()

        print('Input video has finished.')

    def stop(self):
        try:
            self.proc.kill()
        except Exception:
            pass
        self.join()


class MockMediaHandler(MediaHandler):
    def __init__(self, socket):
        self.request = socket
        self.setup()


class Sender(thread.Thread):

    def __init__(self, addr, *args, **kw):
        super(Sender, self).__init__(*args, **kw)
        self.queue = queue.Queue()
        self.running = False
        self.socket = None
        self.handler = None
        self.addr = addr
        self.cond = thread.Condition()

    def run(self):
        self.running = True
        self.socket = socket.socket()
        self.socket.connect(self.addr)
        self.handler = MockMediaHandler(self.socket)
        while self.running:
            data = self.queue.get()
            if data is None:
                break
            type, data, kw = data
            self.handler.write_data(type, data, **kw)

            with self.cond:
                self.cond.notify_all()

    def insert(self, type, value, **kw):
        self.queue.put((type, value, kw))

    def stop(self):
        self.running = False
        self.queue.empty()
        self.queue.put(None)
        self.join()


def read_loop(video_file, audio_file, sender, watcher):
    with open(video_file, 'rb') as fv, open(audio_file, 'rb') as fa:
        while watcher.status:
            v = fv.read()
            if v:
                sender.insert(DataContent.video, v)
            a = fa.read()
            if a:
                sender.insert(DataContent.audio, a)


def main():
    client = pymongo.MongoClient()
    database_name = 'dss_script'
    collection_name = 'mobile_send'
    db = storage.KeyValueStorage(collection_name, client[database_name])

    try:
        file = sys.argv[1]
    except IndexError:
        print('Missing file/stream name as first argument.')
        print('Usage:\n\t', './mobile_send', 'FILE_NAME', '[SERVER_IP_ADDRESS]')
        sys.exit(-1)

    try:
        addr = sys.argv[2]
    except IndexError:
        addr = None

    tmp = tempfile.mkdtemp()
    video_file = join(tmp, 'video.ts')
    audio_file = join(tmp, 'audio.ts')

    cmd = ffmpeg.cmd_outputs(
        '-re', file, '-f mpegts',
        ['-an -c:v libx264', '-vn -c:a libfdk_aac'],
        [video_file, audio_file],
        add_probe=False,
    )
    #print(' '.join(cmd))

    if addr is None:
        addr = config['local']['addr']
    port = config.getint('local', 'tcp_port')

    sender = Sender((addr, port)).start()
    watcher = Watcher(cmd).start()
    try:
        stream_id = db.stream_id
    except AttributeError:
        stream_id = ''

    sender.insert(ContentType.meta, {'id': stream_id}, as_metadata=True)
    with sender.cond:
        sender.cond.wait()
    type, data = sender.handler.read_data()
    type, data = DataProc.decode_data(data)
    if 'id' in data:
        db.stream_id = data['id']

    print('Transmission started')
    print('ID:', db.stream_id)
    time.sleep(2)

    try:
        # Run loop on other thread because it will block!
        _ = thread.Thread(
            read_loop,
            args=(audio_file, video_file, sender, watcher)
        ).start()

        with watcher.cond:
            watcher.cond.wait()
    except KeyboardInterrupt:
        watcher.stop()
        sender.stop()

    print('Exiting...')


if __name__ == '__main__':
    main()
