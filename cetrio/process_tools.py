
import sys
from subprocess import *


if sys.version_info < (3, 2):

    # Add context manager support for Popen class
    # on older Python versions
    class Popen(Popen):
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