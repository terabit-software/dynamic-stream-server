import sys
import os
from subprocess import *

from ..config import config

LOG_DIR = config['log']['dir']


def run_proc(id, cmd, mode):
    """ Open process with error output redirected to file.
        The standart output can be read.

        This should be used as a context manager to close the log file.
    """
    log = os.path.join(LOG_DIR, '{0}-{1}'.format(mode, id))
    with open(log, 'w') as f:
        return Popen(
            cmd,
            stdout=PIPE,
            stderr=f
        )


if sys.version_info < (3, 2):
    _Popen = Popen

    # Add context manager support for Popen class
    # on older Python versions
    class Popen(_Popen):
        def __enter__(self):
            return self

        def __exit__(self, type, value, traceback):
            if self.stdout:
                self.stdout.close()
            if self.stderr:
                self.stderr.close()
            if self.stdin:
                self.stdin.close()
                # Wait for the process to terminate, to avoid zombies.
            self.wait()
