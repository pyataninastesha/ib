import argparse
import hashlib
import os
import secrets
import socket
import subprocess
import sys
import venv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(BASE_DIR, ".venv")
REQ_FILE = os.path.join(BASE_DIR, "requirements.txt")
REQ_HASH_FILE = os.path.join(VENV_DIR, ".requirements.sha256")
SECRET_FILE = os.path.join(BASE_DIR, ".local_secret_key")


def run(cmd, env=None):
    subprocess.check_call(cmd, cwd=BASE_DIR, env=env)


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def create_venv():
    if not os.path.exists(VENV_DIR):
        venv.create(VENV_DIR, with_pip=True)


def venv_python():
    if os.name == "nt":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def sha256_of_file(path: str) -> str:
    h = hashlib.sha256()
    h.update(read_bytes(path))
    return h.hexdigest()


def needs_install() -> bool:
    if not os.path.exists(REQ_HASH_FILE):
        return True
    current = sha256_of_file(REQ_FILE).strip()
    old = read_bytes(REQ_HASH_FILE).decode("utf-8").strip()
    return current != old


def write_req_hash():
    os.makedirs(VENV_DIR, exist_ok=True)
    with open(REQ_HASH_FILE, "w", encoding="utf-8") as f:
        f.write(sha256_of_file(REQ_FILE))


def install_requirements(python_exec: str):
    if not os.path.exists(REQ_FILE):
        return
    if not needs_install():
        return
    run([python_exec, "-m", "pip", "install", "--upgrade", "pip"])
    run([python_exec, "-m", "pip", "install", "-r", REQ_FILE])
    write_req_hash()


def ensure_secret_key() -> str:
    key = os.environ.get("SECRET_KEY")
    if key:
        return key

    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()

    key = secrets.token_urlsafe(64)
    with open(SECRET_FILE, "w", encoding="utf-8") as f:
        f.write(key)
    return key


def build_env():
    env = os.environ.copy()
    env.setdefault("SECRET_KEY", ensure_secret_key())
    env.setdefault("DEBUG", "True")
    return env


def is_port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((host, port)) != 0


def pick_port(preferred: int) -> int:
    if is_port_free(preferred):
        return preferred
    for p in range(preferred + 1, preferred + 50):
        if is_port_free(p):
            return p
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if not os.path.exists(os.path.join(BASE_DIR, "manage.py")):
        sys.exit(1)

    create_venv()
    py = venv_python()
    install_requirements(py)

    env = build_env()

    run([py, "manage.py", "makemigrations"], env=env)
    run([py, "manage.py", "migrate"], env=env)
    run([py, "manage.py", "seed_menu", "--reset"], env=env)

    port = pick_port(args.port)
    if port == 0:
        sys.exit(1)

    run([py, "manage.py", "runserver", f"127.0.0.1:{port}"], env=env)


if __name__ == "__main__":
    main()
