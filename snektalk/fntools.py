from itertools import count

from jurigged import make_recoder, registry

from .utils import Interactor, format_libpath, represents

_c = count()


class SnekRecoder(Interactor):

    js_constructor = "BackedEditor"
    js_source = "/scripts/edit.js"

    def __init__(self, recoder, fn, code_highlight=None):
        self.recoder = recoder
        self.fn = fn
        self.id = next(_c)
        super().__init__(
            {
                "funcId": self.id,
                "content": {
                    "live": self.recoder.focus.live,
                    "saved": self.recoder.focus.saved,
                },
                "filename": format_libpath(self.recoder.codefile.filename),
                "highlight": code_highlight,
                "protectedPrefix": 0,
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


def find_fn(fn, **kwargs):
    recoder = make_recoder(fn)
    return recoder and SnekRecoder(recoder, fn, **kwargs)
