import tornado.ioloop


class TornadoManager(object):

    def __init__(self):
        self.instance = tornado.ioloop.IOLoop.instance()

    def start(self):
        self.instance.start()

    def stop(self):
        self.instance.stop()