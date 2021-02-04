from itertools import count

from jurigged import make_recoder, registry

from .utils import format_libpath, represents

_c = count()


class SnekRecoder:
    def __init__(self, recoder, fn):
        self.id = next(_c)
        self.recoder = recoder
        self.filename = recoder.codefile.filename
        self.source = {
            "live": self.recoder.focus.live,
            "saved": self.recoder.focus.saved,
        }
        self.nlocked = 0
        self.fn = fn

    def recode(self, new_source):
        self.recoder.patch(new_source)
        return True

    def replace(self, new_source):
        if self.recode(new_source):
            self.recoder.commit()

    @classmethod
    def __hrepr_resources__(cls, H):
        return H.javascript(export="BackedEditor", src="scripts/edit.js")

    def __hrepr__(self, H, hrepr):
        html = H.div["snek-bedit"](
            constructor="BackedEditor",
            options={
                "funcId": self.id,
                "content": {
                    "live": self.source["live"],
                    "saved": self.source["saved"],
                },
                "filename": format_libpath(self.filename),
                "save": self.recode,
                "commit": self.replace,
                "highlight": hrepr.config.code_highlight,
                "protectedPrefix": self.nlocked,
            },
        )
        return represents(self.fn, html)


def find_fn(fn, module_name="?", qualname="?"):
    recoder = make_recoder(fn)
    return SnekRecoder(recoder, fn)
