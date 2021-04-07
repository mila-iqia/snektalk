import importlib
import os
import sys
from types import ModuleType

from coleo import Option, default, run_cli
from jurigged import registry
from jurigged.utils import glob_filter

from . import runpy as snek_runpy
from .evaluator import Evaluator, threads
from .network import connect_to_existing
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

    # Don't watch changes on the filesystem
    # [options: --no-watch]
    no_watch: Option & bool = default(False)

    # Server port
    # [alias: -p]
    port: Option & int = default(None)

    # Path to socket
    # [alias: -S]
    socket: Option & str = default(None)

    # Hostname to connect to an existing instance
    # [alias: -c]
    connect: Option & str = default(False)

    # Run the program in a thread
    # [alias: -t]
    thread: Option & bool = default(False)

    if connect:
        connect_to_existing(connect, port, socket)
        return

    pattern = glob_filter(".")
    if no_watch:
        watch_args = None
    else:
        watch_args = {
            "registry": registry,
            "pattern": pattern,
        }

    server_args = {
        "port": port,
        "sock": socket,
    }

    sess = serve(
        watch_args=watch_args,
        template={"title": module or script or "snektalk"},
        **server_args,
    )
    mod = None
    exc = None
    run = None

    try:
        if module:
            if script is not None:
                argv.insert(0, script)
            sys.argv[1:] = argv

            if ":" in module:
                module, func = module.split(":", 1)
                mod = importlib.import_module(module)
                run = getattr(mod, func)

            else:
                _, spec, code = snek_runpy._get_module_details(module)
                if pattern(spec.origin):
                    registry.prepare("__main__", spec.origin)
                mod = ModuleType("__main__")

                def run():
                    snek_runpy.run_module(module, module_object=mod)

        elif script:
            path = os.path.abspath(script)
            if pattern(path):
                # It won't auto-trigger through runpy, probably some idiosyncracy of
                # module resolution
                registry.prepare("__main__", path)
            sys.argv[1:] = argv
            mod = ModuleType("__main__")

            def run():
                snek_runpy.run_path(path, module_object=mod)

        else:
            mod = ModuleType("__main__")

        if run is not None:
            if thread:
                threads.run_in_thread(run, session=sess)
            else:
                run()

    except Exception as exc:
        if sess is not None:
            sess.blt["$$exc_info"] = sys.exc_info()
            sess.queue_result(exc, type="exception")
        else:
            raise

    finally:
        if sess is not None:
            Evaluator(mod, vars(mod) if mod else {}, None, sess).loop()
