import json
import os


def get_config_path(name=None):
    path = os.path.expanduser("~/.config/snektalk")
    if name is not None:
        path = os.path.join(path, name)
    return path


def mayread(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return default


def _dump(contents, f):
    json.dump(contents, f, indent=4)


def maywrite(path, contents, dump=_dump):
    cdir = os.path.dirname(path)
    os.makedirs(cdir, exist_ok=True)
    with open(path, "w") as f:
        _dump(contents, f)
