from __future__ import print_function
from . import thread

PRINT_LOCK = thread.Lock()

def show(*args, **kw):
    with PRINT_LOCK:
        print(*args, **kw)

