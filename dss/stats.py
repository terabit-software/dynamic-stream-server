import collections
import time
import makeobj
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


class StatusTiming(makeobj.Obj):
    STOPPED, STARTED, ON, DIED = makeobj.keys(4)


class TimedStats(Stats):
    MAX_WARMUP_COUNT = 10

    def __init__(self, total=0, uptime=0, warmup_count=10):
        self._measure = None
        self._total = None
        super(TimedStats, self).__init__(total, uptime)

        self.death_count = 0
        self._warmup = collections.deque(maxlen=warmup_count)
        self._last_start = None
        self._last_shutdown = None
        self._status = StatusTiming.STOPPED

    @thread.lock_method
    def started(self, value=None):
        if self._status is StatusTiming.STOPPED:
            self._status = StatusTiming.STARTED

        if value is None:
            value = time.time()
        self._last_start = value

    @thread.lock_method
    def warmup(self, value=None):
        if value is None:
            value = time.time()

        elapsed = value - self._last_start

        # Now _last_start will record the time from
        # publication start instead of process start
        self._last_start = value

        self._warmup.append(elapsed)
        self._total += elapsed  # Warmup time does count as downtime

        if self._status is StatusTiming.DIED:
            self.downtime()

        self._status = StatusTiming.ON

    @thread.lock_method
    def uptime(self, value=None):
        if value is None:
            value = time.time() - self._last_start

        if self._status is StatusTiming.ON:
            self._measure += value
        self._total += value
        self._status = StatusTiming.STOPPED

    @thread.lock_method
    def downtime(self, value=None):
        if value is None:
            value = time.time() - self._last_shutdown
            self._last_shutdown = None
        self._total += value

    @thread.lock_method
    def died(self):
        self.death_count += 1
        if self._last_shutdown is None:
            # Otherwise, the stream is crashing non-stop
            # So it should keep the original time for correct
            # uptime calculation.
            self._last_shutdown = time.time()
        self._status = StatusTiming.DIED

    @thread.lock_method
    def warmup_mean(self):
        if self._warmup:
            return sum(self._warmup) / len(self._warmup)
        return 0

    @thread.lock_method
    def current_uptime(self):
        if self._status is StatusTiming.ON:
            return time.time() - self._last_start
        return 0

    @thread.lock_method
    def current_downtime(self):
        if self._status is StatusTiming.DIED:
            return time.time() - self._last_shutdown
        return 0

    @property
    @thread.lock_method
    def measure(self):
        return self._measure + self.current_uptime()

    @measure.setter
    @thread.lock_method
    def measure(self, value):
        self._measure = value

    @property
    @thread.lock_method
    def total(self):
        return self._total + self.current_uptime() + self.current_downtime()

    @total.setter
    @thread.lock_method
    def total(self, value):
        self._total = value


class StreamStats(object):
    def __init__(self):
        self.thumbnail = CountStats()
        self.timed = TimedStats()

    def metric(self, percent=True):
        mult = 100 if percent else 1
        return {
            'thumbnail': round(self.thumbnail.result() * mult, 3),
            'uptime': round(self.timed.result() * mult, 3),
            'crash': self.timed.death_count,
            'warmup': round(self.timed.warmup_mean(), 3),
            #'__degub__': {
            #    'measure': self.timed.measure,
            #    '_measure': self.timed._measure,
            #    'total': self.timed.total,
            #    '_total': self.timed._total,
            #    'current_uptime': self.timed.current_uptime(),
            #    'current_downtime': self.timed.current_downtime(),
            #    '_warmup': list(self.timed._warmup),
            #    'last_start': self.timed._last_start,
            #    'last_shutdown': self.timed._last_shutdown,
            #}
        }
