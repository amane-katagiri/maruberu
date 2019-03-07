#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import pathlib

from tornado import httpserver
from tornado import ioloop
from tornado import web
from tornado.options import define
from tornado.options import options

from .env import get_env
from .handler import AdminLoginHandler, AdminLogoutHandler, GenerateTokenHandler
from .handler import IndexHandler, ResourceHandler
from .models import DataBaseAddress


define("conf", default="conf/server.conf")
define("debug", default=False, type=bool)
define("host", default="localhost", type=str)
define("port", default=8000, type=int)
define("cookie_secret", default="secret", type=str)
define("ring_command", default="echo", type=str)
define("admin_username", default="admin", type=str)
define("admin_password", default="password", type=str)
define("database", default="localhost:6379/0", type=DataBaseAddress)
define("env", default="ON_MEMORY", type=str)


def main():
    options.parse_command_line()
    if pathlib.Path(options.conf).is_file():
        options.parse_config_file(options.conf)
    else:
        logging.warning("conf '{}' is not found.".format(options.conf))
    options.parse_command_line()

    settings = {
        "cookie_secret": options.cookie_secret,
        "static_path": pathlib.Path(__file__).parent / "static",
        "template_path": pathlib.Path(__file__).parent / "templates",
        "login_url": "/admin/login/",
        "autoescape": "xhtml_escape",
        "debug": options.debug,
    }
    app = web.Application([
        (r"/", IndexHandler, get_env(options.env)),
        (r"/resource/([0-9a-f-]+)/?", ResourceHandler, get_env(options.env)),
        (r"/admin/?", GenerateTokenHandler, get_env(options.env)),
        (r"/admin/login/?", AdminLoginHandler, get_env(options.env)),
        (r"/admin/logout/?", AdminLogoutHandler, get_env(options.env)),
    ], **settings)
    server = httpserver.HTTPServer(app)

    server.listen(options.port)
    ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
