import bdb
import os
import re

from hrepr import H
from jurigged import registry

from .evaluator import Evaluator
from .session import current_session
from .utils import ReadOnly, format_libpath

_here = os.path.dirname(__file__)


class SnekTalkDb(bdb.Bdb):
    # Note: Many methods have been lifted from pdb.py in the standard lib
    # and slightly adapted

    def get_globals(self):
        return self.evaluator.get_globals()

    def reset(self):
        super().reset()
        self.session = current_session()
        self.prompt = H.span["snek-input-mode-debug"]("debug>")
        self.nav = ReadOnly(
            {"filename": "", "content": "", "firstlineno": 1, "highlight": 1}
        )
        self.session.set_nav(self.nav)
        self.evaluator = Evaluator(None, {}, {}, self.session)
        self.last_method = (lambda *_: None), None

    def user_line(self, frame):
        if frame.f_code.co_filename.startswith(_here):
            # Avoid running the debugger in snektalk code
            self.set_continue()
        elif getattr(self, "step_now", False):
            self.step_now = False
            self.set_step()
        else:
            self.set_frame(frame)

    def show_frame(self, frame):
        try:
            cf, defn = registry.find(frame.f_code)
        except Exception as exc:
            cf, defn = None, None
        if defn is None:
            self.session.add_nav_action(
                "update",
                lambda: self.nav.js.update(
                    f"'Could not find source code for {frame.f_code.co_name}'"
                ),
            )
        else:
            self.session.add_nav_action(
                "update",
                lambda: self.nav.js.update(
                    defn.codestring,
                    format_libpath(defn.filename),
                    defn.stashed.lineno,
                    frame.f_lineno,
                ),
            )

    def get_frame(self):
        return self.stack[self.current][0]

    def set_frame(self, frame, tb=None):
        self.stack, self.current = self.get_stack(frame, tb)
        self.proceed = False
        while not self.proceed:
            self.show_frame(self.get_frame())
            with self.session.prompt(prompt=self.prompt, nav=self.nav) as cmd:
                if cmd["command"] == "expr":
                    expr = cmd["expr"]
                    self.do(expr)
                elif cmd["command"] == "noop":
                    pass

    def error(self, message):
        print(H.i(message, style="color:red"))

    def do(self, code):
        frame = self.get_frame()
        gs = frame.f_globals
        ls = frame.f_locals
        cmd = None
        if not code.strip():
            method, arg = self.last_method
        else:
            m = re.match(r"^[?!]+", code)
            if m:
                cmd = code[: m.end()]
                arg = code[m.end() :]
            elif " " in code:
                cmd, arg = code.split(" ", 1)
            else:
                cmd = code
                arg = ""
            method = self.__commands__.get(cmd, None)
        if method and cmd != "!":
            self.last_method = method, arg
        if method:
            return method(self, arg, gs, ls)
        else:
            return self.command_print(code, gs, ls)

    def command_print(self, code, gs, ls):
        """<b>p(rint) expression</b>

        Print the value of the expression. Synonyms: !, pp
        """
        self.evaluator.run(code, gs, ls)

    def command_step(self, arg, gs, ls):
        """<b>s(tep)</b>

        Execute the current line, stop at the first possible occasion
        (either in a function that is called or in the current function).
        """
        self.set_step()
        self.proceed = True

    def command_next(self, arg, gs, ls):
        """<b>n(ext)</b>

        Continue execution until the next line in the current function
        is reached or it returns.
        """
        self.set_next(self.get_frame())
        self.proceed = True

    def command_continue(self, arg, gs, ls):
        """<b>c(ont(inue))</b>

        Continue execution, only stop when a breakpoint is encountered.
        """
        self.set_continue()
        self.proceed = True

    def command_return(self, arg, gs, ls):
        """<b>r(eturn)</b>

        Continue execution until the current function returns.
        """
        self.set_return()
        self.proceed = True

    def command_up(self, arg, gs, ls):
        """<b>u(p) [count]</b>

        Move the current frame count (default one) levels up in the
        stack trace (to an older frame).
        """
        if self.current == 0:
            self.error("Oldest frame")
            return
        try:
            count = int(arg or 1)
        except ValueError:
            self.error("Invalid frame count (%s)" % arg)
            return
        if count < 0:
            self.current = 0
        else:
            self.current = max(0, self.current - count)

    def command_down(self, arg, gs, ls):
        """<b>d(own) [count]</b>

        Move the current frame count (default one) levels down in the
        stack trace (to a newer frame).
        """
        if self.current + 1 == len(self.stack):
            self.error("Newest frame")
            return
        try:
            count = int(arg or 1)
        except ValueError:
            self.error("Invalid frame count (%s)" % arg)
            return
        if count < 0:
            self.current = len(self.stack) - 1
        else:
            self.current = min(len(self.stack) - 1, self.current + count)

    def command_help(self, arg, gs, ls):
        """<b>h(elp)</b>

        Without argument, print the list of available commands.
        With a command name as argument, print help about that command.
        """
        if arg:
            html = H.div(style="border:1px solid black; padding: 5px")
            self.session.queue(
                command="result",
                type="print",
                value=html(H.raw(self.__commands__[arg].__doc__)),
            )
        else:
            commands = [x.__doc__ for x in set(self.__commands__.values())]
            commands.sort()
            html = H.div(style="border:1px solid black; padding: 5px")
            for cmd in commands:
                html = html(H.div(H.raw(cmd)))
            self.session.queue(
                command="result", type="print", value=html,
            )

    def command_quit(self, arg, gs, ls):
        """<b>q(uit)</b>

        Quit from the debugger. The program being executed is aborted.
        """
        self._user_requested_quit = True
        self.set_quit()
        self.proceed = True

    def runeval_step(self, expr, glb, lcl):
        self.step_now = True
        return self.runeval(expr, glb, lcl)

    def interaction(self, frame, tb):
        self.reset()
        self.set_frame(frame, tb)

    __commands__ = {
        "step": command_step,
        "s": command_step,
        "next": command_next,
        "n": command_next,
        "continue": command_continue,
        "c": command_continue,
        "return": command_return,
        "r": command_return,
        "up": command_up,
        "u": command_up,
        "down": command_down,
        "d": command_down,
        "print": command_print,
        "p": command_print,
        "pp": command_print,
        "!": command_print,
        "help": command_help,
        "h": command_help,
        "?": command_help,
        "quit": command_quit,
        "q": command_quit,
    }
