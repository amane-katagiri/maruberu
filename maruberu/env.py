#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging

from tornado.options import options

from .infrastructure import MaruBell, MemoryStorage
from .models import BaseBell, BaseStorage


_environment = None


def _create_env(bell: BaseBell, database: BaseStorage) -> dict:
    return {"bell": bell, "database": database}


def _load_env():
    memory_storage = MemoryStorage(options.database)
    return {"ON_MEMORY": _create_env(MaruBell(memory_storage), memory_storage)}


def get_env(name: str):
    global _environment
    if _environment is None:
        _environment = _load_env()
    if name not in _environment:
        logging.warning("env '{}' is not found (ON_MEMORY will be used).".format(name))
    return _environment.get(name, _environment["ON_MEMORY"])
