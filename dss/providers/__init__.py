import glob
import os
import re

from ..config import Parser, config, dirname
from .. import recorder


class Providers(object):
    """ Container for all providers and enabled providers.
    """
    _all = {}
    _enabled = {}

    @classmethod
    def values(cls):
        return cls._enabled.values()

    @classmethod
    def enabled(cls):
        return cls._enabled

    @classmethod
    def all(cls):
        return cls._all

    @classmethod
    def select(cls, id):
        """ Select enabled provider based on identifier.
        """
        id = re.search(r'^[A-Za-z]*', id).group(0)
        if not id:
            id = None
        return cls._enabled[id]

    @classmethod
    def enable(cls, identifier):
        """ Enable a provider based on text identifier.
            The provider must have been loaded into _all_providers first!
        """
        prov = cls._all[identifier]
        prov.is_enabled = True
        cls._enabled[identifier] = prov
        return prov

    @classmethod
    def disable(cls, identifier):
        """ Disable a provider based on text identifier.
        """
        prov = cls._enabled.pop(identifier)
        prov.is_enabled = False
        return prov

    @classmethod
    def load(cls):
        """ Load providers from configuration files on providers_data/ dir
        """
        ext = config['providers']['conf_file_ext']
        for conf in glob.glob(os.path.join(dirname, 'providers_data/*.' + ext)):
            parser = Parser()
            parser.read(conf)
            name = os.path.splitext(os.path.basename(conf))[0]
            cls.create(name, parser)

    @classmethod
    def finish(cls):
        """ Stop Providers related services:
                - Stream recording
        """
        for provider in cls._all.values():
            if provider.recorder is not None:
                provider.recorder.stop()

    #noinspection PyUnresolvedReferences
    @classmethod
    def _insert(cls, provider, auto_enable=True):
        """ Insert provider in the _all dictionary.
            If it is enabled and auto_enable is true,
            also inserts in the _enabled dictionary.
        """
        cls._all[provider.identifier] = provider
        if auto_enable and provider.is_enabled:
            cls._enabled[provider.identifier] = provider

    @classmethod
    def add_recorder(cls, provider, conf):
        try:
            rec = conf['record']
        except KeyError:
            return

        if not rec.getboolean('enabled', True):
            return

        interval = rec.getint('interval', None)
        format = rec.get('format', None)
        provider.recorder = recorder.StreamRecorder(provider, interval, format)

    @classmethod
    def create(cls, cls_name, conf, auto_enable=True):
        from .loader import load
        provider = load(cls_name, conf)
        cls.add_recorder(provider, conf)
        cls._insert(provider, auto_enable)
