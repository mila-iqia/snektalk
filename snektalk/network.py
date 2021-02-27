import json
import os
import socket
import subprocess
import time
import urllib
import webbrowser


def create_socket(socket_path):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(socket_path)
    usr = os.environ["USER"]
    host = socket.gethostname()
    with open(f"{socket_path}.host", "w") as hostfile:
        hostfile.write(f"{usr}@{host}")
    return s


def check_port(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", port))
    except socket.error as e:
        if e.errno == errno.EADDRINUSE:
            return False
        else:
            raise
    s.close()
    return True


def find_port(preferred_port, min_port, max_port):
    """Find a free port in the specified range.

    Use preferred_port if available (does not have to be in the range).
    """
    candidate = preferred_port
    while not check_port(candidate):
        candidate = random.randint(min_port, max_port)
    return candidate


def connect_to_existing(addr, port, sock):
    assert sock is not None
    if ":" in addr:
        addr, jump_port = addr.split(":")
    else:
        jump_port = "22"

    print("Collecting information about remote socket")
    cmd = [
        "ssh",
        addr,
        "-p",
        jump_port,
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
        port = find_port(6499, min_port=6500, max_port=6600)

    print(f"Forwarding to local port {port}")

    if host == sockhost:
        cmd = [
            "ssh",
            "-nNCL",
            f"{port}:{location}",
            addr,
            "-p",
            jump_port,
        ]

    else:
        cmd = [
            "ssh",
            "-nNCL",
            f"{port}:{location}",
            "-J",
            f"{addr}:{jump_port}",
            sockhost,
        ]

    print("Run:", " ".join(cmd))
    proc = subprocess.Popen(cmd)
    url = f"http://localhost:{port}/"
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
