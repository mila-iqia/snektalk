import json
import os

from sanic import Sanic

from .session import Session


here = os.path.dirname(__file__)
assets_path = os.path.join(here, "../assets")


def serve():
    app = Sanic("pythonface")
    app.static("/", f"{assets_path}/index.html")
    app.static("/scripts/", f"{assets_path}/scripts/")
    app.static("/style/", f"{assets_path}/style/")

    @app.websocket("/pf")
    async def feed(request, ws):
        sess = Session({}, ws)

        while True:
            command = json.loads(await ws.recv())
            print("recv", command)
            await sess.recv(**command)

    app.run(host="0.0.0.0", port=6499)
