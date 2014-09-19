from __future__ import print_function


def show(*args, **kw):
    # Compatibility with dss 0.6 or older.
    # Use dss.tools.show.show instead
    print(*args, **kw)


class DictObj(dict):
    """ Dictionary with attribute syntax to get, set and delete items.
    """
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, item):
        try:
            del self[item]
        except KeyError:
            raise AttributeError(item)


class Suppress:
    """ Silence chosen exceptions.
        Almost like `contextlib.suppress` (Only available on Python 3.4+).
    """
    def __init__(self, *args):
        self.cls = args or None
        self.errors = []

    def __enter__(self):
        return self

    def __call__(self, *args):
        return type(self)(*args)

    def __exit__(self, cls, exc, trace):
        if cls is not None:
            self.errors.append((cls, exc, trace))

        if self.cls is None or cls is None or issubclass(cls, self.cls):
            return True
