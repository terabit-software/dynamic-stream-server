try:
    import Queue as queue
except ImportError:
    import queue

from .tools import thread


PING_INTERVAL = 15  # seconds


class WebsocketBroadcast(thread.Thread):
    _instances = {}

    def __init__(self, cls):
        """ `cls` must be a class providing a list/set of
            connected websocket clients (cls.clients) and
            a lock to access said list (cls.lock).

            All clients must be `tornado.websocket.WebSocketHandler`
            instances.
        """
        super(WebsocketBroadcast, self).__init__()
        self.name = type(self).__name__ + '(%s)' % cls.__name__
        self.queue = queue.Queue()
        self.running = False
        self.cls = cls
        self.ping_timer = thread.IntervalTimer(PING_INTERVAL, self.ping)

    def clients(self):
        with self.cls.lock:
            return list(self.cls.clients)

    def ping(self):
        for client in self.clients():
            try:
                client.ping(bytes())
            except Exception as e:
                print(e)

    def add_message(self, message):
        self.queue.put(message)

    def run(self):
        self.running = True
        self.ping_timer.start()
        while self.running:
            message = self.queue.get()
            if message is None:
                break

            for client in self.clients():
                client.write_message(message)

    def stop(self):
        self.running = False
        self.ping_timer.cancel()
        self.queue.empty()
        self.queue.put(None)
        self.join()

    @classmethod
    def register(cls, key, class_):
        if cls._instances.get(key) is not None:
            raise KeyError('Key already registered: {0!r}'.format(key))
        instance = cls(class_)
        cls._instances[key] = instance
        return instance

    @classmethod
    def select(cls, name):
        return cls._instances[name]
