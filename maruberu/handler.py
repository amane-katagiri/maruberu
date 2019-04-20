#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Handler module of maruberu."""

import crypt
from datetime import datetime
from hmac import compare_digest as compare_hash
import logging
from typing import Optional

from accept_types import parse_header
import pytz
from tornado import escape
from tornado import ioloop
from tornado import web
from tornado.options import options

from .models import BaseBell, BaseStorage, BellResource, init_storage_with_sample_data
from .models import ResourceBeforePeriodError, ResourceBusyError, ResourceDisabledError
from .models import ResourceForbiddenError, ResourceInUseError


class BaseRequestHandler(web.RequestHandler):
    """Useful RequestHandler.

    * Load/store username from secure cookie.
    * Set `env` variables in `initialize` method.
    """

    cookie_username = "username"

    def get_current_user(self) -> Optional[bytes]:
        """Load username from secure cookie."""
        username = self.get_secure_cookie(self.cookie_username)
        if escape.utf8(username) != escape.utf8(options.admin_username):
            return None
        else:
            return escape.utf8(username)

    def set_current_user(self, username) -> None:
        """Store username to secure cookie."""
        self.set_secure_cookie(self.cookie_username, escape.utf8(username))

    def clear_current_user(self) -> None:
        """Clear username from secure cookie."""
        self.clear_cookie(self.cookie_username)

    def initialize(self, bell: BaseBell, database: BaseStorage) -> None:
        """Set `env variables` before handle request."""
        self.bell = bell
        self.database = database


class IndexHandler(BaseRequestHandler):
    """RequestHandler for general user."""

    async def get(self) -> None:
        """Render index page.

        * Show command page to user who has valid token.
        * Show token form page to user who doesn't have valid token.
        """
        token = self.get_argument("token", None)
        resource = None
        if token:
            try:
                c = await self.database.get_resource_context(token)
            except Exception as ex:
                logging.error("Error in getting resource '{}' ({}).".format(token, ex))
                self.set_status(503)
                self.write_error(503)
                return
            async with c:
                resource = c.resource
        items = list()
        if options.debug:
            items = ["00000000-0000-0000-0000-000000000000",
                     "11111111-1111-1111-1111-111111111111",
                     "22222222-2222-2222-2222-222222222222",
                     "33333333-3333-3333-3333-333333333333",
                     "44444444-4444-4444-4444-444444444444",
                     "55555555-5555-5555-5555-555555555555"]
        self.render("index.html",
                    token=escape.url_escape(token) if token else None, resource=resource, msg="",
                    items=items)


class ResourceHandler(BaseRequestHandler):
    """RequestHandler for managing resource."""

    def check_xsrf_cookie(self) -> None:
        """Ignore XSRF cookie.

        If resource has `api` flag, permit action without XSRF token.
        """
        pass

    def _write_json_result(self, code: int, token: str, resource: Optional[BellResource],
                           reason: Optional[str]=None) -> None:
        """Write response in json.

        Use in resource which has `api` flag.
        """
        self.set_status(code)
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        obj = {"code": code,
               "reason": reason,
               "resource": resource.to_dict() if resource else None}
        self.write(escape.json_encode(obj))

    def _write_html_result(self, code: int, token: str, resource: Optional[BellResource],
                           reason: Optional[str]=None) -> None:
        """Write response in html.

        Use in resource which doesn't have `api` flag.
        """
        self.set_status(code)
        self.render("index.html", token=token,
                    resource=resource if resource else None, msg=reason, items=None)

    def _write_result(self, code: int, token: str, resource: Optional[BellResource],
                      reason: Optional[str]=None) -> None:
        accept = parse_header(self.request.headers.get("accept"))
        html_weight = max([*[x.weight for x in accept if x.matches("text/html")], -1])
        json_weight = max([*[x.weight for x in accept if x.matches("application/json")], -1])
        if resource:
            if not resource.api and html_weight > 0:
                self._write_html_result(code, token, resource, reason)
            elif resource.api and json_weight > 0:
                self._write_json_result(code, token, resource, reason)
            elif html_weight > 0 and html_weight >= json_weight:
                self._write_html_result(code, token, resource, reason)
            elif json_weight > 0 and json_weight >= html_weight:
                self._write_json_result(code, token, resource, reason)
            else:
                self.set_status(406)
                self.write_error(406)
        else:
            if html_weight > 0 and html_weight >= json_weight:
                self._write_html_result(code, token, resource, reason)
            elif json_weight > 0 and json_weight >= html_weight:
                self._write_json_result(code, token, resource, reason)
            else:
                self.set_status(406)
                self.write_error(406)

    async def get(self, token: str) -> None:
        """Render resource page."""
        if not token:
            self.redirect("/")
            return
        try:
            c = await self.database.get_resource_context(token)
        except Exception as ex:
            logging.error("Error in getting resource '{}' ({}).".format(token, ex))
            self._write_result(500, token, None, str(ex) if options.debug else None)
            return
        async with c:
            resource = c.resource
        self._write_result(200 if resource else 404, token, resource)

    async def post(self, token: str) -> None:
        """Ring or delete resource."""
        if not token:
            if self.get_argument("action", "") == "reset":
                if not options.debug:
                    self._write_result(403, token, None, "その操作は許可されていません。")
                else:
                    try:
                        ioloop.IOLoop.current().add_callback(init_storage_with_sample_data,
                                                             self.database)
                    except Exception as ex:
                        logging.error("Error in reset resource ({}).".format(ex))
                        self._write_result(500, token, None, str(ex) if options.debug else None)
                    else:
                        self.redirect("/")
            else:
                self.redirect("/")
            return
        if self.get_argument("action", "") == "delete":
            super().check_xsrf_cookie()
            try:
                await self.database.delete_resource(token)
                self.redirect("/")
            except KeyError as ex:
                logging.warning(str(ex))
                self._write_result(404, token, None)
            except Exception as ex:
                logging.error("Error in deleting resource ({}).".format(ex))
                self._write_result(500, token, None, str(ex) if options.debug else None)
        else:
            try:
                try:
                    c = await self.database.get_resource_context(token)
                except Exception as ex:
                    logging.error("Error in getting resource '{}' ({}).".format(token, ex))
                    self._write_result(500, token, None, str(ex) if options.debug else None)
                    return
                async with c:
                    resource = c.resource
                    if not resource:
                        self._write_result(404, token, None)
                        return
                    if not resource.api:
                        super().check_xsrf_cookie()
                    try:
                        resource.ring(self.bell)
                    except (ResourceBeforePeriodError, ResourceDisabledError) as ex:
                        self._write_result(403, token, resource, ex.msg)
                    except ResourceInUseError as ex:
                        self._write_result(429, token, resource, ex.msg)
                    except ResourceBusyError as ex:
                        self._write_result(503, token, resource, ex.msg)
                    except ResourceForbiddenError as ex:
                        self._write_result(503, token, resource, ex.msg)
                    else:
                        self._write_result(202, token, resource)
            except Exception as ex:
                logging.error("Error in ringing resource ({}).".format(ex))
                self._write_result(500, token, None, str(ex) if options.debug else None)


