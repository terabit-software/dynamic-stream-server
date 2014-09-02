# coding: utf-8
import importlib
import json
from os import path
import warnings
import makeobj
import time

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

from .config import config, dirname
from .tools import show
from .storage import db


def _get_from_file(file_path):
    """ Load camera data from local temp file.
    """
    with open(file_path) as f:
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


def _get_from_db(db_name):
    collection = db.providers[db_name]
    return list(collection.find())


def populate_database(db_name, content):
    collection = db.providers[db_name]
    collection.insert(content)


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
    cache, url, file, db = makeobj.keys(4)

all_places = (Place.cache, Place.url, Place.file, Place.db)


def get_streams(name=None, url=None, parser=None, db_name=None, is_dynamic=False, places=all_places):
    """ Load the streams from some media.

        If database support is set, this will be the only place where
        streams will be searched. Only if the database is still not
        populated, other places will be searched.

        Execution order:
        - DB (populated from any subsequent media)
        - Cache (populated from "External URL" only)
        - External URL
        - Fallback file
    """
    tmp = config.get('cache', 'dir')
    cached_data = None

    if Place.db in places:
        content = _get_from_db(db_name)
        if content:
            return content

    if Place.cache in places:
        basename = path.basename(name)
        tmp = path.join(tmp, basename)
        valid_for = config.getint('cache', 'valid_for')

        try:
            cached_data = _get_from_file(tmp)
            if time.time() - path.getmtime(tmp) < valid_for:
                populate_database(db_name, cached_data)
                return cached_data
        except IOError:
            pass
        except Exception as e:
            show("Error when loading streams data from cache:", repr(e))

    if Place.url in places:
        try:
            save = None
            if Place.cache in places:
                save = tmp
            url_data = _get_from_url(url, parser, save=save)
            populate_database(db_name, url_data)
            return url_data
        except Exception as e:
            show("Error when loading streams data from web:", repr(e))

    if cached_data:
        warnings.warn('Using possibly outdated cache for %r provider '
                      'because no other source was available' % name)
        return cached_data

    if Place.file in places:
        if len(places) > 1:  # Any other place should have higher priority
            warnings.warn('Using locally stored data %r for provider '
                          'as last resort.' % path.basename(name))
        file_data = _get_from_file(path.join(dirname, name))
        populate_database(db_name, file_data)
        return file_data

    if is_dynamic:
        # The database may be populated later
        return []

    raise ValueError('Could not load stream from: %s' %
                     [x.name for x in places])

