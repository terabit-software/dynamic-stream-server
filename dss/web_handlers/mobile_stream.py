import tornado.websocket
from bson import json_util

from ..storage import db


class MobileStreamLocation(tornado.websocket.WebSocketHandler):
    def on_open(self, message):
        pass

    def on_message(self, message):
        streams = list(db.mobile.find({'active': True}))
        self.write_message(json_util.dumps({
            'request': 'all',
            'content': streams,
        }))

    def on_close(self):
        pass