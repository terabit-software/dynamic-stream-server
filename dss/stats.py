from .tools import thread


class Stats(thread.LockedObject):
    __locked_properties__ = ('total', 'measures')

    def __init__(self, total=0, measure=0):
        super(Stats, self).__init__()
        self.total = total
        self.measure = measure

    def result(self):
        """ The element being measured divided by the total of occurrences.
            This should always be a value between 0 and 1 (inclusive).
        """
        try:
            return self.measure / self.total
        except ZeroDivisionError:
            return 0.


class CountStats(Stats):
    __locked_properties__ = ('count',)

    def __init__(self, total=0, error_count=0):
        super(CountStats, self).__init__(total)
        self.count = error_count

    @property
    def measure(self):
        return self.total - self._count

    @measure.setter
    def measure(self, value):
        return

    def inc(self, error):
        self.total += 1
        if error:
            self.count += 1


class StreamStats(object):
    def __init__(self):
        self.thumbnail = CountStats()

    def metric(self, percent=True):
        mult = 100 if percent else 1
        return {
            'thumbnail': self.thumbnail.result() * mult,
        }
