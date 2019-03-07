#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections import defaultdict
import copy
import logging
from queue import Full, Queue
import subprocess
from threading import Lock, Thread
from typing import Dict, List, Optional, Tuple

from tornado.options import options

from .models import BaseBell, BaseContext, BaseStorage, BellResource
from .models import DataBaseAddress, ResourceBusyError


class MaruBell(BaseBell):
    def __init__(self, database: BaseStorage):
        super().__init__(database)
        self._ring_queue = Queue(1)
        self.worker_thread = Thread(target=self.worker)
        self.worker_thread.start()

    def ring(self, resource: BellResource):
        try:
            self._ring_queue.put_nowait(resource)
        except Full:
            raise ResourceBusyError

    def worker(self):
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


memory_storage: Dict[str, Tuple[BellResource, Lock]] = defaultdict(dict)


class MemoryContext(BaseContext):
    def __init__(self, resource: BellResource, lock: Optional[Lock]=None) -> None:
        super().__init__(resource)
        self._lock = lock

    def __enter__(self):
        return self

    def __exit__(self, ex_type, ex_value, trace):
        ex = ex_type or ex_value or trace
        if self._lock:
            self.resource.clear_validation_cache()
            if not ex:
                memory_storage[self.resource.uuid][0] = self.resource
            self._lock.release()
        return not ex


class MemoryStorage(BaseStorage):
    def __init__(self, addr: DataBaseAddress,
                 initial_resource_list: Optional[List[BellResource]]=None) -> None:
        super().__init__(addr)
        for r in (initial_resource_list or []):
            self.create_resource(r)

    def get_resource_context(self, key: str) -> MemoryContext:
        row = memory_storage.get(key)
        if row:
            row[1].acquire()
            return MemoryContext(copy.deepcopy(row[0]), row[1])
        else:
            return MemoryContext(None)

    def create_resource(self, obj: BellResource) -> None:
        if obj.uuid in memory_storage:
            raise ValueError
        else:
            memory_storage[obj.uuid] = [obj, Lock()]
