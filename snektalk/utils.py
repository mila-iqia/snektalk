import os
from itertools import count
from types import FunctionType, MethodType
from typing import Union

from hrepr import H, hjson, hrepr

from .registry import callback_registry
from .session import current_session

_count = count()


##########################
# Special JSON converter #
##########################


@hjson.dump.variant
def _sktk_hjson(self, fn: Union[MethodType, FunctionType]):
    method_id = callback_registry.register(fn)
    return f"$$SKTK({method_id})"


def sktk_hjson(obj):
    return str(_sktk_hjson(obj))


#############
# Utilities #
#############


def join(elems, sep):
    rval = [elems[0]]
    for elem in elems[1:]:
        rval.append(sep)
        rval.append(elem)
    return rval


_path_replacements = {
    "PWD": "",
    "CONDA_PREFIX": "$CONDA_PREFIX/",
    "VIRTUAL_ENV": "$VIRTUAL_ENV/",
    "HOME": "~/",
}


def format_libpath(path):
    for var, pfx in sorted(_path_replacements.items(), key=lambda kv: kv[1]):
        if (val := os.environ.get(var, None)) is not None:
            if not val.endswith("/"):
                val += "/"
            if path.startswith(val):
                return os.path.join(pfx, path[len(val) :])
    else:
        return path


class Importer:
    def __getattr__(self, module_name):
        return __import__(module_name)


class ObjectFields:
    def __init__(self, cls, **fields):
        self.cls = cls
        self.fields = fields

    def __eq__(self, other):
        return (
            type(self) is type(other)
            and self.cls == other.cls
            and self.fields == other.fields
        )


def mod(cls):
    def f(**fields):
        return ObjectFields(cls, **fields)

    return f


###########################
# Click/shift-click logic #
###########################


def pastevar(obj):
    sess = current_session()
    sess.queue(command="pastecode", value=sess.getvar(obj))


def pastecode(code, vars={}):
    sess = current_session()
    ev = sess.active_evaluator()
    if ev is not None:
        for var, (expected, generate) in vars.items():
            if ev.get_globals().get(var, None) is not expected:
                code = f"{generate}\n{code}"
    sess.queue(command="pastecode", value=code)


def newvar(prefix):
    sess = current_session()
    ev = sess.active_evaluator()
    name = prefix
    if ev is not None:
        glb = ev.get_globals()
        i = 2
        while name in glb:
            name = f"{prefix}{i}"
            i += 1
        glb[name] = None
    return name


def findvar(value, prefix="_"):
    sess = current_session()
    ev = sess.active_evaluator()
    if ev is not None:
        glb = ev.get_globals()
        for k, v in glb.items():
            if v is value:
                return k
        name = newvar(prefix)
        glb[name] = value
        return name
    return None


def _default_click(obj, evt):
    if evt.get("shiftKey", False):
        sess = current_session()
        sess.queue(command="result", value=hrepr(obj), type="print")
    else:
        pastevar(obj)


def _safe_set(elem, **props):
    if elem.is_virtual():
        return H.div(elem, **props)
    else:
        return elem(**props)


def represents(obj, elem, pinnable=False):
    if obj is None:
        return elem
    elif elem.get_attribute("objid", None) is not None:
        return _safe_set(elem, pinnable=pinnable)
    else:
        method_id = callback_registry.register(MethodType(_default_click, obj))
        return _safe_set(elem, objid=method_id, pinnable=pinnable)


##############
# Interactor #
##############


class BaseJSCaller:
    def __init__(self, interactor, jsid):
        self._interactor = interactor
        self._jsid = jsid
        self._session = current_session()

    def _getcode(self, method_name, args):
        if not self._interactor:
            raise Exception("The JavaScript interface is not active.")
        argtext = ",".join(map(sktk_hjson, args))
        return f"""
        require(
            ['{self._jsid}'],
            wobj => {{
                let obj = wobj.deref();
                if (obj !== null) {{
                    obj.{method_name}({argtext});
                }}
            }}
        );
        """


class AJSCaller(BaseJSCaller):
    # TODO
    def __getattr__(self, method_name):
        async def call(*args):
            code = self._getcode(method_name, args)
            prom = asyncio.Promise()
            self._session.queue(command="eval", value=code, promise=prom)
            return await prom

        return call


class JSCaller(BaseJSCaller):
    def __init__(self, interactor, jsid, return_hrepr):
        super().__init__(interactor, jsid)
        self._return_hrepr = return_hrepr

    def __getattr__(self, method_name):
        def call(*args):
            code = self._getcode(method_name, args)
            if self._return_hrepr:
                return H.javascript(code)
            else:
                self._session.queue(command="eval", value=code)

        return call


class Interactor:
    js_requires = {}
    js_code = None

    @classmethod
    def show(cls, *args, nav=False, **kwargs):
        instance = cls(*args, **kwargs)
        html = hrepr(instance)
        if nav:
            current_session().queue(command="set_nav", value=html)
        else:
            print(html)
        return instance

    def __init__(self, parameters):
        self.jsid = f"interactor{next(_count)}"
        self.js = JSCaller(self, self.jsid, return_hrepr=False)
        self.hjs = JSCaller(self, self.jsid, return_hrepr=True)
        self.ajs = AJSCaller(self, self.jsid)
        self.parameters = parameters
        methods = {}
        for method_name in dir(self):
            if method_name.startswith("py_"):
                methods[method_name[3:]] = getattr(self, method_name)
        self.parameters["py"] = methods
        self.active = False

    def __bool__(self):
        return self.active

    @classmethod
    def __hrepr_resources__(cls, H):
        js_requires = {
            name: {"url": x, "varname": name} if isinstance(x, str) else x
            for name, x in cls.js_requires.items()
        }

        reqs = [
            H.javascript(export=name, src=data["url"])
            for name, data in js_requires.items()
        ]
        if cls.js_code:
            main = H.javascript(
                cls.js_code,
                require={
                    name: data["varname"] for name, data in js_requires.items()
                },
            )
        else:
            main = H.javascript(src=cls.js_source)
        return [*reqs, main(export=cls.js_constructor)]

    def __hrepr__(self, H, hrepr):
        params = sktk_hjson(self.parameters)
        self.active = True
        tmpid = f"$$tmp{next(_count)}"
        return H.div(
            H.div(id=tmpid),
            H.script(
                f"""
                (() => {{
                    let elem = document.getElementById('{tmpid}');
                    let existing = document.getElementById('{self.jsid}');
                    if (existing && existing.handler) {{
                        // Move the existing div
                        elem.parentElement.replaceChild(
                            existing, elem
                        );
                    }}
                    else {{
                        elem.id = '{self.jsid}';
                        requirejs.undef('{self.jsid}');
                        define(
                            '{self.jsid}',
                            ['{self.js_constructor}'],
                            ctor => {{
                                let obj = new ctor(elem, {params});
                                elem.handler = obj;
                                return new WeakRef(obj);
                            }}
                        );
                        require(['{self.jsid}'], _ => null);
                    }}
                }})();
                """
            ),
        )


####################
# Misc interactors #
####################


class ReadOnly(Interactor):
    js_constructor = "ReadOnlyEditor"
    js_source = "/scripts/readonly.js"
