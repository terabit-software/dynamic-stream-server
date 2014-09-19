
import pymongo

from .config import config
from .tools.show import show

client = pymongo.MongoClient()
conf = config['database']
database_name = conf['name']
_db = client[database_name]


class KeyValueStorage(object):
    def __init__(self, database_name, db=_db):
        self.__dict__['_db'] = db[database_name]

    def __getattr__(self, name):
        obj = self._db.find_one({'key': name})
        if obj is None:
            raise AttributeError(name)
        return obj['value']

    def __setattr__(self, name, value):
        self._db.update(
            {'key': name},
            {'$set': {'value': value}},
            upsert=True,
        )

    def __delattr__(self, name):
        self._db.remove({'key': name})

    __getitem__ = __getattr__
    __setitem__ = __setattr__
    __delitem__ = __delattr__


class DB:
    meta = KeyValueStorage('metadata')
    providers = _db.providers
    static = _db.static_streams
    mobile = _db.mobile_streams

db = DB


def update_database():
    if not hasattr(db.meta, 'version'):
        db.meta.version = 0  # stub

    db_version = conf.getint('version')
    current_version = db.meta.version

    if current_version != db_version:
        show('Database content version is {}. Upgrading to version {}'.format(
            current_version, db_version
        ))

    # TODO: Do some actual updating, if it is possible
