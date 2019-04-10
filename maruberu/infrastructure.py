#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Infrastracture module of maruberu."""

import copy
import logging
from queue import Full, Queue
import subprocess
from threading import Lock, Thread
from typing import Dict, List, Optional

from tornado.options import options

from .models import BaseBell, BaseContext, BaseStorage, BellResource
from .models import DataBaseAddress, ResourceBusyError


class MaruBell(BaseBell):
    """Bell implementation with physical bell."""

    def __init__(self, database: BaseStorage) -> None:
        """Initialize with database."""
        super().__init__(database)
        self._ring_queue = Queue(1)
        self.worker_thread = Thread(target=self.worker)
        self.worker_thread.start()

    def ring(self, resource: BellResource) -> None:
        """Add resource to queue."""
        try:
            self._ring_queue.put_nowait(resource)
        except Full:
            raise ResourceBusyError

    def worker(self) -> None:
        """Ring bell and notify result to the resource."""
        while True:
            item = self._ring_queue.get()
            if item is None:
                break
            try:
                p = subprocess.Popen([str(options.ring_command), str(item.milliseconds)])
                p.wait()
            except Exception as ex:
                logging.warning(str(ex))
                with self.database.get_resource_context(item.uuid) as c:
                    c.resource.fail()
            else:
                with self.database.get_resource_context(item.uuid) as c:
                    if p.returncode == 0:
                        c.resource.success()
                    else:
                        c.resource.fail()
            self._ring_queue.task_done()


memory_storage_resource: Dict[str, BellResource] = dict()
memory_storage_lock: Dict[str, Lock] = dict()


class MemoryContext(BaseContext):
    """With-statement context which processes MemoryStorage with specified resource."""

    def __init__(self, resource: BellResource, lock: Optional[Lock]=None) -> None:
        """Initialize with BellResource and releasable lock."""
        super().__init__(resource)
        self._lock = lock

    def __enter__(self):
        """Enter context with resource."""
        return self

    def __exit__(self, ex_type, ex_value, trace):
        """Write back resource and release lock."""
        ex = ex_type or ex_value or trace
        if self._lock:
            self.resource.clear_validation_cache()
            if not ex:
                memory_storage_resource[self.resource.uuid] = self.resource
            self._lock.release()
        return not ex


class MemoryStorage(BaseStorage):
    """Database implementation with on-memory dict."""

    def __init__(self, addr: DataBaseAddress,
                 initial_resource_list: Optional[List[BellResource]]=None) -> None:
        """Initialize with initial resource list."""
        super().__init__(addr)
        for r in (initial_resource_list or []):
            self.create_resource(r)

    def get_resource_context(self, key: str) -> MemoryContext:
        """Get resource from database and return the resource wrapped with MemoryContext."""
        lock = memory_storage_lock.get(key)
        if lock:
            lock.acquire()
            resource = memory_storage_resource.get(key)
            if resource:
                return MemoryContext(copy.deepcopy(resource), lock)
            else:
                lock.release()
                return MemoryContext(None)
        else:
            return MemoryContext(None)

    def get_all_resources(self,
                          cond: Optional[List]=None,
                          start_key: Optional[str]=None,
                          limit: Optional[int]=None) -> List[BellResource]:
        """Get resource list from database."""
        if start_key is not None and start_key not in memory_storage_resource:
            raise KeyError
        return list(reversed([memory_storage_resource[x] for x in memory_storage_resource.keys()
                              if start_key is None or memory_storage_resource[x].created_at >=
                              memory_storage_resource[start_key].created_at][:limit]))

    def create_resource(self, obj: BellResource) -> None:
        """Create resource record."""
        if obj.uuid in memory_storage_resource:
            raise ValueError
        else:
            memory_storage_resource[obj.uuid] = copy.deepcopy(obj)
            memory_storage_lock[obj.uuid] = Lock()

    def delete_resource(self, key: str) -> BellResource:
        """Delete resource record."""
        if key not in memory_storage_resource:
            raise KeyError
        else:
            r = copy.deepcopy(memory_storage_resource[key])
            memory_storage_lock[key].acquire()
            del memory_storage_resource[key]
            memory_storage_lock[key].release()
            return r

# TODO: impl RedisContext/Storage
