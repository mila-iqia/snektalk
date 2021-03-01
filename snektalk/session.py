import asyncio
import builtins
import inspect
import json
import threading
import traceback
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from itertools import count

from hrepr import H, Tag, hrepr

from .registry import callback_registry

_c = count(1)

_current_session = ContextVar("current_session", default=None)
_current_print_session = ContextVar("current_print_session", default=None)
_current_evalid = ContextVar("current_evalid", default=None)


def current_session():
    return _current_session.get()


def current_print_session():
    return _current_print_session.get()


@contextmanager
def new_evalid():
    token = _current_evalid.set(next(_c))
    try:
        yield
    finally:
        _current_evalid.reset(token)


class Session:
    def __init__(self, socket=None):
        self.blt = vars(builtins)
        self.idmap = {}
        self.varcount = count(1)
        self.socket = socket
        self.sent_resources = set()
        self.last_prompt = ""
        self.last_nav = ""
        self.in_queue = deque()
        self.out_queue = deque()
        self.semaphore = threading.Semaphore(value=0)
        self._token = None
        self._tokenp = None

    #############
    # Utilities #
    #############

    def enter(self, capture_print=True):
        self._token = _current_session.set(self)
        if capture_print:
            self._tokenp = _current_print_session.set(self)

    def exit(self):
        _current_session.reset(self._token)
        if self._tokenp:
            _current_print_session.reset(self._tokenp)

    @contextmanager
    def set_context(self):
        token = _current_session.set(self)
        tokenp = _current_print_session.set(self)
        try:
            yield
        finally:
            _current_session.reset(token)
            _current_print_session.reset(tokenp)

    def set_globals(self, glb):
        self.glb = glb

    def newvar(self):
        """Create a new variable."""
        return f"_{next(self.varcount)}"

    def getvar(self, obj):
        """Get the variable name corresponding to the object.

        If the object is not already associated to a variable, one
        will be created and set in the global scope.
        """
        ido = id(obj)
        if ido in self.idmap:
            varname = self.idmap[ido]
        else:
            varname = self.newvar()
            self.idmap[ido] = varname
        self.blt[varname] = obj
        return varname

    def represent(self, typ, result):
        if isinstance(result, Tag):
            return typ, result

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
                typ = "hrepr_exception"
        return typ, html

    ################
    # Proceed/next #
    ################

    def set_prompt(self, prompt):
        if prompt != self.last_prompt:
            self.queue(command="set_mode", html=prompt)

    def set_nav(self, nav):
        if nav != self.last_nav:
            self.queue(command="set_nav", value=hrepr(nav))
            self.last_nav = nav

    @contextmanager
    def prompt(self, prompt="", nav=H.span()):
        self.set_prompt(prompt)
        self.set_nav(nav)
        expr = self.next()
        with self.set_context():
            with new_evalid():
                yield expr

    def next(self):
        self.semaphore.acquire()
        return self.in_queue.popleft()

    ###########
    # Sending #
    ###########

    def bind(self, socket):
        self.loop = asyncio.get_running_loop()
        self.socket = socket
        self.sent_resources = set()
        while self.out_queue:
            self.schedule(self.send(**self.out_queue.popleft()))
        self.submit({"command": "noop"})

    async def send(self, process=True, **command):
        """Send a command to the client, plus any resources.

        Any field that is a Tag and contains resources will send
        resource commands to the client to load these resources.
        A resource is only sent once, the first time it is needed.
        """
        if process:
            resources = []
            for k, v in command.items():
                if isinstance(v, Tag):
                    resources.extend(v.collect_resources())
                    command[k] = str(v)

            for resource in resources:
                if resource not in self.sent_resources:
                    await self.socket.send(
                        json.dumps(
                            {"command": "resource", "value": str(resource)}
                        )
                    )
                    self.sent_resources.add(resource)

            evalid = _current_evalid.get()
            if evalid is not None:
                command["evalid"] = evalid

        await self.socket.send(json.dumps(command))

    def schedule(self, fn):
        self.loop.call_soon_threadsafe(lambda: self.loop.create_task(fn))

    def queue(self, **command):
        """Queue a command to the client, plus any resources.

        This queues the command using the session's asyncio loop.
        """
        if self.socket is None or self.out_queue:
            self.out_queue.append(command)
        else:
            self.schedule(self.send(**command))

    def queue_result(self, result, *, type):
        type, html = self.represent(type, result)
        self.queue(command="result", value=html, type=type)

    ############
    # Commands #
    ############

    def submit(self, data):
        self.in_queue.append(data)
        self.semaphore.release()

    async def recv(self, **command):
        cmd = command.pop("command", "none")
        meth = getattr(self, f"command_{cmd}", None)
        await meth(**command)

    async def command_submit(self, *, expr):
        self.submit({"command": "expr", "expr": expr})

    async def command_callback(self, *, id, response_id, arguments):
        try:
            cb = callback_registry.resolve(int(id))
        except KeyError:
            self.queue(
                command="status",
                type="error",
                value="value is unavailable; it might have been garbage-collected",
            )
            return

        try:
            with self.set_context():
                if inspect.isawaitable(cb):
                    result = await cb(*arguments)
                else:
                    result = cb(*arguments)

            await self.send(
                command="response", value=result, response_id=response_id
            )

        except Exception as exc:
            import traceback

            traceback.print_exc()
            await self.send(
                command="response",
                error={
                    "type": type(exc).__name__,
                    "message": str(exc.args[0]) if exc.args else None,
                },
                response_id=response_id,
            )
