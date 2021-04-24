
from copy import deepcopy
from snektalk.feat import edit as ed


def test_merge():
    obj = {"a": 1, "b": 2}
    a = deepcopy(obj)
    b = {"a": 1, "b": 3}
    assert obj != b
    ed._merge(obj, a, b)
    assert obj == b


def test_merge_deeper():
    obj = {"a": 1, "b": {"c": 2, "d": 3}}
    a = deepcopy(obj)
    b = {"a": 1, "b": {"c": 2, "d": 4}}
    assert obj != b
    ed._merge(obj, a, b)
    assert obj == b
