
import pymongo

from .config import config
from .tools import DictObj, show

client = pymongo.MongoClient()
conf = config['database']
database_name = conf['name']
db = client[database_name]


class KeyValueStorage(object):
    def __init__(self, database_name):
        self.__dict__['_db'] = db[database_name]

    def __getattr__(self, name):
        obj = self._db.find_one({'key': name})
        if obj is None:
            raise AttributeError(name)
        return obj['value']

    def __setattr__(self, name, value):
        self._db.update(
            {'key': name},
            {"$set": {'value': value}},
            upsert=True,
        )

    def __delattr__(self, name):
        self._db.remove({'key': name})

    __getitem__ = __getattr__
    __setitem__ = __setattr__
    __delitem__ = __delattr__


dbs = DictObj(
    meta = KeyValueStorage('metadata'),
    providers = db.providers,
    static = db.static_streams,
    mobile = db.mobile_streams,
)


def update_database():
    if not hasattr(dbs.meta, 'version'):
        dbs.meta.version = 0  # stub

    db_version = conf.getint('version')
    current_version = dbs.meta.version

    if current_version != db_version:
        show('Database content version is {}. Upgrading to version {}'.format(
            current_version, db_version
        ))

    # TODO: Do some actual updating, if it is possible