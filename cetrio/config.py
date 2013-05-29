"""
   Load configuration file into configparser object.
"""

import os
try:
    import configparser
except ImportError:
    import ConfigParser as configparser


dirname = os.path.abspath(os.path.dirname(__file__))

config = configparser.ConfigParser()
config.read(os.path.join(dirname, 'cetrio.conf'))

# Update system wide configs with local values.
_local_config = configparser.ConfigParser()
try:
    _local_config.read(os.path.join(dirname, 'local.conf'))
except Exception:
    pass
else:
    for sec in _local_config.sections():
        for k,v in _local_config.items(sec):
            config.set(sec, k, v)


def create_dir(name):
    if not os.path.exists(name):
        os.makedirs(name)

create_dir(config.get('cache', 'dir'))
create_dir(config.get('thumbnail', 'dir'))
create_dir(config.get('log', 'dir'))

