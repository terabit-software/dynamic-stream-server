# coding: utf-8
import ast
import string


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


def load(value):
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
            this, next_as_pair = _Pair.insert_element(
                this, block,
                create_pair=next_as_pair
            )
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