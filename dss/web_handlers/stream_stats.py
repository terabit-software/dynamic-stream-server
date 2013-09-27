import tornado.web
import json
from .. import video


class StreamStatsHandler(tornado.web.RequestHandler):

    def get(self, id, metric=None, *args, **kw):
        try:
            stream = video.Video.get_stream(id)
        except KeyError:
            self.set_status(404)
            return

        data = stream.stats.metric()
        if metric:
            try:
                data = data[metric]
            except KeyError:
                self.set_status(404)
                return

        self.set_header('Content-Type', 'application/json')
        self.finish(json.dumps(data))

    post = get
