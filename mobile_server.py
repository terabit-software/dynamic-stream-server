import os
import sys

# Set dss root for local importing
dirname = os.path.dirname
_root = dirname(__file__)
sys.path.insert(0, _root)


from dss.mobile import TCPServer
from dss.mobile.handler import MediaHandler


server = TCPServer()
try:
    server.start(False)
except KeyboardInterrupt:
    server.stop()
    MediaHandler.wait_handlers()