import ast
import inspect
import sys
import textwrap
import weakref
from collections import defaultdict
from itertools import count
from types import CodeType, FunctionType

_c = count()
filename_to_module = {}
codefiles = {}


def _map_filenames():
    # TODO: there's probably a hook that we can use to automatically analyze
    # modules when they are imported.
    for mod in sys.modules.values():
        fname = getattr(mod, "__file__", None)
        if fname:
            filename_to_module[fname] = mod


class Function:
    def __init__(self, codefile, fn):
        self.id = next(_c)
        self.fn = fn
        self.name = fn.__name__
        self.orig_code = fn.__code__
        self.glb = fn.__globals__
        self.filename = codefile.filename
        src = inspect.getsource(fn)
        self.source = {
            "saved": src,
            "live": src,
        }

    def recode(self, new_code):
        filename = f"<{self.name}##{next(_c)}>"
        tree = ast.parse(new_code, filename=filename)
        glb = dict(self.glb)
        exec(compile(tree, filename, mode="exec"), glb)
        new_fn = glb[self.name]
        self.fn.__code__ = new_fn.__code__
        self.source[filename] = new_code
        self.source["live"] = new_code
        codefiles[filename] = CodeFile(
            module=None,
            filename=filename,
            functions={(self.name, new_fn.__code__.co_firstlineno): self},
        )
        return True


class CodeFile:
    def __init__(self, module, filename=None, functions=None):
        def acq(name, value):
            if isinstance(value, FunctionType):
                code = value.__code__
                if code.co_filename == self.filename:
                    fnobj = Function(self, value)
                    self.functions[name, code.co_firstlineno] = fnobj

        self.module = module
        self.filename = filename or module.__file__

        if functions is not None:
            self.functions = functions
        else:
            self.functions = defaultdict(dict)
            for name, value in vars(module).items():
                if isinstance(value, type):
                    for field, v in vars(value).items():
                        acq(field, v)
                else:
                    acq(name, value)

    def get(self, name, lineno):
        return self.functions.get((name, lineno), None)


def codefile(filename):
    if filename not in codefiles:
        if filename not in filename_to_module:
            _map_filenames()
        mod = filename_to_module.get(filename, None)
        if mod is None:
            return None
        codefiles[filename] = CodeFile(mod)
    return codefiles[filename]


def find_fn(obj):
    if isinstance(obj, FunctionType):
        code = obj.__code__
    else:
        code = obj

    filename = code.co_filename
    name = code.co_name
    cf = codefile(filename)
    fn = cf and cf.get(name, code.co_firstlineno)
    return fn


class BackedEditor:
    def __init__(self, func_wrapper, highlight=None):
        self.func_wrapper = func_wrapper
        self.highlight = highlight
        self.id = func_wrapper.id
        self.func = func_wrapper.fn
        self.filename = func_wrapper.filename
        self.src = textwrap.dedent(func_wrapper.source["live"]).strip()

    def save(self, new_contents):
        return self.func_wrapper.recode(new_contents)

    def commit(self, new_contents):
        return True

    @classmethod
    def __hrepr_resources__(cls, H):
        return H.javascript(
            export="BackedEditor",
            src="scripts/edit.js",
        )

    def __hrepr__(self, H, hrepr):
        return H.div["pf-bedit"](
            constructor="BackedEditor",
            options={
                "funcId": self.id,
                "contents": self.src,
                "filename": self.filename,
                "save": self.save,
                "commit": self.commit,
                "highlight": self.highlight,
            },
        )


def fnedit(func, **kwargs):
    fn = find_fn(func)
    return fn and BackedEditor(fn, **kwargs)
