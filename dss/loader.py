# coding: utf-8
import json
from os import path
import makeobj

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

from .config import config, dirname


def _get_from_file(path):
    """ Load camera data from local temp file.
    """
    with open(path) as f:
        return json.load(f)


def _get_from_url(url, parser, save=None):
    """ Get most recent camera data from web and save
        in local file.
    """
    text = urlopen(url).read().decode('utf-8')
    data = parser(text)

    if save is not None:
        with open(save, 'w') as f:
            json.dump(data, f)
    return data


class Place(makeobj.Obj):
    cache, url, file = makeobj.keys(3)

all_places = (Place.cache, Place.url, Place.file)


def get_streams(name=None, url=None, parser=None, places=all_places):
    """ Load streams from cache or server.
        If not found, use fallback data.
    """
    tmp = config.get('cache', 'dir')

    if Place.cache in places:
        basename = path.basename(name)
        tmp = path.join(tmp, basename)

        try:
            return _get_from_file(tmp)
        except IOError:
            pass
        except Exception as e:
            print("Error when loading streams data from cache:", repr(e))

    if Place.url in places:
        try:
            save = None
            if Place.cache in places:
                save = tmp
            return _get_from_url(url, parser, save=save)
        except Exception as e:
            print("Error when loading streams data from web:", repr(e))

    if Place.file:
        return _get_from_file(path.join(dirname, name))

    raise ValueError('Could not load data from: %s' % places)
