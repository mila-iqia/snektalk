import atexit
import errno
import json
import os
import random
import re
import socket
import subprocess
import threading
import webbrowser

import jurigged
from jurigged import codetools
from sanic import Sanic, response

from .config import get_config_path
from .lib import inject
from .network import create_inet, create_socket
from .session import Session

here = os.path.dirname(__file__)
assets_path = os.path.join(here, "assets")


def status_logger(sess):
    def log(event):
        if isinstance(event, codetools.UpdateOperation) and not isinstance(
            event.defn, codetools.FunctionDefinition
        ):
            return
        else:
            sess.queue(
                command="status", type="normal", value=str(event),
            )

    return log


def _launch(port=None, sock=None, open_browser=True, template={}, sess=None):
    if port is not None and sock is not None:
        raise ValueError("Cannot specify both port and socket")
    elif sock is not None:
        sock = create_socket(sock)
    elif port is None:
        sock = create_inet()
        host, port = sock.getsockname()
    else:
        host = "localhost"

    app = Sanic("snektalk")
    app.static("/favicon.ico", f"{assets_path}/favicon.ico")
    app.static("/lib/", f"{assets_path}/lib/")
    app.static("/scripts/", f"{assets_path}/scripts/")
    app.static("/style/", f"{assets_path}/style/")
    app.static("/fs/", "/")

    @app.route("/")
    async def index(request):
        index = open(os.path.join(assets_path, "index.html")).read()
        index = re.sub(
            r"{{([^{}]+)}}", lambda m: template.get(m[1], f"!!{m[1]}"), index
        )
        return response.html(index)

    @app.route("/status")
    async def status(request):
        return response.json({"status": "OK"})

    @app.websocket("/sktk")
    async def feed(request, ws):
        sess.bind(ws)
        while True:
            command = json.loads(await ws.recv())
            if sess.socket is ws:
                await sess.recv(**command)
            else:
                await ws.send(
                    json.dumps(
                        {
                            "command": "status",
                            "type": "error",
                            "value": "this connection was closed or pre-empted",
                        }
                    )
                )
                break

    if open_browser and port is not None:

        @app.listener("after_server_start")
        async def launch_browser(app, loop):
            webbrowser.open(f"http://{host}:{port}/")

    atexit.register(app.stop)
    atexit.register(sess.atexit)
    if port is not None:
        print(f"Start server at: http://{host}:{port}/")
    app.run(sock=sock, register_sys_signals=False)


def serve(watch_args=None, restart_command=None, **kwargs):
    sess = Session(
        history_file=get_config_path("history.json"),
        restart_command=restart_command,
    )
    if watch_args is not None:
        jurigged.watch(**watch_args, logger=status_logger(sess))

    def _start_server():
        _launch(sess=sess, **kwargs)

    thread = threading.Thread(target=_start_server, daemon=True)
    thread.start()

    sess.enter()
    inject()
    return sess
