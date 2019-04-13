#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Model module of maruberu."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
import logging
import re
from typing import Callable, List, Optional, Union
import uuid

import pytz


class BellResourceStatus(Enum):
    """Status of bell resource.

    * UNDEFINED: don't use
    * UNUSED: resource is free and available
    * USING: resource is in use (will be free if resource is *sticky*)
    * USED: resource is free but no longer available
    """

    UNDEFINED = 0
    UNUSED = 10
    USING = 20
    USED = 30


class InvalidResourceOperationError(RuntimeError):
    """Base exception for BellResource."""

    def __init__(self, msg: str="") -> None:
        """Initialize with detailed message."""
        super().__init__(msg)
        self.msg = msg


class ResourceInUseError(InvalidResourceOperationError):
    """The resource is in use. Ring after free."""

    def __init__(self) -> None:
        """Initialize with detailed message."""
        super().__init__("同じトークンを同時に使うことはできません。")


class ResourceDisabledError(InvalidResourceOperationError):
    """The resource is no longer available."""

    def __init__(self) -> None:
        """Initialize with detailed message."""
        super().__init__("このトークンは使用済みです。")


class ResourceBeforePeriodError(InvalidResourceOperationError):
    """The resource is not enabled yet. Ring later."""

    def __init__(self) -> None:
        """Initialize with detailed message."""
        super().__init__("このトークンはまだ有効ではありません。")


class ResourceBusyError(InvalidResourceOperationError):
    """The bell is in use by other resource now. Ring later."""

    def __init__(self) -> None:
        """Initialize with detailed message."""
        super().__init__("ベルが混雑しています。")


class ResourceForbiddenError(InvalidResourceOperationError):
    """The bell is not ready now. Ring later."""

    def __init__(self) -> None:
        """Initialize with detailed message."""
        super().__init__("ベルを鳴らす準備ができていません。")


class BellResource(object):
    """Resource of ringing bell with fixed time."""

    def __init__(self, milliseconds: int,
                 not_before: Optional[datetime], not_after: Optional[datetime],
                 sticky: bool=False,
                 api: bool=False,
                 uuid: Union[str, Callable]=uuid.uuid4,
                 status: BellResourceStatus=BellResourceStatus.UNUSED,
                 failed_count: int=0,
                 created_at: Optional[datetime]=None,
                 updated_at: Optional[datetime]=None) -> None:
        """Initialize with resource params."""
        if not_before and not_after and not_before > not_after:
            raise ValueError("Expected not_before < not_after,\
 but {}(not_before) > {}(not_after).".format(not_before, not_after))
        # on table
        self.uuid: str = str(uuid() if callable(uuid) else uuid)
        self.milliseconds: int = milliseconds
        self.not_before: Optional[datetime] = not_before
        self.not_after: Optional[datetime] = not_after
        self.sticky: bool = sticky
        self.api: bool = api
        self._status: BellResourceStatus = status
        self._failed_count: int = failed_count
        self.created_at: datetime = (datetime.fromisoformat(created_at) if created_at else
                                     datetime.now(pytz.utc))
        self.updated_at: datetime = (datetime.fromisoformat(updated_at) if updated_at else
                                     datetime.now(pytz.utc))
        # not on table
        self._is_before_period: Optional[bool] = None
        self._is_after_period: Optional[bool] = None

    @classmethod
    def from_dict(cls, buf) -> BellResource:
        """Get BellResource from dict."""
        return cls(int(buf["milliseconds"]),
                   datetime.fromisoformat(buf["not_before"])
                   if buf["not_before"] else None,
                   datetime.fromisoformat(buf["not_after"])
                   if buf["not_after"] else None,
                   bool(buf.get("sticky", False)), bool(buf.get("api", False)),
                   uuid=str(buf["uuid"]),
                   status=BellResourceStatus[buf["status"]],
                   failed_count=int(buf.get("failed_count", 0)),
                   created_at=buf["created_at"],
                   updated_at=buf["updated_at"])

    def to_dict(self) -> str:
        """Extract BellResource as dict."""
        obj = {"uuid": self.uuid,
               "milliseconds": self.milliseconds,
               "not_before": self.not_before.isoformat() if self.not_before else None,
               "not_after": self.not_after.isoformat() if self.not_after else None,
               "sticky": self.sticky,
               "api": self.api,
               "status": self._status.name,
               "failed_count": self._failed_count,
               "created_at": self.created_at.isoformat() if self.created_at else None,
               "updated_at": self.updated_at.isoformat() if self.updated_at else None}
        return obj

    def _validate_period(self) -> None:
        """Check if it is within valid period.

        The result will be cached in `_is_before_period` and `_is_after_period`.
        """
        self._is_before_period = (datetime.now(pytz.utc) <
                                  self.not_before.astimezone(pytz.utc)
                                  if self.not_before else False)
        self._is_after_period = (self.not_after.astimezone(pytz.utc) <
                                 datetime.now(pytz.utc)
                                 if self.not_after else False)

    def clear_validation_cache(self) -> None:
        """Clear validation result (see `_validate_period`)."""
        self._is_before_period = None
        self._is_after_period = None

    def is_before_period(self) -> bool:
        """Check if it is before valid period (see `_validate_period`)."""
        if self._is_before_period is None:
            self._validate_period()
        return self._is_before_period

    def is_after_period(self) -> bool:
        """Check if it is after valid period (see `_validate_period`)."""
        if self._is_after_period is None:
            self._validate_period()
        return self._is_after_period

    def is_within_period(self) -> bool:
        """Check if it is within valid period (see `_validate_period`)."""
        return not self.is_before_period() and not self.is_after_period()

    def is_unused(self) -> bool:
        """Check if resource is unused."""
        return self._status is BellResourceStatus.UNUSED

    def is_using(self) -> bool:
        """Check if resource is in use."""
        return self._status is BellResourceStatus.USING

    def is_used(self) -> bool:
        """Check if resource is no longer available."""
        return self._status is BellResourceStatus.USED

    def is_valid(self) -> bool:
        """Check if resource is free and available."""
        return self.is_within_period() and self.is_unused()

    def ring(self, bell: BaseBell) -> None:
        """Ring bell by this resource."""
        if not self.is_valid():
            if self.is_before_period():
                raise ResourceBeforePeriodError
            elif self.is_after_period() or self.is_used():
                raise ResourceDisabledError
            elif self.is_using():
                raise ResourceInUseError
            else:
                raise InvalidResourceOperationError
        elif False:  # TODO forbid
            raise ResourceForbiddenError
        else:
            bell.ring(self)
            self._status = BellResourceStatus.USING

    def success(self) -> None:
        """Callback method if resource succeeded in ringing bell."""
        if not self.is_using():
            raise InvalidResourceOperationError
        else:
            self._failed_count = 0
            if self.sticky and self.is_within_period():
                self._status = BellResourceStatus.UNUSED
            else:
                self._status = BellResourceStatus.USED

    def fail(self) -> None:
        """Callback method if resource failed in ringing bell."""
        if not self.is_using():
            raise InvalidResourceOperationError
        else:
            self._failed_count += 1
            if not self.is_within_period():
                self._status = BellResourceStatus.USED
            else:
                self._status = BellResourceStatus.UNUSED
            if self._failed_count >= 3:
                logging.error("'{}' was failed {} times.".format(self.uuid, self._failed_count))


