import tornado.websocket
from bson import json_util

from dss.mobile import handler
from dss.tools import thread
from dss.storage import db
from dss.websocket import WebsocketBroadcast


class MobileStreamLocation(tornado.websocket.WebSocketHandler):
    lock = thread.RLock()
    clients = set()
    broadcaster = None

    def open(self):
        with self.lock:
            self.clients.add(self)

        MediaHandler = handler.MediaHandler
        streams = []
        for stream in db.mobile.find({'active': True}):
            stream['name'] = MediaHandler.stream_name(stream.pop('_id'))
            stream['position'] = stream['position'][-1] \
                if stream.get('position') else None
            streams.append(stream)

        self.write_message(json_util.dumps({
            'request': 'all',
            'content': streams,
        }))

    def on_message(self, message):
        pass

    def on_close(self):
        with self.lock:
            self.clients.remove(self)

    @classmethod
    def broadcast_message(cls, message, request='update'):
        if request is not None:
            message = {
                'request': request,
                'content': message,
            }
        cls.broadcaster.add_message(json_util.dumps(message))


# Register Broadcaster
MobileStreamLocation.broadcaster = \
    WebsocketBroadcast.register('mobile_location', MobileStreamLocation)