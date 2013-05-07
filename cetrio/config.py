"""
   Load configuration file into configparser object.
"""

import os
try:
    import configparser
except ImportError:
    import ConfigParser as configparser

config = configparser.ConfigParser()

dirname = os.path.abspath(os.path.dirname(__file__))
config.read(os.path.join(dirname, 'cetrio.conf'))