class DataBaseAddress(object):
    """Database address representation with host, port and dbname."""

    def __init__(self, uri: str):
        """Initialize with URI in format of `(user:pass@)host:port/dbname`."""
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
        """Return URI in format of `(user:pass@)host:port/dbname` in repr(str)."""
        if self.username:
            return repr("{}:{}@{}:{}/{}".format(self.username, self.password,
                                                self.host, self.port, self.db))
        else:
            return repr("{}:{}/{}".format(self.host, self.port, self.db))

    def __str__(self):
        """Return URI in format of `(user:pass@)host:port/dbname` in str."""
        if self.username:
            return str("{}:{}@{}:{}/{}".format(self.username, self.password,
                                               self.host, self.port, self.db))
        else:
            return str("{}:{}/{}".format(self.host, self.port, self.db))


class BaseContext(object):
    """With-statement context which processes database with specified resource."""

    def __init__(self, resource: BellResource) -> None:
        """Initialize with BellResource."""
        self.resource = resource

    async def __aenter__(self):
        """Enter context with resource."""
        raise NotImplementedError

    async def __aexit__(self, ex_type, ex_value, trace):
        """Exit context with resource."""
        raise NotImplementedError


class BaseStorage(object):
    """Database implementation."""

    def __init__(self, addr: DataBaseAddress) -> None:
        """Initialize with database address."""
        self.addr = addr

    async def get_resource_context(self, key: str) -> BaseContext:
        """Get resource from database and return the resource wrapped with context."""
        raise NotImplementedError

    def get_all_resources(self,
                          cond: Optional[List]=None,
                          start_key: Optional[str]=None,
                          limit: Optional[int]=None) -> List[BellResource]:
        """Get resource list from database."""
        raise NotImplementedError

    async def create_resource(self, obj: BellResource) -> None:
        """Create resource record."""
        raise NotImplementedError

    async def delete_resource(self, key: str) -> BellResource:
        """Delete resource record."""
        raise NotImplementedError


class BaseBell(object):
    """Bell implementation."""

    def __init__(self, database: BaseStorage) -> None:
        """Initialize with database."""
        self.database = database

    def ring(self, resource: BellResource) -> None:
        """Ring bell and notify result to the resource."""
        raise NotImplementedError


async def init_storage_with_sample_data(storage: BaseStorage):
    samples = {"00000000-0000-0000-0000-000000000000":
               BellResource(1000, None, None,
                            uuid="00000000-0000-0000-0000-000000000000"),
               "11111111-1111-1111-1111-111111111111":
               BellResource(1000, None, None, sticky=True,
                            uuid="11111111-1111-1111-1111-111111111111"),
               "22222222-2222-2222-2222-222222222222":
               BellResource(1000, None, None, api=True,
                            uuid="22222222-2222-2222-2222-222222222222"),
               "33333333-3333-3333-3333-333333333333":
               BellResource(1000, None, None, sticky=True, api=True,
                            uuid="33333333-3333-3333-3333-333333333333"),
               "44444444-4444-4444-4444-444444444444":
               BellResource(1000, None, None,
                            uuid="44444444-4444-4444-4444-444444444444",
                            status=BellResourceStatus.USED),
               "55555555-5555-5555-5555-555555555555":
               BellResource(1000, datetime(9999, 12, 31), None,
                            uuid="55555555-5555-5555-5555-555555555555"), }
    for k, v in samples.items():
        c = await storage.get_resource_context(k)
        async with c:
            if not c.resource:
                await storage.create_resource(v)
            else:
                c.resource = v
