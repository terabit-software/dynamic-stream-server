from .tools import thread


class Stats(thread.LockedObject):

    def __init__(self, total=0, measure=0):
        super(Stats, self).__init__()
        self.total = total
        self.measure = measure

    @thread.lock_method
    def result(self):
        """ The element being measured divided by the total of occurrences.
            This should always be a value between 0 and 1 (inclusive).
        """
        try:
            return self.measure / self.total
        except ZeroDivisionError:
            return 0.


class CountStats(Stats):

    def __init__(self, total=0, error_count=0):
        super(CountStats, self).__init__(total)
        self.count = error_count

    @property
    @thread.lock_method
    def measure(self):
        return self.total - self.count

    @measure.setter
    @thread.lock_method
    def measure(self, value):
        return  # XXX FIXME

    @thread.lock_method
    def inc(self, error):
        self.total += 1
        if error:
            self.count += 1


class TimedStats(Stats):

    def __init__(self, total=0, uptime=0):
        super(TimedStats, self).__init__(total, uptime)
        self.death_count = 0

    @thread.lock_method
    def uptime(self, value):
        self.measure += value
        self.total += value

    @thread.lock_method
    def downtime(self, value):
        self.total += value

    @thread.lock_method
    def died(self):
        self.death_count += 1


class StreamStats(object):
    def __init__(self):
        self.thumbnail = CountStats()
        self.timed = TimedStats()

    def metric(self, percent=True):
        mult = 100 if percent else 1
        return {
            'thumbnail': self.thumbnail.result() * mult,
            'time': self.timed.result() * mult,
            'crash': self.timed.death_count,
        }
