"""
   Load configuration file into configparser object.
"""
import os
import re
import string
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


def _insert(x, obj):
    if isinstance(obj, set):
        obj.add(x)
    else:
        obj.append(x)


def _add_element(el, obj, allow_empty=False):
    if el or allow_empty:
        try:
            el = ast.literal_eval(el)
        except Exception:
            pass
        _insert(el, obj)
    return ''


def _pseudo_list_load(value):
    tokens = []
    block = tokens
    block_order = [tokens]

    this = ''
    continuation = ''
    block_continuation = []
    block_token = {
        '[': (list, ']'),
        '(': (list, ')'),
        '{': (set,  '}'),
    }
    close_error = [x[1] for x in block_token.values()]

    for char in value:
        if char == continuation:
            this = _add_element(this, block, allow_empty=True)
            continuation = ''
            continue
        elif continuation:
            this += char
            continue
        elif char in string.whitespace + ',':
            this = _add_element(this, block)
            continue
        elif char in '"\'':
            continuation = char
            continue
        elif char in block_token:
            type_, close = block_token[char]
            block = type_()
            block_continuation.append(close)
            _insert(block, block_order[-1])
            block_order.append(block)
            continue
        elif block_continuation and char in block_continuation[-1]:
            this = _add_element(this, block)
            block_order.pop()
            block_continuation.pop()
            block = block_order[-1]
            continue
        elif char in close_error:
            raise ValueError('Cannot close block: %s' % char)
        this += char

    if continuation:
        raise ValueError('End of text while reading string. '
                         'Missing: %s' % continuation)
    if block_continuation:
        raise ValueError('End of text while reading block. Missing: %s' %
                         ' '.join(reversed(block_continuation)))
    if this:
        _add_element(this, block)

    return tokens


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

    def read(self, filenames, encoding=None):
        if encoding is None:
            try:
                encoding = PROVIDER_CONFIG_ENCODING
            except NameError:
                pass
        return super(Parser, self).read(filenames, encoding)


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


# After configuration loaded.

def create_dir(name):
    if not os.path.exists(name):
        os.makedirs(name)

create_dir(config['cache']['dir'])
create_dir(config['thumbnail']['dir'])
create_dir(config['log']['dir'])

PROVIDER_CONFIG_ENCODING = config['providers']['conf_file_enc']
