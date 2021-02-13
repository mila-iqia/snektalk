import os
import runpy
import sys

from coleo import Option, default, run_cli
from jurigged import registry
from jurigged.utils import glob_filter

from .repr import inject
from .server import run  # serve
from .session import current_session


def main():
    rval = run_cli(cli)
    execute, watch_args = rval
    inject()
    run(execute, watch_args=watch_args)


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

    if module:
        if script is not None:
            argv.insert(0, script)
        sys.argv[1:] = argv

        if ":" in module:
            module, func = module.split(":", 1)
            __import__(module, fromlist=[])

            def execute():
                mod = getattr(sys.modules[module], func)
                mod()
                current_session().set_globals(mod.__globals__)

        else:

            def execute():
                glb = runpy.run_module(module, run_name="__main__")
                current_session().set_globals(glb)

    elif script:
        path = os.path.abspath(script)
        if pattern(path):
            # It won't auto-trigger through runpy, probably some idiosyncracy of
            # module resolution
            registry.prepare("__main__", path)
        sys.argv[1:] = argv

        def execute():
            glb = runpy.run_path(path, run_name="__main__")
            current_session().set_globals(glb)

    else:

        def execute():
            current_session().set_globals({})

    return execute, watch_args
