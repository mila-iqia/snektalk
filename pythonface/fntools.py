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


def _analyze_source(source):
    # Compute indent
    indent = _get_indent(source)

    # Normalized source
    norm_src = textwrap.dedent(source)

    # Compute locked lines (decorator lines)
    tree = ast.parse(norm_src, filename="<string>")
    assert isinstance(tree, ast.Module)
    assert len(tree.body) == 1
    (fn,) = tree.body
    assert isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
    decos = fn.decorator_list
    if decos:
        locked_lines = max(d.end_lineno for d in decos)
    else:
        locked_lines = 0

    lines = norm_src.split("\n")
    locked = "\n".join(lines[:locked_lines]) + "\n"

    return locked_lines, locked, indent, norm_src


def _get_indent(src):
    lines = src.split("\n")
    for line in lines:
        if not src.strip():
            continue
        return len(line) - len(line.lstrip())
    else:
        return 0


class Function:
    def __init__(self, codefile, fn):
        self.id = next(_c)
        self.fn = fn
        self.name = fn.__name__
        self.orig_code = fn.__code__
        self.glb = fn.__globals__
        self.filename = codefile.filename
        src = inspect.getsource(fn)
        self.nlocked, self.locked, self.indent, norm_src = _analyze_source(src)
        self.source = {
            "real_saved": src,
            "saved": norm_src,
            "live": norm_src,
        }

    def recode(self, new_code):
        new_code = textwrap.dedent(new_code)
        if not new_code.startswith(self.locked):
            return {"success": False, "error": "decorators must be preserved"}

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
        return {"success": True}

    def replace(self, new_code):
        return {"success": False, "error": "unsupported operation"}


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

    @classmethod
    def __hrepr_resources__(cls, H):
        return H.javascript(
            export="BackedEditor",
            src="scripts/edit.js",
        )

    def __hrepr__(self, H, hrepr):
        src_live = textwrap.dedent(self.func_wrapper.source["live"]).strip()
        src_saved = textwrap.dedent(self.func_wrapper.source["saved"]).strip()

        return H.div["pf-bedit"](
            constructor="BackedEditor",
            options={
                "funcId": self.func_wrapper.id,
                "content": {
                    "live": src_live,
                    "saved": src_saved,
                },
                "filename": self.func_wrapper.filename,
                "save": self.func_wrapper.recode,
                "commit": self.func_wrapper.replace,
                "highlight": self.highlight,
                "protectedPrefix": self.func_wrapper.nlocked,
            },
        )


def fnedit(func, **kwargs):
    fn = find_fn(func)
    return fn and BackedEditor(fn, **kwargs)
