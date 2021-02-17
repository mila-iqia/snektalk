import ast
import functools
import re
from types import ModuleType

from hrepr import H
from jurigged import CodeFile, registry
from jurigged.recode import virtual_file

from .fntools import find_fn

cmd_rx = re.compile(r"/([^ ]+)( .*)?")


def safe_fail(fn):
    @functools.wraps(fn)
    def deco(self, *args, **kwargs):
        try:
            fn(self, *args, **kwargs)
        except Exception as e:
            self.session.schedule(self.session.send_result(e, type="exception"))

    return deco


class Evaluator:
    def __init__(self, module, glb, lcl, session):
        self.session = session
        if module is None:
            module = ModuleType("__main__")
            module.__dict__.update(glb)
        self.module = module
        self.glb = glb
        self.lcl = lcl

    def eval(self, expr, glb=None, lcl=None):
        if glb is None:
            glb = self.glb
        if lcl is None:
            lcl = self.lcl

        filename = virtual_file("repl", expr)
        cf = CodeFile(filename=filename, source=expr)
        registry.cache[filename] = cf

        tree = ast.parse(expr)
        assert isinstance(tree, ast.Module)
        assert len(tree.body) > 0
        *body, last = tree.body
        if isinstance(last, ast.Expr):
            last = ast.Expression(last.value)
        else:
            body.append(last)
            last = None
        for stmt in body:
            compiled = compile(
                ast.Module(body=[stmt], type_ignores=[]),
                mode="exec",
                filename=filename,
            )
            exec(compiled, glb, lcl)
        if last:
            compiled = compile(last, mode="eval", filename=filename)
            rval = eval(compiled, glb, lcl)
        else:
            rval = None

        cf.discover(lcl, filename)
        return rval

    @safe_fail
    def command_eval(self, expr, glb=None, lcl=None):
        assert isinstance(expr, str)

        self.session.schedule(
            self.session.direct_send(command="echo", value=expr)
        )

        result = self.eval(expr, glb, lcl)
        typ = "statement" if result is None else "expression"

        self.session.blt["_"] = result

        self.session.schedule(self.session.send_result(result, type=typ))

    @safe_fail
    def command_edit(self, expr, glb, lcl):
        expr = expr.lstrip()
        obj = self.eval(expr, glb, lcl)
        self.session.schedule(
            self.session.send_result(find_fn(obj), type="expression")
        )

    def missing(self, expr, cmd, arg, glb, lcl):
        self.session.schedule(
            self.session.direct_send(command="echo", value=expr)
        )
        self.session.schedule(
            self.session.send_result(
                H.div(f"Command '{cmd}' does not exist"), type="exception"
            )
        )

    def dispatch(self, expr, glb=None, lcl=None):
        if match := cmd_rx.fullmatch(expr):
            cmd, arg = match.groups()
            if arg is None:
                arg = ""
        else:
            cmd = "eval"
            arg = expr

        method = getattr(self, f"command_{cmd}", None)
        if method is None:
            self.missing(expr, cmd, arg, glb, lcl)
        else:
            method(arg, glb, lcl)

    def loop(self):
        while True:
            prompt = H.span["snek-input-mode-python"](">>>")
            with self.session.prompt(prompt) as cmd:
                expr = cmd["expr"]
                if expr.strip():
                    self.dispatch(expr)

    run = command_eval
