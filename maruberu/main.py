#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Main module of maruberu."""

import crypt
import logging
import pathlib

from tornado import httpserver
from tornado import ioloop
from tornado import web
from tornado.options import define
from tornado.options import options

from .env import get_env
from .handler import AdminLoginHandler, AdminLogoutHandler, AdminTokenHandler
from .handler import IndexHandler, ResourceHandler


define("conf", default="conf/server.conf", type=str)
define("debug", default=False, type=bool)
define("host", default="localhost", type=str)
define("port", default=8000, type=int)
define("cookie_secret", default="secret", type=str)
define("ring_command", default="echo", type=str)
define("admin_username", default="admin", type=str)
define("admin_password", default="password", type=str)
define("admin_password_hashed", default="", type=str)
define("database", default="localhost:6379/0", type=str)
define("env", default="ON_MEMORY", type=str)


def main() -> None:
    """Start maruberu server."""
    options.parse_command_line(final=False)
    if pathlib.Path(options.conf).is_file():
        options.parse_config_file(options.conf, final=False)
        options.parse_command_line()
    else:
        options.parse_command_line()
        logging.warning("conf '{}' is not found.".format(options.conf))
    cwd = pathlib.Path(__file__).resolve().parent
    if options.ring_command[:2] == ":/":
        options.ring_command = str(cwd / options.ring_command[2:])
    if options.admin_password_hashed == "":
        options.admin_password_hashed = crypt.crypt(options.admin_password)

    settings = {
        "xsrf_cookies": True,
        "cookie_secret": options.cookie_secret,
        "static_path": pathlib.Path(__file__).parent / "static",
        "template_path": pathlib.Path(__file__).parent / "templates",
        "login_url": "/admin/login/",
        "autoescape": "xhtml_escape",
        "debug": options.debug,
    }
    env = get_env(options.env)
    app = web.Application([
        (r"/", IndexHandler, env),
        (r"/resource/([0-9a-f-]+)?/?", ResourceHandler, env),
        (r"/admin/?", AdminTokenHandler, env),
        (r"/admin/login/?", AdminLoginHandler, env),
        (r"/admin/logout/?", AdminLogoutHandler, env),
        (r"/static/(.*)", web.StaticFileHandler),
    ], **settings)
    server = httpserver.HTTPServer(app)

    server.listen(options.port)
    try:
        ioloop.IOLoop.current().start()
    except KeyboardInterrupt:
        ioloop.IOLoop.current().add_callback(get_env("ON_MEMORY")["bell"]._ring_queue.put, None)


if __name__ == "__main__":
    main()
