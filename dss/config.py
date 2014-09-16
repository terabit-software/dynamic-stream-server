"""
   Load configuration file into configparser object.
"""
import os
import re
import string
import configparser

from .tools import pseudo_list


### Fixing the SectionProxy class from configparser module.
def _section_getattr_replacement(self, attr):
    if not attr.startswith('get'):
        raise AttributeError(attr)
    fn = getattr(self.parser, attr)
    return lambda *args, **kw: fn(self.name, *args, **kw)

configparser.SectionProxy.__getattr__ = _section_getattr_replacement


class Parser(configparser.ConfigParser):

    def __init__(self, *args, **kw):
        kw.setdefault('interpolation', configparser.ExtendedInterpolation())
        super(Parser, self).__init__(*args, **kw)

    def get_split_basic(self, section, option, char=None):
        return self.get(section, option).split(char)

    def get_split(self, section, option, chars=string.whitespace, extra=','):
        value = self.get(section, option)
        if extra:
            chars += extra
        return re.split('[%s]' % re.escape(chars), value)

    def get_list(self, section, option):
        value = self.get(section, option)
        return pseudo_list.load(value)

    def get_multiline_list(self, section, option):
        value = self.get(section, option)
        return [pseudo_list.load(x) for x in value.splitlines() if x.strip()]

    def read(self, filenames, encoding=None):
        if encoding is None:
            try:
                encoding = PROVIDER_CONFIG_ENCODING
            except NameError:
                pass
        return super(Parser, self).read(filenames, encoding)


dirname = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(dirname, 'template')

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
        for k, v in _local_config.items(sec):
            config[sec][k] = v


# After configuration loaded.

def create_dir(name):
    if not os.path.exists(name):
        os.makedirs(name)

create_dir(config['cache']['dir'])
create_dir(config['thumbnail']['dir'])
create_dir(config['log']['dir'])
create_dir(config['mobile']['dir'])
create_dir(config['recorder']['dir'])

PROVIDER_CONFIG_ENCODING = config['providers']['conf_file_enc']
