import tornado.web
from tornado import template

from dss.config import template_dir, config

loader = template.Loader(template_dir)


def js_bool(var):
    return ('false', 'true')[bool(var)]


class ViewHandler(tornado.web.RequestHandler):

    def get(self):
        lat, long = config.get_list('web', 'map.position')
        options = {
            'latitude': lat,
            'longitude': long,
            'zoomlevel': config.getint('web', 'map.zoom'),
            'traffic_layer': js_bool(
                config.getboolean('web', 'map.traffic_layer'))
        }

        view = loader.load('map.html').generate(**options)
        self.finish(view)