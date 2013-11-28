import tornado.web
import json
from .. import video
from .. import providers


class StreamStatsHandler(tornado.web.RequestHandler):
    """ Send stream stats for the user per stream or per provider.
        Usage:
            /stats/{id}/[{field1}[,{field2}...]]
        Examples:
            /stats/C/
            /stats/C123/
            /stats/C123/thumbnail
            /stats/C/thumbnail,video,other_field

        The "id" is either the provider identifier (non-digits) or a full
        stream identifier. If just the provider is selected, all its streams
        will be shown.

        The last part of the URI is an optional comma separated list of all
        fields the user wants to receive. If only one stream and one field
        are selected, all information but the exactly item requested will
        be stripped of the response.

        Otherwise, the output is a list of (for provider selection) or a
        single dictionary of stat information. The information includes the
        camera "id" it belongs:
            [{"id": "C0", "foo": 1, "bar": 2},
             {"id": "C1", "foo": 9, "bar": 0}]
    """

    def get(self, id, metric=None, *args, **kw):
        stream = provider = None
        use_percentage = int(self.get_argument('percent', True))

        try:
            stream = video.Video.get_stream(id)
        except KeyError:
            try:
                provider = providers.Providers.select(id)
            except KeyError:
                self.set_status(404)
                return

        if provider:
            streams = [video.Video.get_stream(s) for s in provider.streams()]
        else:
            streams = [stream]

        data = []
        for s in streams:
            content = s.stats.metric(percent=use_percentage)
            content['id'] = s.id
            data.append(content)

        original_metric = []
        if metric:
            original_metric = [x for x in metric.split(',') if x]
            metric = set(original_metric + ['id'])
            try:
                data = [dict((m, d[m]) for m in metric) for d in data]
            except KeyError:
                self.set_status(404)
                return

        if not provider:
            data = data[0]
            if len(original_metric) == 1:
                if original_metric[0] != 'id':
                    data.pop('id', None)
                data = next(iter(data.values()))

        self.set_header('Content-Type', 'application/json')
        self.finish(json.dumps(data))

    post = get
