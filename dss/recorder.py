import os
import time
import datetime
from os.path import join, splitext, dirname
try:
    from urllib import urlencode
    from urllib2 import urlopen
except ImportError:
    from urllib.parse import urlencode
    from urllib.request import urlopen

from .tools import thread
from .tools.show import Show
from .config import config

show = Show('Recorder')

# Template
# http://server.com/rtmp_control/record/start|stop?srv=SRV&app=APP&name=NAME&rec=REC

server = config['http-server']
rec_conf = config['recorder']


class StreamRecorder(thread.Thread):

    workers = rec_conf.getint('workers')
    recorders = rec_conf.get_list('recorders')
    interval = rec_conf.getint('interval')
    format = rec_conf['format']
    url = join(server['addr'], server['control_url'], 'record')

    def __init__(self, provider, interval=None, format=None):
        super(StreamRecorder, self).__init__()
        self.provider = provider
        if interval is not None:
            self.interval = interval
        if format is not None:
            self.format = format
        self.current_time = None
        self.is_running = False
        self.cond = thread.Condition()

    def sleep(self):
        now = time.time()
        t = self.interval - now % self.interval
        with self.cond:
            self.cond.wait(t)
        return time.time()

    def split_records(self, start=True):
        self.current_time = datetime.datetime.now().strftime(self.format)
        try:
            for stream in self.provider.streams():
                self.split_one(stream, start)
            # TODO open workers? to `split_one` for each stream
            # Maybe let all http fetches to be async call
        finally:
            # Invert records order for start/stop logic
            self.recorders = self.recorders[::-1]
        show('Recorder:', self.current_time)

    def split_one(self, id, start):
        rec = self.recorders
        if len(rec) == 1:
            self.stop_recorder(id, rec[0])
            if start:
                self.start_recorder(id, rec[0])
        else:
            if start:
                self.start_recorder(id, rec[1])
            self.stop_recorder(id, rec[0])

    def build_url(self, action, id, rec):
        query = {
            'app': config['rtmp-server']['app'],
            'name': id,
            'rec': rec,
        }
        return join(self.url, action) + '?' + urlencode(query)

    def start_recorder(self, id, rec):
        url = self.build_url('start', id, rec)
        file_name = urlopen(url).read().decode('utf-8')
        return file_name

    def stop_recorder(self, id, rec):
        url = self.build_url('stop', id, rec)
        file_name = urlopen(url).read().decode('utf-8')
        if not file_name:
            return

        name = join(dirname(file_name),
                    id + '-' + self.current_time + splitext(file_name)[-1])
        os.rename(file_name, name)
        return name

    def run(self):
        self.is_running = True

        if not self.recorders:
            raise RuntimeError('No recorder configured!')

        while self.is_running:
            self.split_records()
            self.sleep()

        self.split_records(start=False)

    def stop(self):
        self.is_running = False
        with self.cond:
            self.cond.notify_all()
        self.join()