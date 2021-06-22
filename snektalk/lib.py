import builtins
import os
from types import SimpleNamespace

from hrepr import H, Tag, hrepr, standard_html
from hrepr.h import HType
from hrepr.std import _extract_as

from .debug import SnekTalkDb
from .feat.edit import edit
from .repr import SnekTalkHrepr
from .session import current_print_session, current_session
from .utils import Importer, mod, pastevar, represents, sktk_hjson

##################
# SnekTalk print #
##################


here = os.path.dirname(__file__)
orig_print = print


class PrintSequence(tuple):
    def __hrepr__(self, H, hrepr):
        return H.div["snek-print-sequence"](
            *[H.div(hrepr(x)) for x in self], onclick=False
        )


def snekprint(*args, toplevel=False, to=None, **kwargs):
    sess = current_print_session()
    if sess is None:
        orig_print(*args)
    elif to is not None:
        if toplevel:
            html = hrepr(*args, **kwargs)
        else:
            html = hrepr(PrintSequence(args), **kwargs)
        sess.queue(
            command="insert", value=html, target=to,
        )
    else:
        if all(isinstance(arg, str) for arg in args):
            html = H.div["snek-print-str"](" ".join(args))
        elif toplevel:
            html = hrepr(*args, **kwargs)
        else:
            html = hrepr(PrintSequence(args), **kwargs)
        sess.queue(
            command="result", value=html, type="print",
        )


def snekprint_override(*args, toplevel=False, file=None, std=False, **kwargs):
    builtins.print = orig_print
    sess = current_print_session()
    if sess is None or std or file is not None:
        orig_print(*args, file=file, **kwargs)
    else:
        snekprint(*args, toplevel=toplevel, **kwargs)
    builtins.print = snekprint_override


def insert_at(target, value, index=None, **kwargs):
    html = hrepr(value, **kwargs)
    sess = current_session()
    sess.queue(command="insert", value=html, target=target, index=index)


def fill_at(target, value, **kwargs):
    html = hrepr(value, **kwargs)
    sess = current_session()
    sess.queue(command="fill", value=html, target=target)


def clear_at(target):
    sess = current_session()
    sess.queue(command="clear", target=target)


def help_placeholder(*args, **kwargs):
    print(
        H.span("The help command is not available in snektalk for the moment.")
    )


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
        return H.table["hrepr-body"](
            *[H.tr(H.td(k), H.td(" = ", hrepr(v))) for k, v in self.items()]
        )


def hdir(obj):
    return hrepr(HDir(obj), max_depth=2)


###########################
# Default onclick handler #
###########################


def wrap_onclick(elem, obj, hrepr):
    if not isinstance(obj, Tag) and hrepr.config.interactive is not False:
        return represents(obj, elem, pinnable=True)
    else:
        return elem


#####################################
# Inject changes into default hrepr #
#####################################


sktk = SimpleNamespace(
    edit=edit,
    help=None,
    imp=Importer(),
    mod=mod,
    fill_at=fill_at,
    insert_at=insert_at,
    clear_at=clear_at,
    pastevar=pastevar,
)


def snekbreakpoint():
    SnekTalkDb().set_trace()


@standard_html.variant(
    initial_state={"hjson": sktk_hjson, "requirejs_resources": []}
)
def sktk_html(self, node: HType.include):
    _, children, data = _extract_as(self, node, "include", path=None, type=None)
    if data.type is None or data.path is None:
        raise TypeError("H.include must have a type and a path")

    path = os.path.expanduser(data.path)
    path = os.path.abspath(path)

    if data.type == "text/css":
        return H.link(rel="stylesheet", href=f"/fs{path}")
    elif data.type == "text/javascript":
        return H.script(type="text/javascript", src=f"/fs{path}")
    else:
        raise TypeError(f"Cannot include type '{data.type}'")


def inject():
    builtins.help = help_placeholder
    builtins.print = snekprint_override
    builtins.breakpoint = snekbreakpoint
    builtins.hdir = hdir
    builtins.print0 = orig_print
    builtins.sktk = sktk
    hrepr.configure(
        mixins=SnekTalkHrepr, postprocess=wrap_onclick, backend=sktk_html,
    )
