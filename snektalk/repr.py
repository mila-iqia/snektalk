import os
import types
from types import FunctionType, MethodType, ModuleType
from typing import Union

from hrepr import H
from ovld import OvldBase, extend_super

from .feat.edit import edit
from .utils import format_libpath, join, represents

here = os.path.dirname(__file__)


def shortname(obj):
    return getattr(obj, "__name__", f"<{type(obj).__name__}>")


class SnekTalkHrepr(OvldBase):
    def collapsible(self, title, body, start_visible=False):
        body = self.H.div(self(body))
        if not start_visible:
            body = body["snek-hidden"]
        return self.H.div["snek-collapsible"](
            self.H.div["snek-collapsible-title"](
                title,
                onclick="this.nextSibling.classList.toggle('snek-hidden')",
            ),
            body,
        )

    @extend_super
    def hrepr(self, exc: Exception):
        exc_proper = self.H.div["hrepr-error", "hrepr-instance", "hreprl-h"](
            self.H.div["hrepr-title"](type(exc).__name__),
            self.H.div["hrepr-error-message"](self.H.code(str(exc))),
        )

        if self.state.depth > 0:
            return exc_proper

        tb = exc.__traceback__
        skipping = not self.config.include_snektalk_frames
        parts = []
        curr = tb
        while curr:
            fr = curr.tb_frame
            code = fr.f_code
            filename = code.co_filename
            if filename.startswith(here) and skipping:
                curr = curr.tb_next
                continue
            skipping = False
            if filename.startswith(os.getcwd()) or filename.startswith("<"):
                importance_class = "snek-exception-local"
            else:
                importance_class = "snek-exception-lib"

            hl = curr.tb_lineno - code.co_firstlineno
            try:
                ed = edit(code, code_highlight=hl, max_height=19 * 7)
            except Exception as exc:
                ed = None
            parts.append(
                self.collapsible(
                    self.H.div["snek-title-row", importance_class](
                        self.H.span(code.co_name),
                        self.H.span(
                            f"{format_libpath(filename)}:{fr.f_lineno}"
                        ),
                    ),
                    self(ed)
                    if ed is not None
                    else self.H.span("Could not find source"),
                )
            )
            curr = curr.tb_next

        return self.H.div["hrepr-body"](*parts, exc_proper)

    def hrepr(self, r: range):  # noqa: F811
        rval = self.H.instance(self(r.start), self(r.stop), type="range")
        if r.step != 1:
            rval = rval(self(r.step))
        return rval

    def hrepr(self, fn: types.BuiltinFunctionType):  # noqa: F811
        if self.state.depth == 0:
            return H.instance(
                H.pre["snek-docstring"](fn.__doc__),
                type=fn.__name__,
                vertical=True,
            )
        else:
            return NotImplemented

    def hrepr(self, fn: FunctionType):  # noqa: F811
        if self.state.depth == 0:
            ed = edit(fn)
            if ed is None:
                return NotImplemented
            return self(ed)
        else:
            return NotImplemented

    def hrepr(self, fn: MethodType):  # noqa: F811
        if self.state.depth == 0:
            ed = edit(fn.__func__)
            if ed is None:
                return NotImplemented
            return H.instance(
                self(ed), type=self.hrepr_short(fn), vertical=True
            )
        else:
            return NotImplemented

    def hrepr(self, mod: ModuleType):  # noqa: F811
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
                    self.H.span["snek-block-type"]("module "), mod.__name__
                ),
                vertical=True,
            )
        else:
            return NotImplemented

    def hrepr(self, cls: type):  # noqa: F811
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
                "snek-clsname-principal"
                if clsname == cls.__name__
                else "snek-clsname"
            )
            tbl = tbl(
                self.H.tr(
                    self.H.td[css_class](clselem, "."),
                    self.H.td(nameelem),
                    self.H.td("= ", self(value)),
                )
            )

        title = self.H.span(
            self.H.span["snek-block-type"]("class "), *join(clselems, " > ")
        )

        return self.H.instance(tbl, type=title, vertical=True)

    @extend_super
    def hrepr_short(self, clsm: Union[classmethod, staticmethod]):  # noqa: F811
        return self.H.defn(type(clsm).__name__, shortname(clsm.__func__))

    def hrepr(self, clsm: Union[classmethod, staticmethod]):  # noqa: F811
        fn = clsm.__func__
        if self.state.depth == 0 and isinstance(fn, FunctionType):
            ed = edit(fn)
            if ed is None:
                return NotImplemented
            return self.H.div(self(ed))
        else:
            return NotImplemented

    def hrepr_short(self, prop: property):  # noqa: F811
        return self.H.defn(
            type(prop).__name__, shortname(prop.fget or prop.fset or prop.fdel)
        )

    def hrepr(self, prop: property):  # noqa: F811
        if self.state.depth == 0:
            title = "property"
            return self.H.instance(
                H.pair("fget", self(edit(prop.fget)), delimiter="="),
                H.pair("fset", self(edit(prop.fset)), delimiter="="),
                H.pair("fdel", self(edit(prop.fdel)), delimiter="="),
                type=title,
                vertical=True,
            )
        else:
            return NotImplemented
