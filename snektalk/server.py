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
from sanic import Sanic, response

from .repr import inject
from .session import Session

here = os.path.dirname(__file__)
assets_path = os.path.join(here, "assets")


def check_port(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", port))
    except socket.error as e:
        if e.errno == errno.EADDRINUSE:
            return False
        else:
            raise
    s.close()
    return True


def find_port(preferred_port, min_port, max_port):
    """Find a free port in the specified range.

    Use preferred_port if available (does not have to be in the range).
    """
    candidate = preferred_port
    while not check_port(candidate):
        print("Nope to", candidate)
        candidate = random.randint(min_port, max_port)
    return candidate


def status_logger(sess):
    def log(event):
        sess.queue(
            command="status", type="normal", value=str(event),
        )

    return log


class SessionLock:
    def __init__(self):
        self.session = None
        self.lock = threading.Lock()
        self.lock.acquire()

    def set(self, session):
        self.session = session
        self.lock.release()

    def get(self):
        self.lock.acquire()
        self.lock.release()
        return self.session


def _launch(slock, watch_args=None, template={}):
    port = find_port(6499, min_port=6500, max_port=6600)

    app = Sanic("snektalk")
    app.static("/lib/", f"{assets_path}/lib/")
    app.static("/scripts/", f"{assets_path}/scripts/")
    app.static("/style/", f"{assets_path}/style/")

    @app.route("/")
    async def index(request):
        index = open(os.path.join(assets_path, "index.html")).read()
        index = re.sub(
            r"{{([^{}]+)}}", lambda m: template.get(m[1], f"!!{m[1]}"), index
        )
        return response.html(index)

    @app.websocket("/sktk")
    async def feed(request, ws):
        sess = Session(ws)
        slock.set(sess)
        if watch_args is not None:
            jurigged.watch(**watch_args, logger=status_logger(sess))
        while True:
            command = json.loads(await ws.recv())
            await sess.recv(**command)

    @app.listener("after_server_start")
    async def launch_func(app, loop):
        webbrowser.open(f"http://localhost:{port}/")

    atexit.register(app.stop)
    app.run(host="0.0.0.0", port=port, register_sys_signals=False)


def serve(**kwargs):
    slock = SessionLock()

    def _start_server():
        _launch(slock, **kwargs)

    thread = threading.Thread(target=_start_server, daemon=True)
    thread.start()

    sess = slock.get()
    sess.enter()
    inject()
    return sess
