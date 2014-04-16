# coding: utf-8
import random
import unittest
from dss.tools import buffer


class DummySocket(object):
    message = b'x'

    def recv_into(self, buff, k):
        data = self.recv(k)
        buff[:len(data)] = data
        return len(data)

    def recv(self, k):
        n = k - random.randrange(0, 10)
        if n <= 0:
            n = 1
        return self.message * n


class BufferTest(unittest.TestCase):
    def test_buffer_read(self):
        to_read = 10
        buff = buffer.Buffer(DummySocket())
        data = buff.read(to_read)

        self.assertIsInstance(data, bytearray)
        self.assertEqual(len(data), to_read)
        self.assertEqual(data, DummySocket.message * to_read)

        to_read = buff.read_size - to_read * 3
        DummySocket.message = b'y'
        buff.read_size = 5

        data = buff.read(to_read)
        self.assertEqual(len(data), to_read)