class AdminLoginHandler(BaseRequestHandler):
    """RequestHandler for login as admin."""

    def get(self) -> None:
        """Render admin login page."""
        if self.get_current_user():
            self.redirect("/admin/")
        else:
            self.render("login.html", failed=False)

    def post(self) -> None:
        """Attempt login as admin."""
        username = self.get_argument("username")
        password = self.get_argument("password")
        if (username == options.admin_username and
                compare_hash(crypt.crypt(password, options.admin_password_hashed),
                             options.admin_password_hashed)):
            self.set_current_user(username)
            self.redirect("/admin/")
        else:
            self.render("login.html", failed=True)


class AdminLogoutHandler(BaseRequestHandler):
    """RequestHandler for logout."""

    @web.authenticated
    def get(self) -> None:
        """Logout and redirect to admin login page."""
        self.clear_current_user()
        self.redirect("/admin/login/")


class AdminTokenHandler(BaseRequestHandler):
    """RequestHandler for managing resource as admin."""

    @web.authenticated
    def get(self) -> None:
        """Render resource list page."""
        try:
            items = self.database.get_all_resources()
        except Exception as ex:
            logging.error("Error in getting resources ({}).".format(ex))
            self.set_status(500)
            self.write_error(500)
            return
        self.render("generate.html", items=items, new_token=None, old_token=None,
                    failed_in_delete=False, failed_in_create=False,
                    tz=datetime.now(pytz.timezone(options.timezone)).strftime("%z"))

    @web.authenticated
    async def post(self) -> None:
        """Create or delete resource."""
        if self.get_argument("action", "") == "delete":
            try:
                token = self.get_argument("token")
                r = await self.database.delete_resource(token)
                items = self.database.get_all_resources()
                self.render("generate.html", items=items,
                            new_token=None, old_token=r.uuid,
                            failed_in_delete=False, failed_in_create=False,
                            tz=datetime.now(pytz.timezone(options.timezone)).strftime("%z"))
            except KeyError as ex:
                logging.warning(str(ex))
                token = self.get_argument("token", None)
                items = self.database.get_all_resources()
                self.render("generate.html", items=items,
                            new_token=None, old_token=token,
                            failed_in_delete=True, failed_in_create=False,
                            tz=datetime.now(pytz.timezone(options.timezone)).strftime("%z"))
            except Exception as ex:
                logging.error("Error in deleting resource ({}).".format(ex))
                token = self.get_argument("token", None)
                items = self.database.get_all_resources()
                self.render("generate.html", items=items,
                            new_token=None, old_token=token,
                            failed_in_delete=True, failed_in_create=False,
                            tz=datetime.now(pytz.timezone(options.timezone)).strftime("%z"))
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
                await self.database.create_resource(r)
                items = self.database.get_all_resources()
                self.render("generate.html", items=items, new_token=r.uuid, old_token=None,
                            failed_in_delete=False, failed_in_create=False,
                            tz=datetime.now(pytz.timezone(options.timezone)).strftime("%z"))
            except Exception as ex:
                logging.warning(str(ex))
                items = self.database.get_all_resources()
                self.render("generate.html", items=items, new_token=None, old_token=None,
                            failed_in_delete=False, failed_in_create=True,
                            tz=datetime.now(pytz.timezone(options.timezone)).strftime("%z"))
