import importlib
import sys

from .debug import SnekTalkDb
from .evaluator import Evaluator
from .repr import inject
from .server import serve
from .session import current_session
from .utils import Interactor, pastecode, pastevar
from .version import version


def interact(**kwargs):
    glb = sys._getframe(1).f_globals
    mname = glb["__name__"]
    module = importlib.import_module(mname)
    lcl = sys._getframe(1).f_locals
    if not (sess := current_session()):
        sess = serve(**kwargs, template={"title": mname})
    Evaluator(module, glb, lcl, sess).loop()


def debug(**kwargs):
    if not current_session():
        serve(**kwargs, template={"title": "debug"})
    SnekTalkDb().set_trace()
