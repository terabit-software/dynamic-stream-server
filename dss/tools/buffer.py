"""
    Socket Buffer
    Usage:

    buff = Buffer(socket_object)
    buff.read(10)

"""
from . import thread


class _BaseBuffer(object):

    def __init__(self, size):
        self._data = bytearray(size)
        self._pos = 0
        self._max = 0
        self._require_resize = False
        self._inconsistent_state = False

    def __len__(self):
        return self._max - self._pos

    def _extract(self, amount):
        pos = self._pos

        if amount:
            self._pos += amount
        else:
            self._pos = self._max

        return self._data[pos:self._pos]

    def set_size(self, value):
        self._require_resize = value

    def set(self, data, clear_data=False, fill_later=False):
        """ Set new content for buffer.

            The buffer must be empty for data to be added unless
            `clear_data` is set.

            If the buffer is being set directly, call this function
            first with the `fill_later` argument set. This is required
            for the buffer to be resized if needed and previous content
            to be checked.
        """
        if len(self) and not clear_data:
            raise BufferError('Rewriting non empty buffer.')

        if self._require_resize:
            self._data = bytearray(self._require_resize)
            self._require_resize = False

        if fill_later:
            self._inconsistent_state = True
        else:
            self._data[:] = data
            self._pos = 0
            self._max = len(data)

    def set_fill(self, size):
        """ To be used with the `fill_later` argument of `set` method
            After the buffer is filled, this function will set the
            filled size and set the state to consistent.
        """
        self._pos = 0
        self._max = size
        self._inconsistent_state = False

    def get(self, amount):
        if self._inconsistent_state:
            raise BufferError('Buffer is inconsistent.')

        read_size = amount if amount <= len(self) else 0
        return self._extract(read_size)

    def view(self):
        return self._data


class Buffer(thread.LockedObject):

    def __init__(self, socket, read_size=4096, lock=None):
        self.socket = socket
        self._read_size = read_size
        self.buffer = _BaseBuffer(read_size)
        super(Buffer, self).__init__(lock)

    @property
    def read_size(self):
        return self._read_size

    @read_size.setter
    def read_size(self, value):
        self._read_size = value
        self.buffer.set_size(value)

    @thread.lock_method
    def read(self, amount):
        data = bytearray()
        while True:
            new_data = self.buffer.get(amount)
            data.extend(new_data)
            amount -= len(new_data)
            if not amount:
                break

            self.buffer.set(None, fill_later=True)
            read = self.socket.recv_into(self.buffer.view(), self.read_size)
            if not read: 
                break  # TODO RAISE ERROR???
            self.buffer.set_fill(read)

        return data
