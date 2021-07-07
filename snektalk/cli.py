import sys
from types import SimpleNamespace

from coleo import Option, default, run_cli
from jurigged import registry
from jurigged.live import find_runner
from jurigged.utils import glob_filter

from .evaluator import Evaluator, threads
from .network import connect_to_existing
from .server import serve


def main():
    mod, run, sess, thread = run_cli(cli)

    try:
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
        Evaluator(mod, vars(mod) if mod else {}, None, sess).loop()


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

    # Show the version
    version: Option & bool = default(False)

    if version:
        from .version import version

        print(version)
        return

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

    restart_command = sys.argv[0:]

    sess = serve(
        watch_args=watch_args,
        template={"title": module or script or "snektalk"},
        restart_command=restart_command,
        **server_args,
    )

    opts = SimpleNamespace(module=module, script=script, rest=argv,)

    mod, run = find_runner(opts, pattern)
    return mod, run, sess, thread
