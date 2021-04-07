import types
from dataclasses import dataclass
from itertools import count

from jurigged import make_recoder
from ovld import ovld

from ..utils import Interactor, format_libpath, represents

########
# edit #
########


@ovld.dispatch
def edit(self, obj, **kwargs):
    if hasattr(obj, "__snek_edit__"):
        return obj.__snek_edit__(**kwargs)
    else:
        return self[type(obj)](obj, **kwargs)


@ovld
def edit(
    obj: (type, types.FunctionType, types.CodeType, types.ModuleType), **kwargs
):
    recoder = make_recoder(obj)
    return recoder and SnekRecoder(recoder, obj, **kwargs)


######################
# Python code editor #
######################


class SnekRecoder(Interactor):

    js_constructor = "LiveEditor"
    js_source = "/scripts/liveedit.js"

    def __init__(
        self, recoder, fn, code_highlight=None, max_height=500, autofocus=False
    ):
        self.recoder = recoder
        self.fn = fn
        super().__init__(
            {
                "content": {
                    "live": self.recoder.focus.codestring,
                    "saved": self.recoder.focus.stashed.content,
                },
                "filename": format_libpath(self.recoder.codefile.filename),
                "highlight": code_highlight,
                "max_height": max_height,
                "autofocus": autofocus,
            }
        )
        self.recoder.on_status.register(self.on_status)

    def on_status(self, recoder, status):
        if status == "out-of-sync":
            self.js.setStatus("dirty", "out of sync")

    def py_save(self, new_source):
        self.recoder.patch(new_source)
        return True

    def py_commit(self, new_source):
        if self.py_save(new_source):
            self.recoder.commit()
