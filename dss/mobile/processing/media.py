import os
try:
    import Queue as queue
except ImportError:
    import queue

from dss.tools.os import pipe_nonblock_read, PIPE_SIZE
from dss.tools import thread, show
from ..const import WAIT_TIMEOUT, DEFAULT_PIPE_SIZE


class Media(thread.Thread):
    # If it takes too long to retrieve data from queue,
    timeout = WAIT_TIMEOUT

    # If the queue gets too big, there is a problem with the transcoding
    # process consuming it. The process should end.
    # With preliminary tests on 4K video, the queue can grow much bigger than 50.
    # Optimally, this shold be based on video bitrate
    queue_limit = 50000

    def __init__(self, pipe, parent, name=None, queue_limit=None):
        super(Media, self).__init__(name=name)
        self.pipe = pipe
        self.parent = parent
        self._run = True
        if queue_limit is not None:
            self.queue_limit = queue_limit
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
        pipe_nonblock_read(self.pipe)
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