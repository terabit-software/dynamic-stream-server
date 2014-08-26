""" Enums for mobile stream communication.
"""
import makeobj


class DataContent(makeobj.Obj):
    metadata = 0
    video = 1
    audio = 2
    userdata = 3


class ContentType(makeobj.Obj):
    meta = 0
    coord = 1
    cmd = 2