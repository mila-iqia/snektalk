import ast
import types
from itertools import product
from typing import Union

from hrepr import H, standard_terminal
from jurigged import make_recoder
from jurigged.codetools import Extent
from ovld import OvldMC, exactly, ovld
from ptera import Probe, accumulate, probing

from ..analyze import explore
from ..utils import Interactor, ObjectFields, format_libpath, newvar, pastecode

########
# edit #
########


@ovld.dispatch
def edit(self, obj, **kwargs):
    if hasattr(obj, "__snek_edit__"):
        return obj.__snek_edit__(**kwargs)
    else:
        return self[type(obj)](obj, **kwargs)


@ovld
def edit(
    obj: Union[type, types.FunctionType, types.CodeType, types.ModuleType],
    **kwargs,
):
    if hasattr(obj, "__ptera__"):
        obj = obj.__ptera__.fn
    recoder = make_recoder(obj)
    return recoder and SnekRecoder(recoder, obj, **kwargs)


@ovld
def edit(obj: Union[tuple, int, float, bool, type(None), frozenset], **kwargs):
    raise ValueError(f"Cannot edit data with type {type(obj).__qualname__}")


@ovld
def edit(obj: object, **kwargs):
    return DataEditor(obj, **kwargs)


######################
# Python code editor #
######################


@ovld
def _probables(self, seq: list, path):
    results = set()
    for node in seq:
        results |= self(node, path)
    return results


@ovld
def _probables(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef], path):
    func_path = (*path, node.name)
    return (
        self(node.body, func_path)
        | self(node.args.args, func_path)
        | self(node.args.posonlyargs, func_path)
        | self(node.args.kwonlyargs, func_path)
        | self(node.args.kwarg, func_path)
        | self(node.args.vararg, func_path)
        | self(node.decorator_list, path)
        | self(node.args.defaults, path)
        | self(node.args.kw_defaults, path)
    )


@ovld
def _probables(self, node: ast.ClassDef, path):
    cls_path = (*path, node.name)
    return self(node.body, cls_path) | self(node.decorator_list, path)


@ovld
def _probables(self, node: ast.arg, path):
    return {(*path, node.arg)}


@ovld
def _probables(self, node: ast.Name, path):
    if isinstance(node.ctx, ast.Store):
        return {(*path, node.id)}
    else:
        return set()


@ovld
def _probables(self, node: ast.AST, path):
    return self(list(ast.iter_child_nodes(node)), path)


@ovld  # pragma: no cover
def _probables(self, thing: object, path):
    # Just in case
    return set()


