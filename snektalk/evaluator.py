import ast

from hrepr import H
from jurigged import CodeFile, registry
from jurigged.recode import virtual_file


class Evaluator:
    def __init__(self, session):
        self.session = session

    def eval(self, expr, glb=None, lcl=None):
        if glb is None:
            glb = self.session.glb

        filename = virtual_file("repl", expr)
        cf = CodeFile(filename=filename, source=expr)
        cf.discover(self.session.module)
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
        cf.discover(self.session.module)
        return rval

    def run(self, thing, glb=None, lcl=None):
        if isinstance(thing, str):
            self.session.schedule(
                self.session.direct_send(command="echo", value=thing)
            )

        try:
            if isinstance(thing, str):
                result = self.eval(thing, glb, lcl)
            else:
                result = thing()
            typ = "statement" if result is None else "expression"
        except Exception as e:
            result = e
            typ = "exception"

        self.session.blt["_"] = result

        self.session.schedule(self.session.send_result(result, type=typ))

    def loop(self):
        while True:
            prompt = H.span["snek-input-mode-python"](">>>")
            with self.session.prompt(prompt) as cmd:
                expr = cmd["expr"]
                if not isinstance(expr, str) or expr.strip():
                    self.run(expr)
