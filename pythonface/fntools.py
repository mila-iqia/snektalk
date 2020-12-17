import ast
import inspect
import sys
import textwrap
import weakref
from collections import defaultdict
from itertools import count
from types import CodeType, FunctionType

from ovld import ovld

_c = count()
filename_to_module = {}
codefiles = {}


class InvalidSourceException(Exception):
    pass


def _map_filenames():
    # TODO: there's probably a hook that we can use to automatically analyze
    # modules when they are imported.
    for mod in sys.modules.values():
        fname = getattr(mod, "__file__", None)
        if fname:
            filename_to_module[fname] = mod


def _get_fnode(tree, expected_name=None):
    assert isinstance(tree, ast.Module)
    if len(tree.body) == 1:
        (fn,) = tree.body
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if expected_name and expected_name != fn.name:
                raise InvalidSourceException(
                    f"the function must be named '{expected_name}'"
                )
            return fn
    raise InvalidSourceException(
        "the code may only contain a function definition"
    )


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
    locked = "\n".join(lines[:locked_lines])
    if locked:
        locked += "\n"

    return locked_lines, locked, indent, norm_src


def _get_indent(src):
    lines = src.split("\n")
    for line in lines:
        if not src.strip():
            continue
        return len(line) - len(line.lstrip())
    else:
        return 0


def declare_virtual_codefile(filename, functions):
    codefile = CodeFile(
        module=None,
        filename=filename,
        functions=functions,
    )
    codefiles[filename] = codefile
    return codefile


class Function:
    def __init__(self, codefile, fn, source=None):
        self.id = next(_c)
        self.codefile = codefile
        self.fn = fn
        self.name = fn.__name__
        self.orig_code = fn.__code__
        self.glb = fn.__globals__
        self.filename = codefile.filename
        self.firstlineno = self.fn.__code__.co_firstlineno
        src = source or inspect.getsource(fn)
        self.nlocked, self.locked, self.indent, norm_src = _analyze_source(src)
        self.source = {
            "real_saved": src,
            "saved": norm_src,
            "live": norm_src,
        }

    def recode(self, new_code):
        new_code = textwrap.dedent(new_code)
        if not new_code.startswith(self.locked):
            raise InvalidSourceException("decorators must be preserved")

        filename = f"<{self.name}##{next(_c)}>"

        tree = ast.parse(new_code, filename=filename)
        fnode = _get_fnode(tree, self.name)

        # Remove the decorators
        fnode.decorator_list.clear()

        lcl = {}
        exec(compile(tree, filename, mode="exec"), self.glb, lcl)
        new_fn = lcl[self.name]
        self.fn.__code__ = new_fn.__code__
        self.source[filename] = new_code
        self.source["live"] = new_code
        declare_virtual_codefile(
            filename=filename,
            functions={(self.name, new_fn.__code__.co_firstlineno): self},
        )
        return True

    def replace(self, new_code):
        new_code = textwrap.dedent(new_code)
        recode_results = self.recode(new_code)
        old = self.source["real_saved"]
        with open(self.codefile.filename) as fd:
            content = fd.read()
            idx = content.find(old)
            if idx == -1:
                raise InvalidSourceException(
                    "cannot update file, it might have changed"
                )
            if content.find(old, idx + 1) != -1:
                raise InvalidSourceException(
                    "ambiguous: multiple identical functions"
                )
            indented_code = textwrap.indent(new_code, " " * self.indent)
            if not indented_code.endswith("\n"):
                indented_code += "\n"
            new_content = content.replace(old, indented_code)

        with open(self.codefile.filename, "w") as fd:
            fd.write(new_content)

        self.source["saved"] = new_code
        self.source["real_saved"] = indented_code
        return True


@ovld
def dig(self, obj: FunctionType):
    return {inspect.unwrap(obj)}


@ovld
def dig(self, obj: (classmethod, staticmethod)):
    return self(obj.__func__)


@ovld
def dig(self, obj: property):
    return self(obj.fget) | self(obj.fset) | self(obj.fdel)


@ovld
def dig(self, object):
    return set()


class CodeFile:
    def __init__(self, module, filename=None, functions=None):
        def acq(name, value):
            for fn in dig(value):
                code = fn.__code__
                if code.co_filename == self.filename:
                    fnobj = Function(self, fn)
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
    if obj is None:
        return None
    elif isinstance(obj, FunctionType):
        obj = inspect.unwrap(obj)
        code = obj.__code__
    else:
        code = obj

    filename = code.co_filename
    name = code.co_name
    cf = codefile(filename)
    fn = cf and cf.get(name, code.co_firstlineno)
    return fn
