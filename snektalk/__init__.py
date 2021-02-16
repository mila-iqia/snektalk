import importlib
import sys

from .debug import SnekTalkDb
from .evaluator import Evaluator
from .repr import inject
from .server import serve
from .utils import Interactor


def interact(**kwargs):
    glb = sys._getframe(1).f_globals
    module = importlib.import_module(glb["__name__"])
    lcl = sys._getframe(1).f_locals
    sess = serve(**kwargs)
    Evaluator(module, glb, lcl, sess).loop()


def debug(**kwargs):
    serve(**kwargs)
    SnekTalkDb().set_trace()
