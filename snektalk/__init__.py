import importlib
import sys

from .repr import inject
from .server import run


def interact(**kwargs):
    glb = sys._getframe(1).f_globals
    module = importlib.import_module(glb["__name__"])
    inject()
    run(module, **kwargs)
