import ffmpeg
from config import config
import re
import cameras as _cetrio_cameras


def select_provider(id):
    """ Select provider based on identifier.
    """
    id = re.search(r'^[A-Za-z]*', id).group(0)
    if not id:
        id = None
    return providers[id]


class BaseRemoteCamera(object):
    """ Basic camera system with a text identifier and a numbering
        identifier.
        Subclasses must provide a `in_stream` URI and the text identifier.
        The `_cam` variable should have the number id's to be used.
    """
    conf = None
    in_stream = None
    identifier = None
    out_stream = '{0}{1}/'.format(
        config.get('rtmp-server', 'addr'),
        config.get('rtmp-server', 'app')
    ) + '{0}'
    _cam = None

    @classmethod
    def make_cmd(cls, id):
        """ Generate FFmpeg command to fetch video from
            remote source.
        """
        cam = cls.get_camera(id)
        return ffmpeg.cmd(
            config.get(cls.conf, 'input_opt'),
            cls.in_stream.format(cam),
            config.get(cls.conf, 'output_opt'),
            cls.out_stream.format(id),
        )

    @classmethod
    def _cameras(cls):
        if cls._cam is None:
            cls._cam = cls.lazy_initialization()
        return cls._cam

    @classmethod
    def lazy_initialization(cls):
        """ Override this method to provide a way to initialize the list
            of cameras only when asked. This is handy when the list must
            be fetched from a remote source or might take a long time to
            respond.
            If the list is supplied in the class definition, it may delay
            the program start needlessly.
        """
        return []

    @classmethod
    def cameras(cls):
        return [cls.make_id(x) for x in cls._cameras()]

    @classmethod
    def _number_id(cls, id):
        """ The id number of a camera without possible class identifier.
        """
        return int(re.sub(r'\D', '', id))

    @classmethod
    def make_id(cls, num):
        """ Create an identifier from the id number.
        """
        return cls.identifier + str(num)

    @classmethod
    def get_camera(cls, id):
        """ Retrieve camera name based on id.
        """
        return cls._number_id(id)

    @classmethod
    def get_id(cls, camera):
        return cls.identifier + str(camera)


class NamedRemoteCamera(BaseRemoteCamera):
    """ Subclass for camera System with names as identifiers instead
        of numbers or if you want to create a different numbering
        system.

        The `_cam` variable must be given and contain the list of
        identifiers.
    """
    @classmethod
    def _cameras(cls):
        super(NamedRemoteCamera, cls)._cameras()
        return list(range(len(cls._cam)))

    @classmethod
    def get_camera(cls, id):
        return cls._cam[cls._number_id(id)]

    @classmethod
    def get_id(cls, camera):
        return cls.identifier + str(cls._cam.index(camera))


class Cetrio(BaseRemoteCamera):
    conf = 'cetrio'
    identifier = 'C'
    in_stream = '{0}{1}/{2} {3}'.format(
        config.get(conf, 'addr'),
        config.get(conf, 'app'),
        config.get(conf, 'stream'),
        config.get(conf, 'data'),
    )

    @classmethod
    def lazy_initialization(cls):
        return [c['id'] for c in _cetrio_cameras.get_cameras()]


class Fundao(NamedRemoteCamera):
    conf = 'fundao'
    identifier = 'F'
    in_stream = config.get(conf, 'addr')
    _cam = config.get(conf, 'cameras').split()


# Select stream provider classes from global namespace.
# noinspection PyUnresolvedReferences
providers = dict(
    (cls.identifier, cls)
    for cls in globals().values()
    if isinstance(cls, type) and \
       issubclass(cls, BaseRemoteCamera) and \
       cls.conf is not None # remove base classes
)
