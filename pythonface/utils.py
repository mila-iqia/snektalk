from hrepr import H, hjson, hrepr
from types import FunctionType, MethodType

from .registry import callback_registry
from .session import session


##########################
# Special JSON converter #
##########################


@hjson.dump.variant
def _pf_hjson(self, fn: (MethodType, FunctionType)):
    method_id = callback_registry.register(fn)
    return f"$$PFCB({method_id})"


def pf_hjson(obj):
    return str(_pf_hjson(obj))


#############
# Utilities #
#############


def join(elems, sep):
    rval = [elems[0]]
    for elem in elems[1:]:
        rval.append(sep)
        rval.append(elem)
    return rval


###########################
# Click/shift-click logic #
###########################


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


def represents(obj, elem, pinnable=False):
    if obj is None:
        return elem
    elif elem.get_attribute("objid", None) is not None:
        return elem(pinnable=pinnable)
    else:
        method_id = callback_registry.register(MethodType(_default_click, obj))
        return elem(objid=method_id, pinnable=pinnable)
