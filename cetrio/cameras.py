# coding: utf-8
import re
import json
from os import path
try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

from config import config, dirname


_reg_cet = re.compile(r"LatLng\(\s*([\d\.-]+)\s*,\s*([\d\.-]+)\s*\)"
                      r".*?\n"
                      r".*?(\d+).*?'(.*?)'.*?'(.*?)'")


def _get_from_file(path):
    """ Load camera data from local temp file.
    """
    with open(path) as f:
        return json.load(f)


def _get_from_url(save=None):
    """ Get most recent camera data from web and save
        in local file.
    """
    url = config.get('camera', 'url')
    text = urlopen(url).read().decode('utf-8')

    data = _reg_cet.findall(text)
    data = [{'id': int(x[2]),
             'geo': [float(i) for i in x[:2]],
             'name': x[3],
             'status': 'Desligado' not in x[-1]}
            for x in data]

    if save is not None:
        with open(save, 'w') as f:
            json.dump(data, f)
    return data


def get_cameras():
    """ Load cameras from cache or server.
        If not found, use fallback data.
    """
    name = config.get('camera', 'file')
    tmp = config.get('cache', 'dir')
    tmp = path.join(tmp, name)

    try:
        return _get_from_file(tmp)
    except IOError:
        pass
    except Exception as e:
        print("Error when loading cameras from cache:", repr(e))
    
    try:
        return _get_from_url(save=tmp)
    except Exception as e:
        print("Error when loading cameras from web:", repr(e))

    # Fallback: not on cache and can't load from server
    return _get_from_file(path.join(dirname, name)) 


