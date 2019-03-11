#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from enum import Enum
import re
from typing import Callable, List, Optional, Union
import uuid

import pytz


class BellResourceStatus(Enum):
    UNDEFINED = 0
    UNUSED = 10
    USING = 20
    USED = 30


class InvalidResourceOperationError(RuntimeError):
    pass


class ResourceInUseError(InvalidResourceOperationError):
    pass


class ResourceDisabledError(InvalidResourceOperationError):
    pass


class ResourceBeforePeriodError(InvalidResourceOperationError):
    pass


class ResourceBusyError(InvalidResourceOperationError):
    pass


class ResourceForbiddenError(InvalidResourceOperationError):
    pass


class BellResource(object):
    def __init__(self, milliseconds: int,
                 not_before: Optional[datetime], not_after: Optional[datetime],
                 sticky: bool=False,
                 uuid: Union[str, Callable]=uuid.uuid4,
                 status: BellResourceStatus=BellResourceStatus.UNUSED) -> None:
        # on table
        self.uuid: str = str(uuid() if callable(uuid) else uuid)
        self.milliseconds: int = milliseconds
        self.not_before: Optional[datetime] = not_before
        self.not_after: Optional[datetime] = not_after
        self.sticky: bool = sticky
        self._status: BellResourceStatus = status
        self.created_at: datetime = datetime.now(pytz.utc)
        self.updated_at: datetime = datetime.now(pytz.utc)
        # not on table
        self._is_before_period: Optional[bool] = None
        self._is_after_period: Optional[bool] = None

    @classmethod
    def from_dict(cls, buf) -> BellResource:
        return cls(int(buf["milliseconds"]),
                   datetime.fromisoformat(buf["not_before"])
                   if buf["not_before"] is not None else None,
                   datetime.fromisoformat(buf["not_after"])
                   if buf["not_after"] is not None else None,
                   bool(buf["sticky"]), uuid=str(buf["uuid"]),
                   status=BellResourceStatus[buf["status"]])

    def to_dict(self) -> str:
        obj = {"uuid": self.uuid,
               "milliseconds": self.milliseconds,
               "not_before": self.not_before.isoformat() if self.not_before is not None else None,
               "not_after": self.not_after.isoformat() if self.not_after is not None else None,
               "sticky": self.sticky,
               "status": self._status.name}
        return obj

    def _validate_period(self) -> None:
        self._is_before_period = (datetime.now(pytz.utc) <
                                  self.not_before.astimezone(pytz.utc)
                                  if self.not_before else False)
        self._is_after_period = (self.not_after.astimezone(pytz.utc) <
                                 datetime.now(pytz.utc)
                                 if self.not_after else False)

    def clear_validation_cache(self) -> None:
        self._is_before_period = None
        self._is_after_period = None

    def is_before_period(self) -> bool:
        if self._is_before_period is None:
            self._validate_period()
        return self._is_before_period

    def is_after_period(self) -> bool:
        if self._is_after_period is None:
            self._validate_period()
        return self._is_after_period

    def is_within_period(self) -> bool:
        return not self.is_before_period() and not self.is_after_period()

    def is_unused(self) -> bool:
        return self._status is BellResourceStatus.UNUSED

    def is_using(self) -> bool:
        return self._status is BellResourceStatus.USING

    def is_used(self) -> bool:
        return self._status is BellResourceStatus.USED

    def is_valid(self) -> bool:
        return self.is_within_period() and self.is_unused()

    def ring(self, bell: BaseBell) -> None:
        if not self.is_valid():
            if self.is_before_period():
                raise ResourceBeforePeriodError
            elif self.is_after_period() or self.is_used():
                raise ResourceDisabledError
            elif self.is_using():
                raise ResourceInUseError
            else:
                raise InvalidResourceOperationError
        elif False:  # TODO
            raise ResourceForbiddenError
        else:
            bell.ring(self)
            self._status = BellResourceStatus.USING

    def success(self) -> None:
        if not self.is_using():
            raise InvalidResourceOperationError
        else:
            if self.sticky and self.is_within_period():
                self._status = BellResourceStatus.UNUSED
            else:
                self._status = BellResourceStatus.USED

    def fail(self) -> None:
        if not self.is_using():
            raise InvalidResourceOperationError
        else:
            if not self.is_within_period():
                self._status = BellResourceStatus.USED
            else:
                self._status = BellResourceStatus.UNUSED


class DataBaseAddress(object):
    def __init__(self, uri: str):
        if re.match("[^:]+:[0-9]+/.+", uri):
            self.username, self.password = None, None
            self.host, remain = uri.split(":", 1)
            self.port, self.db = remain.split("/", 1)
        elif re.match("[^:]+:.*@[^:]+:[0-9]+/.+", uri):
            cred, loc = uri.rsplit("@", 1)
            self.username, self.password = cred.split(":", 1)
            self.host, remain = loc.split(":", 1)
            self.port, self.db = remain.split("/", 1)
        else:
            msg = "{} is not in database address format (user:pass@)host:port/dbname"
            raise ValueError(msg.format(uri))

    def __repr__(self):
        if self.username:
            return repr("{}:{}@{}:{}/{}".format(self.username, self.password,
                                                self.host, self.port, self.db))
        else:
            return repr("{}:{}/{}".format(self.host, self.port, self.db))

    def __str__(self):
        if self.username:
            return str("{}:{}@{}:{}/{}".format(self.username, self.password,
                                               self.host, self.port, self.db))
        else:
            return str("{}:{}/{}".format(self.host, self.port, self.db))


class BaseContext(object):
    def __init__(self, resource: BellResource) -> None:
        self.resource = resource

    def __enter__(self):
        raise NotImplementedError

    def __exit__(self, ex_type, ex_value, trace):
        raise NotImplementedError


class BaseStorage(object):
    def __init__(self, addr: DataBaseAddress) -> None:
        self.addr = addr

    def get_resource_context(self, key: str) -> BaseContext:
        raise NotImplementedError

    def get_all_resources(self,
                          cond: Optional[List]=None,
                          start_key: Optional[str]=None,
                          limit: Optional[int]=None) -> List[BellResource]:
        raise NotImplementedError

    def create_resource(self, obj: BellResource) -> None:
        raise NotImplementedError

    def delete_resource(self, key: str) -> BellResource:
        raise NotImplementedError


class BaseBell(object):
    def __init__(self, database: BaseStorage) -> None:
        self.database = database

    def ring(self, resource: BellResource) -> None:
        raise NotImplementedError
