from .tools import thread


class StreamStats(object):
    class Stats(object):
        def __init__(self, total=0, error_count=0):
            self._total = total
            self._count = error_count
            self._lock = thread.Lock()

        def inc(self, error):
            with self._lock:
                self._total += 1
                if error:
                    self._count += 1

        def error(self):
            try:
                return self._count / self._total
            except ZeroDivisionError:
                return 0.

        def ok(self):
            return 1 - self.error()

    class TimeStats(Stats):
        pass

    def __init__(self):
        self.thumbnail = self.Stats()

    def metric(self):
        # TODO: add other metrics
        return {
            'thumbnail': self.thumbnail.ok() * 100,
        }