class SnekRecoder(Interactor):

    js_constructor = "LiveEditor"
    js_source = "/scripts/liveedit.js"

    def __init__(
        self,
        recoder,
        fn,
        code_highlight=None,
        max_height=500,
        autofocus=False,
        evaluator=None,
    ):
        self.recoder = recoder
        self.fn = fn
        super().__init__(
            {
                "content": {
                    "live": self.recoder.focus.codestring,
                    "saved": self.recoder.focus.stashed.content,
                },
                "filename": format_libpath(self.recoder.codefile.filename),
                "highlight": code_highlight,
                "max_height": max_height,
                "autofocus": autofocus,
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

    def _selector(self, selection):
        focus = self.recoder.focus
        baseline = focus.stashed
        ext = Extent(
            filename=baseline.filename,
            lineno=selection["startLineNumber"],
            col_offset=selection["startColumn"],
            end_lineno=selection["endLineNumber"],
            end_col_offset=selection["endColumn"],
        )
        lines = self.recoder.focus.codestring.split("\n")
        text = lines[ext.lineno - 1][
            ext.col_offset - 1 : ext.end_col_offset - 1
        ]
        probables = [p for p in _probables(focus.node, ()) if p[-1] == text]
        *path, varname = probables[0]

        hier = list(focus.hierarchy())
        names = [part.name for part in reversed(hier)]
        names += path[len(names) - 1 :]
        selector = "/" + "/".join(names) + " > " + varname
        return selector

    def py_explore(self, selection):
        selector = self._selector(selection)
        pastecode(
            f'explore({newvar("probe")} := Probe("{selector}"))',
            vars={
                "Probe": (Probe, "from ptera import Probe"),
                "explore": (explore, "from snektalk import explore"),
            },
        )

    def py_probe(self, selection):
        selector = self._selector(selection)
        pastecode(
            f'Probe("{selector}")',
            vars={"Probe": (Probe, "from ptera import Probe"),},
        )

    def py_local_probe(self, selection):
        selector = self._selector(selection)
        pastecode(
            f'with probing("{selector}") as probe:\n    ',
            vars={"probing": (probing, "from ptera import probing"),},
        )

    def py_local_explore(self, selection):
        selector = self._selector(selection)
        lp = newvar("lprobe")
        pastecode(
            f'{lp} = probing("{selector}")\nwith {lp} as probe:\n    explore(probe)',
            vars={
                "probing": (probing, "from ptera import probing"),
                "explore": (explore, "from snektalk import explore"),
            },
        )

    def py_accumulate(self, selection):
        selector = self._selector(selection)
        pastecode(
            f'with accumulate("{selector}") as results:\n    ',
            vars={"accumulate": (accumulate, "from ptera import accumulate"),},
        )


##########################
# Data structures editor #
##########################


class DataEditor(Interactor):

    js_constructor = "LiveEditor"
    js_source = "/scripts/liveedit.js"

    def __init__(
        self,
        obj,
        *,
        evaluator,
        code_highlight=None,
        max_height=500,
        autofocus=False,
    ):
        self.obj = obj
        self.repr = editable_repr(self.obj, evaluator=evaluator)
        self.repr = self.repr.replace(" \n", "\n")
        self.model = evaluator.eval(self.repr)
        self.evaluator = evaluator
        super().__init__(
            {
                "content": {"live": self.repr, "saved": self.repr,},
                "filename": "<data>",
                "highlight": code_highlight,
                "max_height": max_height,
                "autofocus": autofocus,
            }
        )

    def py_save(self, new_source):
        new_model = self.evaluator.eval(new_source)
        _merge(self.obj, self.model, new_model)

    def py_commit(self, new_source):
        raise Exception("This data does not correspond to a file")


class EditableRepr(metaclass=OvldMC):
    def __init__(self, max_depth, evaluator):
        self.max_depth = max_depth
        self.evaluator = evaluator
        self.seen = set()

    def ref(self, obj, wrap=H.atom):
        paths = []

        if type(obj) in (str, type(None), bool, int, float):
            return wrap(repr(obj))

        if (mod := getattr(obj, "__module__", None)) and (
            name := getattr(obj, "__qualname__", None)
        ):
            paths.append(name)
            paths.append(f"{mod}.{name}")
            paths.append(f"sktk.imp.{mod}.{name}")

        for path in paths:
            try:
                result = self.evaluator.eval(path)
                if result is obj:
                    return wrap(path)
            except Exception as exc:
                pass
        else:
            return wrap(self.evaluator.session.getvar(obj))

    def run(self, obj, *, depth):
        oid = id(obj)
        if oid in self.seen:
            return self.ref(obj)
        result = self._run(obj, depth=depth)
        self.seen.add(oid)
        return result

    @ovld
    def _run(
        self,
        s: Union[
            exactly(str),
            exactly(type(None)),
            exactly(bool),
            exactly(int),
            exactly(float),
        ],
        *,
        depth,
    ):
        return H.atom(repr(s))

    @ovld
    def _run(
        self, s: Union[types.FunctionType, types.ModuleType, type], *, depth
    ):
        return self.ref(s)

    @ovld
    def _run(self, d: exactly(dict), *, depth):
        if depth == self.max_depth:
            return self.ref(d)

        items = list(d.items())
        return H.bracketed(
            [
                H.pair(
                    self.run(k, depth=depth + 1),
                    self.run(v, depth=depth + 1),
                    delimiter=": ",
                )
                for k, v in items
            ],
            start="{",
            end="}",
            delimiter=", ",
        )

    @ovld
    def _run(self, xs: exactly(list), *, depth):
        if depth == self.max_depth:
            return self.ref(xs)

        return H.bracketed(
            [self.run(x, depth=depth + 1) for x in xs],
            start="[",
            end="]",
            delimiter=", ",
        )

    @ovld
    def _run(self, xs: exactly(tuple), *, depth):
        if depth == self.max_depth:
            return self.ref(xs)

        elems = [self.run(x, depth=depth + 1) for x in xs]
        if len(xs) == 1:
            elems.append(H.atom(""))
        return H.bracketed(elems, start="(", end=")", delimiter=", ")

    @ovld
    def _run(self, xs: exactly(set), *, depth):
        if depth == self.max_depth:
            return self.ref(xs)

        if not xs:
            return H.atom("set()")
        else:
            return H.bracketed(
                [self.run(x, depth=depth + 1) for x in xs],
                start="{",
                end="}",
                delimiter=",",
            )

    @ovld
    def _run(self, obj: object, *, depth):
        d = getattr(obj, "__dict__", None)
        if depth == self.max_depth or not isinstance(d, dict):
            return self.ref(obj)

        call = f"sktk.mod({self.ref(type(obj), wrap=str)})"
        return H.bracketed(
            [
                H.pair(k, self.run(v, depth=depth + 1), delimiter="=")
                for k, v in d.items()
            ],
            start=f"{call}(",
            end=")",
            delimiter=", ",
        )

        return self.ref(obj)

    def __call__(self, obj):
        return self.run(obj, depth=0)


def editable_repr(obj, max_depth=2, evaluator=None):
    er = EditableRepr(max_depth=max_depth, evaluator=evaluator)
    spec = standard_terminal(er(obj))
    return spec.to_string(max_col=80)


@ovld.dispatch(initial_state=lambda: {"seen": set()})
def _merge(self, obj, m1, m2):
    if m1 == m2:
        return obj
    elif type(m1) is not type(m2):
        if isinstance(m2, ObjectFields):
            raise ValueError("Cannot merge ObjectFields object")
        return m2
    elif id(obj) in self.seen:
        return obj
    else:
        self.seen.add(id(obj))
        return self.call(obj, m1, m2)


@ovld
def _merge(self, obj: dict, m1: dict, m2):
    keys = {*m1.keys(), *m2.keys()}
    for k in keys:
        if k not in m2:
            del obj[k]
        elif k not in m1:
            obj[k] = m2[k]
        else:
            obj[k] = self(obj[k], m1[k], m2[k])
    return obj


@ovld
def _merge(self, obj: list, m1: list, m2):
    ops = _sequence_operations(obj, m1, m2)
    obj[:] = []
    for op, *args in ops:
        if op == "merge":
            value = self(*args)
        else:
            (value,) = args
        obj.append(value)
    return obj


@ovld
def _merge(
    self,
    obj: Union[
        exactly(str),
        exactly(type(None)),
        exactly(bool),
        exactly(int),
        exactly(float),
    ],
    m1,
    m2,
):
    return m2


@ovld
def _merge(self, obj: object, m1: ObjectFields, m2):
    if m1.cls is not m2.cls:
        raise TypeError("Cannot update object to a different type")
    self(obj.__dict__, m1.fields, m2.fields)
    return obj


def _sequence_operations(obj, m1, m2):
    used1 = set()
    fits = [
        (_correspondence(x, y), -abs(i - j), -i, (i, j))
        for (i, x), (j, y) in product(enumerate(m1), enumerate(m2))
    ]
    fits.sort(reverse=True)
    operations = [("set", y) for y in m2]
    for _, _, _, (i, j) in fits:
        if j not in operations and i not in used1:
            operations[j] = ("merge", obj[i], m1[i], m2[j])
            used1.add(i)
    return operations


def _correspondence(x, y):
    if x is y:
        return 3
    elif x == y:
        return 2
    elif type(x) is type(y):
        return 1
    else:
        return 0
