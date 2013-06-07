"""
   Load configuration file into configparser object.
"""

import os
import configparser

def Parser():
    return configparser.ConfigParser(
        interpolation=configparser.ExtendedInterpolation()
    )

dirname = os.path.abspath(os.path.dirname(__file__))

config = Parser()
config.read(os.path.join(dirname, 'global.conf'))

# Update system wide configs with local values.
_local_config = Parser()
try:
    _local_config.read(os.path.join(dirname, 'local.conf'))
except Exception:
    pass
else:
    for sec in _local_config.sections():
        for k,v in _local_config.items(sec):
            config[sec][k] = v


def create_dir(name):
    if not os.path.exists(name):
        os.makedirs(name)

create_dir(config['cache']['dir'])
create_dir(config['thumbnail']['dir'])
create_dir(config['log']['dir'])

