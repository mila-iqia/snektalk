import builtins
from types import FunctionType, MethodType

from hrepr import Hrepr, hjson, hrepr, standard_html

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
        html = hrepr(PrintSequence(args), **kwargs)
        sess.queue(
            command="result",
            value=html,
            type="print",
        )
    builtins.print = pfprint


###############################
# Add default onclick handler #
###############################


def _default_click(obj, evt):
    ctx = session.get()
    varname = ctx.session.getvar(obj)
    ctx.queue(
        command="pastevar",
        value=varname,
    )


def wrap_onclick(elem, obj, hrepr):
    if obj is not None:
        method_id = callback_registry.register(MethodType(_default_click, obj))
        return elem(objid=method_id, pinnable=True)
    else:
        return elem


class Goodies(Hrepr):
    pass


#####################################
# Inject changes into default hrepr #
#####################################


def inject():
    builtins.print = pfprint
    hrepr.configure(
        mixins=Goodies,
        postprocess=wrap_onclick,
        backend=standard_html.copy(initial_state={
            "hjson": pf_hjson,
            "requirejs_resources": [],
        }),
    )
