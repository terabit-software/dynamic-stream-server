"""
    Tools for some OS related problems
"""
from __future__ import absolute_import

import os
import warnings

try:
    import fcntl
except ImportError:
    fcntl = None


def set_pipe_max_size(*pipes):
    global PIPE_SIZE
    if PIPE_SIZE is None:
        # On the first time, try to get the max pipe
        # size value. Should only work on Linux
        try:
            with open('/proc/sys/fs/pipe-max-size') as f:
                PIPE_SIZE = int(f.read())
        except IOError:
            PIPE_SIZE = False

    if not PIPE_SIZE:
        return

    F_SETPIPE_SZ = 1031
    for pipe in pipes:
        fcntl.fcntl(pipe, F_SETPIPE_SZ, PIPE_SIZE)


def pipe_nonblock_read(pipe):
    if fcntl is None:
        warnings.warn(
            'Pipe not set to nonblock because `fcntl` is absent',
            RuntimeError
        )
        return
    fcntl.fcntl(pipe, fcntl.F_SETFL, os.O_NONBLOCK)