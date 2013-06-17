"""
   Load configuration file into configparser object.
"""
import os
import re
import string
import ast
import configparser

### Fixing the SectionProxy class from configparser module.
#noinspection PyCallingNonCallable
def _section_getattr_replacement(self, attr):
    if not attr.startswith('get'):
        raise AttributeError(attr)
    fn = getattr(self.parser, attr)
    return lambda *args, **kw: fn(self.name, *args, **kw)

#noinspection PyUnresolvedReferences
configparser.SectionProxy.__getattr__ = _section_getattr_replacement


class _Pair(object):
    def __init__(self, a, b):
        self._data = (a, b)

    __hash__ = None

    @property
    def data(self):
        return self._data

    @classmethod
    def convert_list(cls, lst):
        pairs = sum(isinstance(x, cls) for x in lst)
        if pairs:
            if pairs != len(lst):
                print('-->', pairs)
                raise TypeError('Do not mix dictionary key-value '
                                'pairs with single values.')
            return dict(x.data for x in lst)
        return set(lst)

    _pair_error = 'Cannot create pair without %s element.'

    @classmethod
    def insert_element(cls, el, obj, allow_empty=False, create_pair=False):
        if el or allow_empty:
            try:
                el = ast.literal_eval(el)
            except Exception:
                pass
            if create_pair:
                try:
                    el = cls(obj.pop(), el)
                except IndexError:
                    raise TypeError(cls._pair_error % 'first')
            obj.append(el)
        elif create_pair:
            raise TypeError(cls._pair_error % 'second')
        return '', False


def _pseudo_list_load(value):
    tokens = []
    block = tokens
    block_order = [tokens]

    this = ''
    continuation = ''
    block_continuation = []
    block_token = {
        '[': ']',
        '(': ')',
        '{': '}',
    }
    block_token_close = {
        ']': list,
        ')': tuple,
        '}': _Pair.convert_list,
    }
    next_as_pair = False

    for char in value:
        if char == continuation:
            this, next_as_pair = _Pair.insert_element(
                continuation + this + continuation,  # Interpreted as string
                block,
                allow_empty=True,
                create_pair=next_as_pair
            )
            continuation = ''
            continue
        elif continuation:
            this += char
            continue
        elif char in string.whitespace + ',':
            if next_as_pair and not this:
                if char == ',':
                    raise ValueError('Expecting dictionary value, '
                                     'got "," instead')
                else:
                    continue
            this, next_as_pair = _Pair.insert_element(
                this, block,
                create_pair=next_as_pair
            )
            continue
        elif char in '"\'':
            if not continuation:
                continuation = char
                continue
        elif char in ':':
            next_as_pair = True
            this, _ = _Pair.insert_element(this, block, create_pair=False)
            if not block_continuation or block_continuation[-1] != '}':
                raise ValueError('Cannot create dictionary without { }')
            continue
        elif char in block_token:
            block = []
            block_order.append(block)
            block_continuation.append(block_token[char])
            continue
        elif block_continuation and char in block_continuation[-1]:
            char = block_continuation.pop()
            this, next_as_pair = _Pair.insert_element(
                this, block,
                create_pair=next_as_pair
            )
            converter = block_token_close[char]
            old_block = converter(block_order.pop())
            block = block_order[-1]
            block.append(old_block)
            continue
        elif char in block_token_close:
            raise ValueError('Cannot close block: %s' % char)
        this += char

    if continuation:
        raise ValueError('End of text while reading string. '
                         'Missing: %s' % continuation)
    if block_continuation:
        raise ValueError('End of text while reading block. Missing: %s' %
                         ' '.join(reversed(block_continuation)))
    if this:
        _Pair.insert_element(this, block, create_pair=next_as_pair)

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
