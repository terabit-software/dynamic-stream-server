import re

from ..tools import ffmpeg
from ..config import config


class BaseStreamProvider(object):
    """ Basic stream provider system with a text identifier and a number
        identifier.
        Subclasses must provide an `in_stream` URI and the text identifier.
        The `stream_list` variable should have the number id's to be used.
    """
    conf = None  # Dictionary like object: configparser section
    in_stream = None
    identifier = None
    recorder = None
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
            Start related services
        """
        for k, v in cls._stream_data.items():
            v['id'] = cls.get_id(k)

        if cls.recorder is not None:
            cls.recorder.start()

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


class DynamicStreamProvider(NamedStreamProvider):

    @classmethod
    def get_id(cls, stream):
        pass