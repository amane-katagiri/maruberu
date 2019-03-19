#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
import logging
from typing import Optional

from tornado import escape
from tornado import web
from tornado.options import options

from .models import BaseBell, BaseStorage, BellResource
from .models import ResourceBeforePeriodError, ResourceBusyError, ResourceDisabledError
from .models import ResourceForbiddenError, ResourceInUseError


class BaseRequestHandler(web.RequestHandler):
    cookie_username = "username"

    def get_current_user(self):
        username = self.get_secure_cookie(self.cookie_username)
        if escape.utf8(username) != escape.utf8(options.admin_username):
            return None
        else:
            return escape.utf8(username)

    def set_current_user(self, username) -> None:
        self.set_secure_cookie(self.cookie_username, escape.utf8(username))

    def clear_current_user(self) -> None:
        self.clear_cookie(self.cookie_username)

    def initialize(self, bell: BaseBell, database: BaseStorage) -> None:
        self.bell = bell
        self.database = database


class IndexHandler(BaseRequestHandler):
    def get(self) -> None:
        token = self.get_argument("token", "")
        with self.database.get_resource_context(token) as c:
            resource = c.resource
        self.render("index.html", token=escape.url_escape(token) if resource else "",
                    resource=resource)


class ResourceHandler(BaseRequestHandler):
    def check_xsrf_cookie(self):
        pass

    def _write_result(self, code: int, resource: BellResource, reason: Optional[str]=None):
        self.set_status(code)
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        obj = {"code": code,
               "reason": reason,
               "resource": resource.to_dict() if resource is not None else None}
        self.write(escape.json_encode(obj))

    def get(self, token) -> None:
        with self.database.get_resource_context(token) as c:
            resource = c.resource
        self._write_result(200 if resource is not None else 404, resource)

    def post(self, token) -> None:
        if self.get_argument("action", "") == "delete":
            super().check_xsrf_cookie()
            try:
                r = self.database.delete_resource(token)
                self._write_result(200, r)
            except KeyError:
                self._write_result(404, None)
        else:
            with self.database.get_resource_context(token) as c:
                resource = c.resource
                if not resource.api:
                    super().check_xsrf_cookie()
                try:
                    resource.ring(self.bell)
                except (ResourceBeforePeriodError, ResourceDisabledError):
                    self._write_result(403, resource)
                except AttributeError:
                    self._write_result(404, resource)
                except ResourceInUseError:
                    self._write_result(429, resource)
                except ResourceBusyError:
                    self._write_result(503, resource, "ベルが混雑しています。")
                except ResourceForbiddenError:
                    self._write_result(503, resource, "ベルを鳴らす準備ができていません。")
                else:
                    self._write_result(202, resource)


class AdminLoginHandler(BaseRequestHandler):
    def get(self) -> None:
        self.render("login.html")

    def post(self) -> None:
        username = self.get_argument("username")
        password = self.get_argument("password")
        if username == options.admin_username and password == options.admin_password:
            self.set_current_user(username)
            self.redirect("/admin/")
        else:
            self.redirect("/admin/login/")


class AdminLogoutHandler(BaseRequestHandler):
    @web.authenticated
    def get(self) -> None:
        self.clear_current_user()
        self.redirect("/admin/login/")


class AdminTokenHandler(BaseRequestHandler):
    @web.authenticated
    def get(self) -> None:
        items = self.database.get_all_resources()
        self.render("generate.html", items=items, new_token=None, old_token=None)

    @web.authenticated
    def post(self) -> None:
        if self.get_argument("action", "") == "delete":
            try:
                token = self.get_argument("token")
                r = self.database.delete_resource(token)
                items = self.database.get_all_resources()
                self.render("generate.html", items=items, new_token=None, old_token=r.uuid)
            except KeyError as ex:
                logging.warning(str(ex))
                items = self.database.get_all_resources()
                self.render("generate.html", items=items, new_token=None, old_token=None)
        else:
            milliseconds = self.get_argument("milliseconds")
            not_before_date = self.get_argument("not_before_date")
            not_before_time = self.get_argument("not_before_time") or "00:00:00"
            not_after_date = self.get_argument("not_after_date")
            not_after_time = self.get_argument("not_after_time") or "23:59:59"
            sticky = self.get_argument("sticky", "")
            api = self.get_argument("api", "")
            try:
                if int(milliseconds) <= 0:
                    msg = "milliseconds must be positive int (actual: {})"
                    raise ValueError(msg.format(milliseconds))
                r = BellResource(int(milliseconds),
                                 datetime.strptime("{} {}".format(not_before_date,
                                                                  not_before_time),
                                                   "%Y-%m-%d %H:%M:%S")
                                 if not_before_date else None,
                                 datetime.strptime("{} {}".format(not_after_date, not_after_time),
                                                   "%Y-%m-%d %H:%M:%S")
                                 if not_after_date else None,
                                 bool(sticky),
                                 bool(api))
                self.database.create_resource(r)
                items = self.database.get_all_resources()
                self.render("generate.html", items=items, new_token=r.uuid, old_token=None)
            except Exception as ex:
                logging.warning(str(ex))
                items = self.database.get_all_resources()
                self.render("generate.html", items=items, new_token=None, old_token=None)
