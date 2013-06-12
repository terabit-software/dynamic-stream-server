import re
import time
import os
from concurrent import futures

from .config import config
from .tools import thread, process, ffmpeg
from .streams import Providers
from .video import Video


class Thumbnail(object):
    run = True
    clean = True
    lock = thread.Condition()

    stream_list = None
    _thumb = config['thumbnail']
    interval = _thumb.getint('interval')
    workers = _thumb.getint('workers')
    timeout = _thumb.getint('timeout')

    class Worker(object):
        def __init__(self, id, timeout):
            self.id = id
            self.timeout = timeout
            self.proc = None
            self.lock = None

        def _open_proc(self):
            """ Select stream and open process
            """
            provider = Providers.select(self.id)
            source = provider.in_stream
            seek = None
            origin = None
            id = self.id

            # Use local connection if stream is already running.
            # The provider can choose not use the local connection.
            if provider.thumbnail_local and Video.get_stream(self.id).alive:
                source = provider.out_stream
                seek = 1
            else:
                # If using remote server identifier instead of local.
                id = provider.get_stream(self.id)
                origin = provider

            return process.run_proc(
                self.id,
                Thumbnail.make_cmd(id, source, seek, origin),
                'thumb',
            )

        def _close_proc(self):
            """ Kill the open process.
            """
            if self.proc.poll() is not None:
                return
            try:
                self.proc.kill()
                self.proc.wait()
            except OSError:
                pass

        def _waiter(self):
            """ Wait until the first of these events :
                    - Process finished;
                    - Timeout (on another thread);
                    - User request for termination (at the same thread as
                      the timeout).
            """
            with self.lock:
                thread.Condition.wait_for_any(
                    [Thumbnail.lock, self.lock], self.timeout
                )
                self._close_proc()

        def __call__(self):
            """ Opens a new process and sets a waiter with timeout on
                another thread.
                Waits for the end of the process (naturally or killed
                by waiter). Awakes the waiter if process finished first.
                Returns the process output code.
            """
            self.lock = thread.Condition.from_condition(Thumbnail.lock)
            with self.lock:
                if not Thumbnail.run:
                    return

            with self._open_proc() as self.proc:
                thread.Thread(self._waiter).start()

                self.proc.communicate()
                with self.lock:
                    self.lock.notify_all()

                return self.proc.poll()

    @classmethod
    def main_worker(cls):
        stream_list = [p.streams() for p in Providers.values()]
        cls.stream_list = [item for sublist in stream_list for item in sublist]

        try:
            delay = cls._thumb.getint('start_after')
        except Exception:
            delay = 0
        with cls.lock:
            cls.lock.wait(delay)

        while True:
            with cls.lock:
                if not cls.run:
                    break
                cls.clean = False
            t = time.time()
            with futures.ThreadPoolExecutor(cls.workers) as executor:
                map = dict(
                    (executor.submit(cls.Worker(x, cls.timeout)), x)
                        for x in cls.stream_list
                )
                done = {}
                for future in futures.as_completed(map):
                    done[map[future]] = future.result()
                error = [x for x in cls.stream_list if done[x] != 0]

                if cls.run: # Show stats
                    cams = len(cls.stream_list)
                    print('Finished fetching thumbnails: {0}/{1}'.format(cams - len(error), cams))
                    if error:
                        print('Could not fetch:\n' + ', '.join(error))

            t = time.time() - t
            interval = cls.interval - t
            with cls.lock:
                cls.clean = True
                cls.lock.notify_all()

                if interval >= 0:
                    cls.lock.wait(interval)
                elif cls.run:
                    print('Thumbnail round delayed by {0:.2f} seconds'.format(-interval))


    @classmethod
    def make_cmd(cls, name, source, seek=None, origin=None):
        """ Generate FFmpeg command for thumbnail generation.
        """
        thumb = cls._thumb
        out_opt = thumb['output_opt']
        if seek is not None:
            out_opt += ' -ss ' + str(seek)

        resize_opt = thumb['resize_opt']
        sizes = re.findall(r'(\w+):(\w+)', thumb['sizes'])

        resize = [''] + [resize_opt.format(s[1]) for s in sizes]
        names = [''] + ['-' + s[0] for s in sizes]

        # If fetching thumbnail from origin server, will need the stream
        # id that is different from stream name.
        id = name
        if origin:
            id = origin.get_id(name)

        outputs = [
        os.path.join(
            thumb['dir'],
            '{0}{1}.{2}'.format(id, _name, thumb['format'])
        )
        for _name in names
        ]

        return ffmpeg.cmd_outputs(
            thumb['input_opt'],
            source.format(name),
            out_opt,
            resize,
            outputs
        )

    @classmethod
    def start_download(cls):
        thread.Thread(cls.main_worker).start()

    @classmethod
    def stop_download(cls):
        with cls.lock:
            cls.run = False
            cls.lock.notify_all()
            while not cls.clean:
                cls.lock.wait()
