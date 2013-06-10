import glob
import os
import re

from .config import Parser, config, dirname
from . import loader
from . import ffmpeg

def select_provider(id):
    """ Select provider based on identifier.
    """
    id = re.search(r'^[A-Za-z]*', id).group(0)
    if not id:
        id = None
    return providers[id]


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
    stream_list = None

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
        if cls.stream_list is None:
            cls.stream_list = cls.lazy_initialization()
        return cls.stream_list

    @classmethod
    def lazy_initialization(cls):
        """ Override this method to provide a way to initialize the list
            of streams only when asked. This is handy when the list must
            be fetched from a remote source or might take a long time to
            respond.
            If the list is supplied in the class definition, it may delay
            the program start needlessly.
        """
        return []

    @classmethod
    def streams(cls):
        return [cls.make_id(x) for x in cls._streams()]

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
    def get_id(cls, stream):
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
        return list(range(len(cls.stream_list)))

    @classmethod
    def get_stream(cls, id):
        return cls.stream_list[cls._number_id(id)]

    @classmethod
    def get_id(cls, stream):
        return cls.identifier + str(cls.stream_list.index(stream))


def create_provider(cls_name, conf):
    strm = conf['streams']
    mode = set(strm.get_split('mode'))

    cls = BaseStreamProvider
    if 'named' in mode:
        cls = NamedStreamProvider

    attr = {}
    if 'list' in mode:
        def fetch_function():
            return [x[0] for x in strm.get_multiline_list('list')]
    else:
        fetch = []
        url = None
        parser = None
        name = None
        if 'download' in mode:
            fetch.append(loader.Place.url)
            url = strm['url']
            parser = loader.load_object(strm['parser'], 'dss.providers')
        if 'cache' in mode:
            fetch.append(loader.Place.cache)
            name = strm.get('file', cls_name + '-streams.json')
        if 'file' in mode:
            fetch.append(loader.Place.file)
            join = os.path.join
            name = join(join(dirname, 'providers'), strm['file'])

        def fetch_function():
            return [x['id'] for x in loader.get_streams(name, url, parser, fetch)]

    if 'lazy' in mode:
        attr['lazy_initialization'] = classmethod(lambda cls: fetch_function())
        attr['stream_list'] = None
    else:
        attr['stream_list'] = fetch_function()

    conf = conf['base']
    attr.update(
        identifier = conf['identifier'],
        in_stream = conf['access'],
        conf = conf
    )
    return type(cls_name, (cls,), attr)


# Load providers from "conf" files on providers/ dir
providers = {}
for conf in glob.glob(os.path.join(dirname, 'providers/*.conf')):
    parser = Parser()
    parser.read(conf)
    name = os.path.splitext(os.path.basename(conf))[0]
    prov = create_provider(name, parser)
    # noinspection PyUnresolvedReferences
    providers[prov.identifier] = prov
