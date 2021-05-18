import atexit
import errno
import ipaddress
import json
import os
import random
import socket
import subprocess
import time
import urllib
import webbrowser


def create_socket(socket_path):
    def rmsock():
        os.remove(socket_path)
        os.remove(f"{socket_path}.host")

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(socket_path)
    usr = os.environ["USER"]
    host = socket.gethostname()
    with open(f"{socket_path}.host", "w") as hostfile:
        hostfile.write(f"{usr}@{host}")
    atexit.register(rmsock)
    return s


def create_inet(randomize=False):
    # Generate a random loopback address (127.x.x.x)
    if randomize:
        addr = ipaddress.IPv4Address("127.0.0.1") + random.randrange(
            2 ** 24 - 2
        )
        addr = str(addr)
    else:
        addr = "localhost"
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((addr, 0))
    except OSError as exc:
        if exc.errno == errno.EADDRNOTAVAIL:
            # The full 127.x.x.x range may not be available on this system
            sock.bind(("localhost", 0))
    return sock


def connect_to_existing(addr, port, sock):
    assert sock is not None
    if ":" in addr:
        addr, jump_port = addr.split(":")
    else:
        jump_port = None

    print("Collecting information about remote socket")
    cmd = [
        "ssh",
        addr,
        *(["-p", jump_port] if jump_port else []),
        f"pwd; echo $USER; hostname; cat {sock}.host",
    ]
    output = subprocess.check_output(cmd)
    home, hostuser, hostname, sockhost = output.decode("utf8").split("\n")[:4]
    host = f"{hostuser}@{hostname}"
    if sock.startswith("/"):
        location = sock
    else:
        location = f"{home}/{sock}"

    print(f"Socket host: {sockhost}")
    print(f"Socket path: {location}")

    if port is None:
        sock = create_inet()
        localhost, port = sock.getsockname()
        sock.close()
    else:
        localhost = "localhost"

    print(f"Forwarding to local port {port}")

    if host == sockhost:
        cmd = [
            "ssh",
            "-nNCL",
            f"{localhost}:{port}:{location}",
            addr,
            "-p",
            jump_port,
        ]

    else:
        cmd = [
            "ssh",
            "-nNCL",
            f"{localhost}:{port}:{location}",
            "-J",
            f"{addr}:{jump_port}" if jump_port else addr,
            sockhost,
        ]

    print("Run:", " ".join(cmd))
    proc = subprocess.Popen(cmd)
    url = f"http://{localhost}:{port}/"
    print(f"Connecting to {url}")

    wait_time = 0.05
    for i in range(5):
        time.sleep(wait_time)
        wait_time *= 2
        try:
            with urllib.request.urlopen(f"{url}status") as req:
                status = json.loads(req.read().decode("utf8"))
                if status["status"] == "OK":
                    break
        except urllib.error.URLError:
            continue

    webbrowser.open(url)
    proc.wait()
