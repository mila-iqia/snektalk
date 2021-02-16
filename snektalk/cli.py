import importlib
import os
import runpy
import sys
from types import ModuleType

from coleo import Option, default, run_cli
from jurigged import registry
from jurigged.utils import glob_filter

from .evaluator import Evaluator
from .server import serve


def main():
    run_cli(cli)


def cli():
    # Module or module:function to run
    # [options: -m]
    module: Option = default(None)

    # Path to the script to run
    # [positional: ?]
    script: Option = default(None)

    # Script arguments
    # [remainder]
    argv: Option

    pattern = glob_filter(".")
    watch_args = {
        "registry": registry,
        "pattern": pattern,
    }

    sess = serve(watch_args=watch_args)

    if module:
        if script is not None:
            argv.insert(0, script)
        sys.argv[1:] = argv

        if ":" in module:
            module, func = module.split(":", 1)
            mod = importlib.import_module(module)
            call = getattr(mod, func)
            call()
            Evaluator(mod, vars(mod), {}, sess).loop()

        else:
            glb = runpy.run_module(module, run_name="__main__")
            Evaluator(None, glb, {}, sess).loop()

    elif script:
        path = os.path.abspath(script)
        if pattern(path):
            # It won't auto-trigger through runpy, probably some idiosyncracy of
            # module resolution
            registry.prepare("__main__", path)
        sys.argv[1:] = argv
        glb = runpy.run_path(path, run_name="__main__")
        Evaluator(None, glb, {}, sess).loop()

    else:
        mod = ModuleType("__main__")
        Evaluator(mod, vars(mod), {}, sess).loop()
