import argparse
import hashlib
import os
import socket
import subprocess
import sys
import venv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(BASE_DIR, ".venv")
REQ_FILE = os.path.join(BASE_DIR, "requirements.txt")
REQ_HASH_FILE = os.path.join(VENV_DIR, ".requirements.sha256")


def run(cmd):
    subprocess.check_call(cmd)


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def fix_requirements_encoding():
    """
    У вас requirements.txt иногда бывает UTF-16.
    Перекодируем в UTF-8 только если это действительно UTF-16.
    """
    raw = read_bytes(REQ_FILE)
    try:
        raw.decode("utf-8")
        return
    except UnicodeDecodeError:
        text = raw.decode("utf-16")
        with open(REQ_FILE, "w", encoding="utf-8") as f:
            f.write(text)
        print("✔ requirements.txt перекодирован в UTF-8")


def create_venv():
    if not os.path.exists(VENV_DIR):
        print("📦 Создание виртуального окружения...")
        venv.create(VENV_DIR, with_pip=True)
    else:
        print("✔ Виртуальное окружение уже существует")


def venv_python():
    if os.name == "nt":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def sha256_of_file(path: str) -> str:
    h = hashlib.sha256()
    h.update(read_bytes(path))
    return h.hexdigest()


def needs_install() -> bool:
    """
    Ставим зависимости только если:
    - нет файла с хэшем, или
    - requirements.txt поменялся с прошлого раза
    """
    if not os.path.exists(REQ_HASH_FILE):
        return True

    current = sha256_of_file(REQ_FILE).strip()
    old = read_bytes(REQ_HASH_FILE).decode("utf-8").strip()
    return current != old


def write_req_hash():
    os.makedirs(VENV_DIR, exist_ok=True)
    with open(REQ_HASH_FILE, "w", encoding="utf-8") as f:
        f.write(sha256_of_file(REQ_FILE))


def install_requirements(python_exec: str, force: bool = False):
    if (not force) and (not needs_install()):
        print("✔ Зависимости уже установлены (requirements.txt не менялся)")
        return

    print("📥 Установка/обновление зависимостей...")
    # pip обновлять не обязательно каждый раз — делаем только при установке зависимостей
    run([python_exec, "-m", "pip", "install", "--upgrade", "pip"])
    run([python_exec, "-m", "pip", "install", "-r", REQ_FILE])
    write_req_hash()


def migrate(python_exec: str):
    print("🗄 Применение миграций...")
    run([python_exec, "manage.py", "migrate"])


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
    # fallback
    return 0


def runserver(python_exec: str, port: int):
    if port == 0:
        print("❌ Не удалось найти свободный порт рядом с указанным.")
        sys.exit(1)

    print(f"🚀 Запуск сервера: http://127.0.0.1:{port}/")
    run([python_exec, "manage.py", "runserver", f"127.0.0.1:{port}"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000, help="Порт для запуска (по умолчанию 8000)")
    parser.add_argument("--force-install", action="store_true", help="Форсировать установку зависимостей заново")
    args = parser.parse_args()

    if not os.path.exists(os.path.join(BASE_DIR, "manage.py")):
        print("❌ start.py должен лежать в корне проекта, рядом с manage.py")
        sys.exit(1)

    fix_requirements_encoding()
    create_venv()
    py = venv_python()

    install_requirements(py, force=args.force_install)
    migrate(py)

    port = pick_port(args.port)
    if port != args.port:
        print(f"⚠ Порт {args.port} занят, беру свободный {port}")
    runserver(py, port)


if __name__ == "__main__":
    main()