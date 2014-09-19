import json
import datetime

from dss.tools import thread
from dss.tools.show import Show
from dss.storage import db
from dss.websocket import WebsocketBroadcast
from ..enum import DataContent

show = Show('Mobile.Data')


class DataProc(thread.Thread):
    def __init__(self, parent):
        super(DataProc, self).__init__()
        self.name = 'data'
        self.parent = parent
        self.queue = parent.data_queue
        self.latest_position = None

    def run(self):
        try:
            self.handle_data()
        except BaseException as e:
            self.parent.error = e
            show('Data processing error:', repr(e))

    @classmethod
    def decode_data(cls, payload):
        data = json.loads(payload.decode())
        return data['type'], data['content']

    def handle_data(self):
        while True:
            data = self.queue.get()
            if data is None:
                break
            type, payload = data
            action, content = self.decode_data(payload)

            if type is DataContent.userdata:
                fn = getattr(self, '_handle_' + action, None)
                if fn is None:
                    show('Warning: action not found for user content of type', repr(action))
                else:
                    fn(content)

            elif type is DataContent.metadata:
                # TODO Handle metadata
                show('Metadata:', repr(data))

    def _handle_coord(self, data):

        obj = {'time': datetime.datetime.utcnow(),
               'coord': [data['latitude'], data['longitude']]}
        self.latest_position = obj
        db.mobile.update({'_id': self.parent._id},
                         {'$push': {'position': obj}})

        WebsocketBroadcast.select('mobile_location').cls.broadcast_message({
            'name': self.parent.get_stream_name(),
            'info': obj
        })

        show('Stream: {0} | {1} | {2}'.format(
            self.parent._id, obj['time'], obj['coord'])
        )

    def stop(self):
        self.queue.empty()
        self.queue.put(None)
        self.join()