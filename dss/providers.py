import glob
import os
import re
import sys

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from .config import Parser, config, dirname
from .tools import ffmpeg
from . import loader


class BaseStreamProvider(object):
    """ Basic stream provider system with a text identifier and a number
        identifier.
        Subclasses must provide an `in_stream` URI and the text identifier.
        The `stream_list` variable should have the number id's to be used.
    """
    conf = None  # Dictionary like object: configparser section
    in_stream = None
    identifier = None
    _rtmp_server = config['rtmp-server']
    out_stream = '{0}{1}/'.format(
        _rtmp_server['addr'],
        _rtmp_server['app']
    ) + '{0}'
    _stream_list = None
    _stream_data = None

    @classmethod
    def make_cmd(cls, id):
        """ Generate FFmpeg command to fetch video from
            remote source.
        """
        stream = cls.get_stream(id)
        return ffmpeg.cmd(
            cls.conf['input_opt'],
            cls.in_stream.format(stream),
            cls.conf['output_opt'],
            cls.out_stream.format(id),
        )

    @classmethod
    def _streams(cls):
        if cls._stream_list is None:
            cls.execute_lazy_initialization()
        return cls._stream_list

    @classmethod
    def execute_lazy_initialization(cls):
        cls._stream_data = cls.lazy_initialization()
        cls._stream_list = list(cls._stream_data)
        cls.post_initialization()

    @classmethod
    def lazy_initialization(cls):
        """ Override this method to provide a way to initialize the list
            of streams only when asked. This is handy when the list must
            be fetched from a remote source or might take a long time to
            respond.
            If the list is supplied in the class definition, it may delay
            the program start needlessly.
        """
        return {}

    @classmethod
    def post_initialization(cls):
        """ Set id information after stream data initialization
        """
        for k, v in cls._stream_data.items():
            v['id'] = cls.get_id(k)

    @classmethod
    def streams(cls):
        """ Get all streams ids
        """
        return [cls.make_id(x) for x in cls._streams()]

    @classmethod
    def stream_data(cls):
        """ Complete stream information in a dictionary
        """
        if cls._stream_data is None:
            cls.execute_lazy_initialization()
        return cls._stream_data

    @classmethod
    def _number_id(cls, id):
        """ The id number of a stream without possible class identifier.
        """
        return int(re.sub(r'\D', '', id))

    @classmethod
    def make_id(cls, num):
        """ Create an identifier from the id number.
        """
        return cls.identifier + str(num)

    @classmethod
    def get_stream(cls, id):
        """ Retrieve stream name based on id.
        """
        return cls._number_id(id)

    @classmethod
    def get_stream_data(cls, id):
        """ Return stream data based on id
        """
        if cls._stream_data is None:
            cls.execute_lazy_initialization()
        return cls._stream_data[cls.get_stream(id)]

    @classmethod
    def get_id(cls, stream):
        """ Get Id based on original stream number
        """
        return cls.identifier + str(stream)


class NamedStreamProvider(BaseStreamProvider):
    """ Subclass for provider system with names as identifiers instead
        of numbers or if you want to create a different numbering
        scheme.

        The `stream_list` variable must be given and contain the list of
        identifiers.
    """
    @classmethod
    def _streams(cls):
        super(NamedStreamProvider, cls)._streams()
        return list(range(len(cls._stream_list)))

    @classmethod
    def get_stream(cls, id):
        """ Retrieve stream name based on id.
        """
        return cls._stream_list[cls._number_id(id)]

    @classmethod
    def get_id(cls, stream):
        """ Get Id based on original stream name
        """
        return cls.identifier + str(cls._stream_list.index(stream))


# ---------------------------------------------------------------------
class Providers(object):
    """ Container for all providers and enabled providers.
    """
    _all = {}
    _enabled = {}

    @classmethod
    def values(cls):
        return cls._enabled.values()

    @classmethod
    def enabled(cls):
        return cls._enabled

    @classmethod
    def all(cls):
        return cls._all

    @classmethod
    def select(cls, id):
        """ Select enabled provider based on identifier.
        """
        id = re.search(r'^[A-Za-z]*', id).group(0)
        if not id:
            id = None
        return cls._enabled[id]

    @classmethod
    def enable(cls, identifier):
        """ Enable a provider based on text identifier.
            The provider must have been loaded into _all_providers first!
        """
        prov = cls._all[identifier]
        prov.is_enabled = True
        cls._enabled[identifier] = prov
        return prov

    @classmethod
    def disable(cls, identifier):
        """ Disable a provider based on text identifier.
        """
        prov = cls._enabled.pop(identifier)
        prov.is_enabled = False
        return prov

    @classmethod
    def load(cls):
        """ Load providers from configuration files on providers_data/ dir
        """
        ext = config['providers']['conf_file_ext']
        for conf in glob.glob(os.path.join(dirname, 'providers_data/*.' + ext)):
            parser = Parser()
            parser.read(conf)
            name = os.path.splitext(os.path.basename(conf))[0]
            cls.create(name, parser)

    #noinspection PyUnresolvedReferences
    @classmethod
    def _insert(cls, provider, auto_enable=True):
        """ Insert provider in the _all dictionary.
            If it is enabled and auto_enable is true,
            also inserts in the _enabled dictionary.
        """
        cls._all[provider.identifier] = provider
        if auto_enable and provider.is_enabled:
            cls._enabled[provider.identifier] = provider

    @classmethod
    def create(cls, cls_name, conf, auto_enable=True):
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
                mode = lazy, download, cache, file, list, named
                url = http://url-for-download-mode.com
                parser = module.function  # This function must generate
                                          # json-serializable data if cache
                                          # is enabled
                file = local_file_to_load.json
                list =
                    ID1 GEO1 DESCRIPITION1   # if "named", the ID is the name
                    ID2 GEO2 DESCRIPITION2   # used to fetch the stream with
                                             # the access url

            The mode list is how the streams will be provided.
        """
        strm = conf['streams']
        mode = set(strm.get_split('mode'))

        cls_ = BaseStreamProvider
        if 'named' in mode:
            cls_ = NamedStreamProvider

        attr = {}
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

            def fetch_function():
                streams = loader.get_streams(name, url, parser, fetch)
                return OrderedDict((x['id'], x) for x in streams)

        if 'lazy' in mode:
            attr['lazy_initialization'] = classmethod(lambda cls: fetch_function())
            attr['_stream_list'] = None
            attr['_stream_data'] = None
        else:
            stream_data = fetch_function()
            attr['_stream_data'] = stream_data
            attr['_stream_list'] = list(stream_data)

        conf = conf['base']
        attr.update(
            name = cls_name,
            identifier = conf['identifier'],
            in_stream = conf['access'],
            thumbnail_local = conf.getboolean('thumbnail_local', fallback=True),
            conf = conf,
            is_enabled = conf.getboolean(
                'enabled',
                fallback=config['providers'].getboolean('enabled')
            ),
        )

        if sys.version_info < (3, 0):
            # When configparser has an encoding set, all strings become
            # unicode and Py2k do not accept them as class name.
            cls_name = cls_name.encode('utf-8')

        provider = type(cls_name, (cls_,), attr)
        cls._insert(provider, auto_enable)

        if 'lazy' not in mode:
            # Only chance to run this function if
            # initialization is not lazy
            provider.post_initialization()

        return provider
