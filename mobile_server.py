import os
import sys

# Set dss root for local importing
dirname = os.path.dirname
_root = dirname(__file__)
sys.path.insert(0, _root)


from dss.mobile import TCPServer


server = TCPServer()
try:
    server.start(False)
except KeyboardInterrupt:
    server.stop()
