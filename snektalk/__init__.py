import importlib
import sys

from .debug import SnekTalkDb
from .evaluator import Evaluator
from .repr import inject
from .server import serve
from .session import current_session
from .utils import Interactor
from .version import version


def interact(**kwargs):
    glb = sys._getframe(1).f_globals
    module = importlib.import_module(glb["__name__"])
    lcl = sys._getframe(1).f_locals
    if not (sess := current_session()):
        sess = serve(**kwargs)
    Evaluator(module, glb, lcl, sess).loop()


def debug(**kwargs):
    if not current_session():
        serve(**kwargs)
    SnekTalkDb().set_trace()
