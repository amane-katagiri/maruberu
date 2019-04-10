#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Environment module of maruberu."""

import logging

from tornado.options import options

from .infrastructure import MaruBell, MemoryStorage, RedisStorage
from .models import BaseBell, BaseStorage, DataBaseAddress


_environment = None


def _create_env(bell: BaseBell, database: BaseStorage) -> dict:
    return {"bell": bell, "database": database}


def _load_env(name: str) -> dict:
    db = DataBaseAddress(options.database)
    if name == "REDIS":
        storage = RedisStorage(db)
    else:
        storage = MemoryStorage(db)
        if name != "ON_MEMORY":
            logging.warning("env '{}' is not found (ON_MEMORY will be used).".format(name))
    return _create_env(MaruBell(storage), storage)


def get_env(name: str) -> dict:
    """Return env variabled from env name."""
    global _environment
    if _environment is None:
        _environment = _load_env(name)
    return _environment
