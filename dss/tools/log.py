""" Add logging capabilities to DSS
"""
import os
import datetime
import makeobj

from ..config import config
from . import thread

logdir = config['log']['dir']


class Levels(makeobj.Obj):
    debug = 0
    info = 1
    warn = 2
    error = 3
    max = 99


class Writer(object):

    def __init__(self, filename):
        self.filename = filename
        self._opened = False
        self.file = None
        self.lock = thread.Lock()
        self._format = '[{date}] [{owner}] {level.name}: {message}'

    def format(self, owner, level, message):
        now = datetime.datetime.now()
        return self._format.format(
            date=now,
            message=message,
            owner=owner or '',
            level=level,
        ) + '\n'

    def add(self, *args):
        # TODO Add to queue and write on another thread.
        with self.lock:
            self._write(*args)

    def _write(self, owner, level, message):
        text = self.format(owner, level, message)
        if not self._opened:
            self.file = open(os.path.join(logdir, self.filename), 'a')
            self._opened = True

        self.file.write(text)
        self.file.flush()

    def __del__(self):
        if self._opened:
            self.file.close()


class Log(object):
    _writers = {}

    def __init__(self, owner, filename):
        self.owner = owner
        self.writer = self._writers.get(filename)
        if self.writer is None:
            self.writer = Writer(filename)
            self._writers[filename] = self.writer

    def log(self, message, level=Levels.info):
        self.writer.add(self.owner, level, message)

    def __getattr__(self, name):
        level = Levels(name)

        def call(message):
            return self.log(message, level=level)

        return call
