import os
import sys

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from ..config import config, dirname
from .. import loader
from . import stream_provider


def load(cls_name, conf):
        """ Create provider based on configuration file.
            This file (parsed with `.config.Parser`), must have
            at least the sections "base" and "streams".

                [base]
                access = url://someurl/to/be/used/{0}.stream
                identifier = X
                input_opt = -ffmpeg -input -cmd
                output_opt = -ffmpeg -output -cmd
                thumbnail_local = true  # optional

                [streams]
                mode = lazy, download, cache, file, list, named, db
                url = http://url-for-download-mode.com
                parser = module.function  # This function must generate
                                          # json-serializable data if cache
                                          # is enabled
                db = collection_name
                file = local_file_to_load.json
                list =
                    ID1 GEO1 DESCRIPITION1   # if "named", the ID is the name
                    ID2 GEO2 DESCRIPITION2   # used to fetch the stream with
                                             # the access url

                [record]  # all optional
                enable = yes       # default is "yes" if record section is defined
                format = %H:%M:%S  # strftime format for file name
                interval = 45      # seconds for each file

            The mode list is how the streams will be provided.
        """

        strm = conf['streams']
        mode = set(strm.get_split('mode'))

        cls_ = stream_provider.BaseStreamProvider
        if 'named' in mode:
            cls_ = stream_provider.NamedStreamProvider

        attr = {
            'mode': mode,
            'dynamic': 'dynamic' in mode
        }

        if 'list' in mode:
            def fetch_function():
                keys = strm.get_list('keys')
                values = strm.get_multiline_list('list')
                ret = OrderedDict([
                    (v[0], dict(zip(keys, v)))
                    for v in values
                ])
                return ret
        else:
            fetch = []
            url = None
            parser = None
            name = None
            db_name = None
            if 'download' in mode:
                fetch.append(loader.Place.url)
                url = strm['url']
                parser = loader.load_object(strm['parser'], 'dss.providers_data')
            if 'cache' in mode:
                fetch.append(loader.Place.cache)
                name = strm.get('file', cls_name + '-streams.json')
            if 'file' in mode:
                fetch.append(loader.Place.file)
                join = os.path.join
                name = join(join(dirname, 'providers_data'), strm['file'])
            if 'db' in mode:
                fetch.append(loader.Place.db)
                db_name = strm['db']

            def fetch_function():
                streams = loader.get_streams(
                    name, url, parser, db_name,
                    is_dynamic=attr['dynamic'],
                    places=fetch
                )
                return OrderedDict((x['id'], x) for x in streams)

        if 'lazy' in mode:
            attr['lazy_initialization'] = classmethod(lambda cls: fetch_function())
            attr['_stream_list'] = None
            attr['_stream_data'] = None
        else:
            stream_data = fetch_function()
            attr['_stream_data'] = stream_data
            attr['_stream_list'] = list(stream_data)

        confb = conf['base']
        attr.update(
            name = cls_name,
            identifier = confb['identifier'],
            in_stream = confb['access'],
            thumbnail_local = confb.getboolean('thumbnail_local', fallback=True),
            conf = confb,
            is_enabled = confb.getboolean(
                'enabled',
                fallback=config['providers'].getboolean('enabled')
            ),
        )

        if sys.version_info < (3, 0):
            # When configparser has an encoding set, all strings become
            # unicode and Py2k do not accept them as class name.
            cls_name = cls_name.encode('utf-8')

        provider = type(cls_name, (cls_,), attr)

        if 'lazy' not in mode:
            # Only chance to run this function if
            # initialization is not lazy
            provider.post_initialization()

        return provider