#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Environment module of maruberu."""

from datetime import datetime
import logging

from tornado import ioloop
from tornado.options import options

from .infrastructure import MaruBell, MemoryStorage, RedisStorage
from .models import BaseBell, BaseStorage, BellResource, BellResourceStatus, DataBaseAddress


_environment = None


def _create_env(bell: BaseBell, database: BaseStorage) -> dict:
    return {"bell": bell, "database": database}


async def _init_memory_storage_with_sample_data(storage: MemoryStorage):
    obj = BellResource(1000, None, None,
                       uuid="00000000-0000-0000-0000-000000000000")
    obj_sticky = BellResource(1000, None, None, sticky=True,
                              uuid="11111111-1111-1111-1111-111111111111")
    obj_api = BellResource(1000, None, None, api=True,
                           uuid="22222222-2222-2222-2222-222222222222")
    obj_sticky_api = BellResource(1000, None, None,
                                  sticky=True, api=True,
                                  uuid="33333333-3333-3333-3333-333333333333")
    obj_used = BellResource(1000, None, None,
                            uuid="44444444-4444-4444-4444-444444444444",
                            status=BellResourceStatus.USED)
    obj_before_period = BellResource(1000, datetime(9999, 12, 31), None,
                                     uuid="55555555-5555-5555-5555-555555555555")
    await storage.create_resource(obj)
    await storage.create_resource(obj_sticky)
    await storage.create_resource(obj_api)
    await storage.create_resource(obj_sticky_api)
    await storage.create_resource(obj_used)
    await storage.create_resource(obj_before_period)


def _load_env(name: str) -> dict:
    db = DataBaseAddress(options.database)
    if name == "REDIS":
        storage = RedisStorage(db)
    else:
        storage = MemoryStorage(db)
        if name != "ON_MEMORY":
            logging.warning("env '{}' is not found (ON_MEMORY will be used).".format(name))
        if options.debug:
            ioloop.IOLoop.current().add_callback(_init_memory_storage_with_sample_data, storage)

    return _create_env(MaruBell(storage), storage)


def get_env(name: str) -> dict:
    """Return env variabled from env name."""
    global _environment
    if _environment is None:
        _environment = _load_env(name)
    return _environment
