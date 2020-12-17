from hrepr import H

class Evaluator:
    def __init__(self, session):
        self.session = session
        self.glb = session.glb

    def eval(self, expr, glb=None, lcl=None):
        if glb is None:
            glb = self.session.glb
        try:
            return eval(expr, glb, lcl)
        except SyntaxError:
            exec(expr, glb, lcl)
            return None

    def run(self, thing, glb=None, lcl=None):
        if isinstance(thing, str):
            self.session.schedule(
                self.session.direct_send(
                    command="echo",
                    value=thing,
                )
            )

        try:
            if isinstance(thing, str):
                result = self.eval(thing, glb, lcl)
                typ = "statement" if result is None else "expression"
            else:
                result = thing()
                typ = "expression"
        except Exception as e:
            result = e
            typ = "exception"

        self.session.blt["_"] = result

        self.session.schedule(self.session.send_result(result, type=typ))

    def loop(self):
        while True:
            prompt = H.span["pf-input-mode-python"](">>>")
            with self.session.prompt(prompt) as cmd:
                expr = cmd["expr"]
                if not isinstance(expr, str) or expr.strip():
                    self.run(expr)
