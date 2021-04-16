import asyncio
import builtins
import ctypes
import inspect
import json
import os
import random
import re
import threading
import traceback
from collections import defaultdict, deque
from contextlib import contextmanager
from contextvars import ContextVar
from itertools import count

from hrepr import H, Tag, hrepr

from .config import mayread, maywrite
from .registry import callback_registry

_c = count(1)


class NoPatternException(Exception):
    pass


class CommandDispatcher:
    def __init__(self, patterns):
        self.patterns = [
            (re.compile(pattern, re.MULTILINE | re.DOTALL), fn)
            for pattern, fn in patterns.items()
        ]

    def __call__(self, expr):
        for (pattern, fn) in self.patterns:
            if m := pattern.fullmatch(expr):
                try:
                    return fn(m[0], *m.groups())
                except NotImplementedError:
                    continue
        else:
            raise NoPatternException(f"'{expr}' matches no known pattern")


class ThreadKilledException(Exception):
    pass


class SnektalkInterrupt(Exception):
    pass


def kill_thread(thread, exctype=ThreadKilledException):
    ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_long(thread.ident), ctypes.py_object(exctype)
    )


class KillableThread(threading.Thread):
    @property
    def dead(self):
        return not self.is_alive() or getattr(self, "_dead", False)

    kill = kill_thread


class NamedThreads:
    @classmethod
    def current(cls):
        thread = threading.current_thread()
        if isinstance(thread, KillableThread):
            return thread
        else:
            return None

    def __init__(self):
        self.words = [
            word
            for word in open(
                os.path.join(os.path.dirname(__file__), "words.txt")
            )
            .read()
            .split("\n")
            if word
        ]
        random.shuffle(self.words)
        self.threads = {}
        self.count = count(1)

    def run_in_thread(self, fn, session):
        def run():
            reason = " finished"
            self.threads[word] = thread
            with session.set_context():
                with new_evalid():
                    session.queue_result(
                        H.div("Starting thread ", H.strong(word)), type="info",
                    )
                    try:
                        fn()
                    except ThreadKilledException:
                        reason = " killed"
                    except Exception as e:
                        session.queue_result(e, type="exception")
                    finally:
                        thread._dead = True
                        session._clean_owners()
                        del self.threads[word]
                        self.words.append(word)
                        session.queue_result(
                            H.div("Thread ", H.strong(word), reason),
                            type="info",
                        )

        thread = KillableThread(target=run, daemon=True)

        if not self.words:
            self.words.append(f"t{next(self.count)}")
        word = self.words.pop()

        thread.start()
        return word, thread


threads = NamedThreads()
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


class Lib:
    def __init__(self, session):
        self._export = None
        self.session = session

    def method_stop(self):
        thread = self.session.owner or threading.main_thread()
        kill_thread(thread, SnektalkInterrupt)

    def export(self):
        if self._export:
            return self._export

        self._export = rval = {}
        for method_name in dir(type(self)):
            if method_name.startswith("method_"):
                method = getattr(self, method_name)
                method_id = callback_registry.register(method)
                rval[method_name[7:]] = method_id

        return rval


class Session:
    def __init__(self, socket=None, history_file=None):
        self.lib = Lib(self)
        self.blt = vars(builtins)
        self.idmap = {}
        self.varcount = count(1)
        self.socket = socket
        self.sent_resources = set()
        self.last_prompt = ""
        self.last_nav = ""
        self.in_queue = deque()
        self.out_queue = deque()
        self.semaphores = defaultdict(lambda: threading.Semaphore(value=0))
        self.navs = {}
        self.owners = []
        self.history_file = history_file
        self.history = mayread(history_file, default=[])
        self.dispatch = CommandDispatcher(
            {
                "/attach[ \n]?(.*)": self.submit_command_attach,
                "/detach[ \n]?(.*)": self.submit_command_detach,
                "/kill[ \n]?(.*)": self.submit_command_kill,
            }
        )
        self._token = None
        self._tokenp = None

    #############
    # Utilities #
    #############

    @property
    def owner(self):
        return self.owners[-1] if self.owners else None

    def _clean_owners(self):
        while self.owners and (curr := self.owners[-1]) and curr.dead:
            del self.navs[curr]
            self.pop_owner()

    def _acquire_all(self):
        current = self.semaphores[self.owner]
        while current.acquire(blocking=False):
            pass

    def _release_all(self):
        current = self.semaphores[self.owner]
        if self.in_queue:
            current.release(len(self.in_queue))

    def _current_prompt(self):
        for act in self.navs.get(self.owner, []):
            act()

    def push_owner(self, thread):
        self._acquire_all()
        self.owners.append(thread)
        self._release_all()
        self._current_prompt()

    def pop_owner(self):
        self._acquire_all()
        if self.owners:
            self.owners.pop()
        self._release_all()
        self._current_prompt()

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
        self.add_nav_action(lambda: self.queue(command="set_mode", html=prompt))

    def set_nav(self, nav):
        self.add_nav_action(
            lambda: self.queue(command="set_nav", value=hrepr(nav))
        )

    def add_nav_action(self, action):
        self.navs.setdefault(NamedThreads.current(), []).append(action)

    @contextmanager
    def prompt(self, prompt="", nav=H.span()):
        self.set_prompt(prompt)
        self.set_nav(nav)
        self._clean_owners()
        self._current_prompt()
        expr = self.next()
        with self.set_context():
            with new_evalid():
                yield expr

    def next(self):
        self.semaphores[NamedThreads.current()].acquire()
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
        self.queue(command="add_history", history=self.history)
        self.queue(command="set_lib", lib=self.lib.export())
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

    def submit_command_attach(self, expr, tname):
        tname = tname.strip()
        self.queue(command="echo", value=expr, process=False)
        if tname == "main":
            self.push_owner(None)
        elif tname in threads.threads:
            thread = threads.threads[tname]
            self.push_owner(thread)
        else:
            self.queue(
                command="result",
                value=f"No thread named {tname}"
                if tname
                else "Please provide the name of the thread to attach to",
                type="exception",
            )

    def submit_command_detach(self, expr, arg):
        self.queue(command="echo", value=expr, process=False)
        assert not arg.strip()
        self.pop_owner()

    def submit_command_kill(self, expr, tname):
        tname = tname.strip()
        self.queue(command="echo", value=expr, process=False)
        if tname in threads.threads:
            thread = threads.threads[tname]
            thread.kill()
            self.queue(
                command="result",
                value=f"Sent an exception to {tname}. It should terminate as soon as possible.",
                type="print",
            )
        else:
            self.queue(
                command="result",
                value=f"No thread named {tname}"
                if tname
                else "Please provide the name of the thread to kill",
                type="exception",
            )

    def submit(self, data):
        self.in_queue.append(data)
        self.semaphores[self.owner].release()

    async def recv(self, **command):
        cmd = command.pop("command", "none")
        meth = getattr(self, f"command_{cmd}", None)
        await meth(**command)

    async def command_submit(self, *, expr):
        if expr.strip():
            self.history.append(expr)
        try:
            self.dispatch(expr)
        except NoPatternException:
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
                if inspect.isawaitable(cb) or inspect.iscoroutinefunction(cb):
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

    def atexit(self):
        maywrite(self.history_file, self.history[:1000])
