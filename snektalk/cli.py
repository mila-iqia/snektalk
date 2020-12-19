from coleo import Option, auto_cli, default

from .repr import inject
from .server import serve


def main():
    inject()
    auto_cli(cli)


def cli():
    serve()
