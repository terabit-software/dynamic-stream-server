import re
import time
import os
from concurrent import futures

from .config import config
from .tools import show, thread, process, ffmpeg
from .providers import Providers
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
    delete_after = _thumb.getint('delete_after')

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

                if cls.run:  # Show stats
                    cams = len(cls.stream_list)
                    show('Finished fetching thumbnails: {0}/{1}'.format(cams - len(error), cams))
                    if error:
                        show('Could not fetch:\n' + ', '.join(error))

                error = set(error)
                for s in cls.stream_list: # Record stats
                    Video.get_stream(s).stats.thumbnail.inc(s in error)

            if cls.run:
                # Do not start delete routine if the program was requested
                # to stop otherwise it may delete inconsistently data from
                # other runs.
                # It may seem as a desirable behavior to delete old data,
                # but this should be done at the program start.
                cls.delete_old_thumbnails(error)

            with cls.lock:
                t = time.time() - t
                interval = cls.interval - t

                cls.clean = True
                cls.lock.notify_all()

                if interval >= 0:
                    cls.lock.wait(interval)
                elif cls.run:
                    show('Thumbnail round delayed by {0:.2f} seconds'.format(-interval))

    @classmethod
    def make_file_names(cls, id, resize_information=False):
        sizes = re.findall(r'(\w+):(\w+)', cls._thumb['sizes'])
        names = [''] + ['-' + s[0] for s in sizes]

        outputs = [
            os.path.join(
                cls._thumb['dir'],
                '{0}{1}.{2}'.format(id, _name, cls._thumb['format'])
            )
            for _name in names
        ]

        if resize_information:
            return outputs, sizes
        return outputs

    @classmethod
    def make_cmd(cls, name, source, seek=None, origin=None):
        """ Generate FFmpeg command for thumbnail generation.
        """
        thumb = cls._thumb
        out_opt = thumb['output_opt']
        if seek is not None:
            out_opt += ' -ss ' + str(seek)

        # If fetching thumbnail from origin server, will need the stream
        # id that is different from stream name.
        id = name
        if origin:
            id = origin.get_id(name)

        outputs, sizes = cls.make_file_names(id, resize_information=True)

        resize_opt = cls._thumb['resize_opt']
        resize = [''] + [resize_opt.format(s[1]) for s in sizes]

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

    @classmethod
    def delete_old_thumbnails(cls, thumbs):
        """ From a list of thumbnails ids, check which files are older than
            delete_after and remove them.
            If delete_after is zero, skip the check.
        """
        if not cls.delete_after:
            return

        deleted = []

        for id in thumbs:
            names = cls.make_file_names(id)
            try:
                modified_time = os.path.getmtime(names[0])
            except OSError:
                continue
            if time.time() - modified_time > cls.delete_after:
                for name in names:
                    try:
                        os.remove(name)
                    except OSError:
                        pass
                deleted.append(id)

        if deleted:
            show('Old thumbnails removed:\n', ', '.join(deleted))

        return deleted
