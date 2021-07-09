import importlib
import sys

from ptera import Probe

from .analyze import explore
from .debug import SnekTalkDb
from .evaluator import Evaluator
from .lib import inject, snekprint as print
from .server import serve
from .session import current_session
from .utils import Interactor, pastecode, pastevar
from .version import version


def interact(prompt=">>>", **kwargs):
    glb = sys._getframe(1).f_globals
    mname = glb["__name__"]
    module = importlib.import_module(mname)
    lcl = sys._getframe(1).f_locals
    if not (sess := current_session()):
        sess = serve(**kwargs, template={"title": mname})
    Evaluator(module, glb, lcl, sess, prompt=prompt).loop()


def debug(**kwargs):
    if not current_session():
        serve(**kwargs, template={"title": "debug"})
    SnekTalkDb().set_trace()
