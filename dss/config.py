"""
   Load configuration file into configparser object.
"""
import os
import re
import string
import sys
import ast
import configparser


#noinspection PyCallingNonCallable
def _section_getattr_replacement(self, attr):
    if not attr.startswith('get'):
        raise AttributeError(attr)
    fn = getattr(self.parser, attr)
    return lambda *args, **kw: fn(self.name, *args, **kw)

#noinspection PyUnresolvedReferences
configparser.SectionProxy.__getattr__ = _section_getattr_replacement


def _ast_load(s):
    try:
        return ast.literal_eval(s)
    except Exception:
        return s


def _pseudo_list_load(value):
    tokens = []
    this = ''
    continuation = ''
    for char in value:
        if char == continuation:
            tokens.append(this)
            this = ''
            continuation = ''
            continue
        if continuation:
            this += char
            continue
        if char in string.whitespace + ',':
            if this:
                tokens.append(this)
                this = ''
            continue
        if char in '"\'':
            continuation = char
            continue
        this += char
    if continuation:
        raise ValueError('EOL while reading string. '
                         'Missing: %s' % continuation)
    if this:
        tokens.append(this)

    return [_ast_load(x) for x in tokens]


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
        return _pseudo_list_load(value)

    def get_multiline_list(self, section, option):
        value = self.get(section, option)
        return [_pseudo_list_load(x) for x in value.splitlines() if x.strip()]


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

