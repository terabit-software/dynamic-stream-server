import tornado.web
import json

from .. import providers


class InfoHandler(tornado.web.RequestHandler):

    def get(self, opt, id=None, **kw):
        data = None

        if opt == 'provider':
            providers_ = providers.Providers.enabled()

            if not id:
                data = [
                    {'name': p.name, 'id': k}
                    for k, p in providers_.items()
                ]
            else:
                try:
                    data = list(providers_[id].stream_data().values())
                except KeyError:
                    self.set_status(404)
                    return
        elif opt == 'stream':
            if not id:
                self.set_status(404)
                return
            data = providers.Providers.select(id).get_stream_data(id)

        self.set_header('Content-Type', 'application/json')
        self.finish(json.dumps(data))

    post = get
