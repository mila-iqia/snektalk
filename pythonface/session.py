import asyncio
import builtins
import inspect
import json
import traceback
from contextlib import contextmanager
from contextvars import ContextVar
from itertools import count

from hrepr import H, Tag, hrepr

from .registry import UNAVAILABLE, callback_registry

_c = count()

session = ContextVar("session", default=None)

sessions = {}


class Evaluator:
    def __init__(self, session):
        self.session = session
        self.evalid = next(_c)

    @contextmanager
    def push_context(self):
        token = session.set(self)
        try:
            yield
        finally:
            session.reset(token)

    def eval(self, expr):
        with self.push_context():
            try:
                return eval(expr, self.session.glb)
            except SyntaxError:
                exec(expr, self.session.glb)
                return None

    def queue(self, **command):
        self.session.loop.create_task(
            self.session.send(**command, evalid=self.evalid)
        )


class Session:
    def __init__(self, glb, socket):
        self.glb = glb
        self.idmap = {}
        self.varcount = count(1)
        self.socket = socket
        self.sent_resources = set()
        self.loop = asyncio.get_running_loop()

    def getvar(self, obj):
        ido = id(obj)
        if ido in self.idmap:
            varname = self.idmap[ido]
        else:
            varname = self.newvar()
            self.idmap[ido] = varname
        self.glb[varname] = obj
        return varname

    def newvar(self):
        return f"_{next(self.varcount)}"

    async def direct_send(self, **command):
        await self.socket.send(json.dumps(command))

    async def send(self, **command):
        resources = []
        for k, v in command.items():
            if isinstance(v, Tag):
                resources.extend(v.collect_resources())
                command[k] = str(v)

        for resource in resources:
            if resource not in self.sent_resources:
                await self.socket.send(
                    json.dumps(
                        {
                            "command": "resource",
                            "value": str(resource),
                        }
                    )
                )
                self.sent_resources.add(resource)

        await self.socket.send(json.dumps(command))

    async def send_result(self, result, *, type, evalid):
        try:
            html = hrepr(result)
        except Exception as exc:
            try:
                html = hrepr(exc)
            except Exception:
                html = H.pre(
                    traceback.format_exception(
                        builtins.type(exc), exc, exc.__traceback__
                    )
                )

        await self.send(
            command="result",
            value=html,
            type=type,
            evalid=evalid,
        )

    async def recv(self, **command):
        cmd = command.pop("command", "none")
        meth = getattr(self, f"command_{cmd}", None)
        await meth(**command)

    async def command_submit(self, *, expr):
        ev = Evaluator(self)

        try:
            result = ev.eval(expr)
            typ = "statement" if result is None else "expression"
        except Exception as e:
            result = e
            typ = "exception"

        self.glb["_"] = result

        await self.direct_send(
            command="echo",
            value=expr,
        )

        await self.send_result(
            result,
            type=typ,
            evalid=ev.evalid,
        )

    async def command_callback(self, *, id, response_id, arguments):
        ev = Evaluator(self)

        try:
            cb = callback_registry.resolve(int(id))
        except KeyError:
            ev.queue(
                command="result",
                value=hrepr(UNAVAILABLE),
            )
            return

        try:
            with ev.push_context():
                if inspect.isawaitable(cb):
                    result = await cb(*arguments)
                else:
                    result = cb(*arguments)

            await self.send(
                command="response",
                value=result,
                response_id=response_id,
            )

        except Exception as exc:
            await self.send(
                command="response",
                error={
                    "type": type(exc).__name__,
                    "message": str(exc.args[0]) if exc.args else None,
                },
                response_id=response_id,
            )
