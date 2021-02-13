from itertools import count

from jurigged import make_recoder

from .utils import Interactor, format_libpath, represents

_c = count()


class SnekRecoder(Interactor):

    js_constructor = "LiveEditor"
    js_source = "/scripts/liveedit.js"

    def __init__(self, recoder, fn, code_highlight=None, max_height=500):
        self.recoder = recoder
        self.fn = fn
        super().__init__(
            {
                "content": {
                    "live": self.recoder.focus.live,
                    "saved": self.recoder.focus.saved,
                },
                "filename": format_libpath(self.recoder.codefile.filename),
                "highlight": code_highlight,
                "max_height": max_height,
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
