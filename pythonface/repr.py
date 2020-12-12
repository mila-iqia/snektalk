import builtins
from types import FunctionType, MethodType, ModuleType

from hrepr import H, Hrepr, Tag, hjson, hrepr, standard_html

from .fntools import fnedit
from .registry import callback_registry
from .session import session

##########################
# Special JSON converter #
##########################


@hjson.dump.variant
def _pf_hjson(self, fn: (MethodType, FunctionType)):
    method_id = callback_registry.register(fn)
    return f"$$PFCB({method_id},this,event)"


def pf_hjson(obj):
    return str(_pf_hjson(obj))


####################
# PythonFace print #
####################


orig_print = print


class PrintSequence(tuple):
    def __hrepr__(self, H, hrepr):
        return H.div["pf-print-sequence"](
            *[H.div(hrepr(x)) for x in self], onclick=False
        )


def pfprint(*args, **kwargs):
    builtins.print = orig_print
    sess = session.get()
    if sess is None:
        orig_print(*args, **kwargs)
    else:
        if all(isinstance(arg, str) for arg in args):
            html = H.div["pf-print-str"](" ".join(args))
        else:
            html = hrepr(PrintSequence(args), **kwargs)
        sess.queue(
            command="result",
            value=html,
            type="print",
        )
    builtins.print = pfprint


class HDir:
    exclusions = {"__doc__", "__dict__"}

    def __init__(self, obj):
        self.obj = obj

    def items(self):
        for k in dir(self.obj):
            if k in self.exclusions:
                continue
            try:
                v = getattr(self.obj, k)
            except Exception as e:
                v = e
            yield (k, v)

    def __hrepr__(self, H, hrepr):
        exclusions = {"__doc__", "__dict__"}
        return H.table["hrepr-body"](
            *[H.tr(H.td(k), H.td(" = ", hrepr(v))) for k, v in self.items()]
        )


def hdir(obj):
    return hrepr(HDir(obj), max_depth=2)


###############################
# Add default onclick handler #
###############################


def _default_click(obj, evt):
    ctx = session.get()
    if evt.get("shiftKey", False):
        ctx.queue(
            command="result",
            value=hrepr(obj),
            type="print",
        )
    else:
        varname = ctx.session.getvar(obj)
        ctx.queue(
            command="pastevar",
            value=varname,
        )


def join(elems, sep):
    rval = [elems[0]]
    for elem in elems[1:]:
        rval.append(sep)
        rval.append(elem)
    return rval


def represents(obj, elem, pinnable=False):
    if obj is None:
        return elem
    else:
        method_id = callback_registry.register(MethodType(_default_click, obj))
        return elem(objid=method_id, pinnable=pinnable)


def wrap_onclick(elem, obj, hrepr):
    if not isinstance(obj, Tag) and hrepr.config.interactive is not False:
        return represents(obj, elem, pinnable=True)
    else:
        return elem


class PFHrepr(Hrepr):
    def collapsible(self, title, body, start_visible=False):
        body = self.H.div(self(body))
        if not start_visible:
            body = body["pf-hidden"]
        return self.H.div["pf-collapsible"](
            self.H.div["pf-collapsible-title"](
                title,
                onclick="this.nextSibling.classList.toggle('pf-hidden')",
            ),
            body,
        )

    def hrepr(self, exc: Exception):
        exc_proper = self.H.div["hrepr-error", "hrepr-instance", "hreprl-h"](
            self.H.div["hrepr-title"](type(exc).__name__),
            self.H.div["hrepr-error-message"](
                self.H.code(exc.args[0]),
            ),
        )

        if self.state.depth > 0:
            return exc_proper

        tb = exc.__traceback__
        parts = []
        curr = tb
        while curr:
            fr = curr.tb_frame
            code = fr.f_code
            hl = curr.tb_lineno - code.co_firstlineno
            ed = fnedit(code, highlight=hl)
            parts.append(
                self.collapsible(
                    self.H.div["pf-title-row"](
                        self.H.span(code.co_name),
                        self.H.span(f"{code.co_filename}:{fr.f_lineno}"),
                    ),
                    self(ed) if ed else self.H.span("Could not find source"),
                )
            )
            curr = curr.tb_next

        return self.H.div["hrepr-body"](*parts, exc_proper)

    def hrepr(self, fn: FunctionType):
        if self.state.depth == 0:
            ed = fnedit(fn)
            if ed is None:
                return NotImplemented
            return self.H.div(self(ed))
        else:
            return NotImplemented

    def hrepr(self, mod: ModuleType):
        exclusions = {
            "__builtins__",
            "__name__",
            "__doc__",
            "__path__",
            "__file__",
            "__cached__",
            "__package__",
            "__loader__",
            "__spec__",
            "__all__",
            "__author__",
        }
        if self.state.depth == 0:
            return self.H.instance(
                self.H.pre(mod.__doc__.strip()) if mod.__doc__ else "",
                *[
                    self.H.pair(
                        represents(value, self.H.span(name)),
                        self(value, max_depth=2),
                        delimiter="=",
                    )
                    for name, value in sorted(vars(mod).items())
                    if name not in exclusions
                ],
                type=self.H.span(
                    self.H.span["pf-block-type"]("module "), mod.__name__
                ),
                vertical=True,
            )
        else:
            return NotImplemented

    def hrepr(self, cls: type):
        if self.state.depth > 0:
            return NotImplemented

        exclusions = {"__dict__", "__module__", "__weakref__", "__doc__"}

        # Exclude the object type to reduce noise
        mro = list(type.mro(cls))[:-1]

        rows = {}
        clselems = []
        for cls2 in mro:
            clsname = cls2.__qualname__
            clselem = represents(cls2, self.H.span(clsname))
            clselems.append(clselem)
            for name, value in vars(cls2).items():
                if name not in rows and name not in exclusions:
                    rows[name] = (
                        name,
                        clsname,
                        clselem,
                        represents(value, self.H.span(name)),
                        value,
                    )

        rows = list(rows.values())
        rows.sort(key=lambda row: row[0])

        tbl = self.H.table["hrepr-body"]()

        doc = getattr(cls, "__doc__", None)
        if doc:
            tbl = tbl(self.H.tr(self.H.td(self.H.pre(doc), colspan=3)))

        for _, clsname, clselem, nameelem, value in rows:
            css_class = (
                "pf-clsname-principal"
                if clsname == cls.__name__
                else "pf-clsname"
            )
            tbl = tbl(
                self.H.tr(
                    self.H.td[css_class](clselem, "."),
                    self.H.td(nameelem),
                    self.H.td("= ", self(value)),
                )
            )

        title = self.H.span(
            self.H.span["pf-block-type"]("class "), *join(clselems, " > ")
        )

        return self.H.instance(
            tbl,
            type=title,
            vertical=True,
        )


#####################################
# Inject changes into default hrepr #
#####################################


def inject():
    builtins.print = pfprint
    builtins.hdir = hdir
    hrepr.configure(
        mixins=PFHrepr,
        postprocess=wrap_onclick,
        backend=standard_html.copy(
            initial_state={
                "hjson": pf_hjson,
                "requirejs_resources": [],
            }
        ),
    )
