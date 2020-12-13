from types import MethodType

from .registry import callback_registry
from .session import session


def join(elems, sep):
    rval = [elems[0]]
    for elem in elems[1:]:
        rval.append(sep)
        rval.append(elem)
    return rval


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
