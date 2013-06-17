# coding: utf-8
import importlib
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


def load_object(name, package=None):
    """ Load an object from a module and, if the module
        cannot be found in a package (if given), it will
        be loaded from global namespace.
        No relative imports allowed.
    """
    module, function = name.rsplit('.', 1)
    load_from_global = True
    if package:
        try:
            module = importlib.import_module(package + '.' + module)
        except ImportError:
            pass
        else:
            load_from_global = False

    if load_from_global:
        module = importlib.import_module(module)

    return getattr(module, function)


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
