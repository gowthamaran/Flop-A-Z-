#!/usr/bin/env python3
"""
╔══════════════════════════════════════╗
║     FLOP A-Z Setup Tool              ║
║     Made by MARAN                    ║
║     X: https://x.com/TheMaran        ║
╚══════════════════════════════════════╝

Run:  python3 flop_setup.py            (interactive menu)
      python3 flop_setup.py --help     (subcommands)

On first run this creates a private virtualenv in ./.venv and installs the
three Python dependencies listed in requirements.txt. It repairs itself if a
previous run left a broken .venv, and on Debian/Ubuntu it installs the missing
pythonX.Y-venv package (the usual cause of "No module named pip").
"""

import os
import shutil
import subprocess
import sys
import urllib.request
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
VPY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
PYVER = f"{sys.version_info.major}.{sys.version_info.minor}"
GET_PIP = "https://bootstrap.pypa.io/get-pip.py"

# Test hook: pretend ensurepip is missing (simulates Debian/Ubuntu without python3-venv).
_FAKE_NO_ENSUREPIP = os.environ.get("FLOP_AZ_TEST_NO_ENSUREPIP") == "1"

if sys.version_info < (3, 9):
    sys.exit("FLOP A-Z needs Python 3.9 or newer.")


def say(msg: str) -> None:
    print(f"› {msg}", flush=True)


def _quiet(cmd: list) -> int:
    return subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _deps_ok() -> bool:
    try:
        import questionary  # noqa: F401
        import rich  # noqa: F401
        import websocket  # noqa: F401
        return True
    except ImportError:
        return False


def _venv_has(module: str) -> bool:
    return VPY.exists() and _quiet([str(VPY), "-c", f"import {module}"]) == 0


def _make_venv(with_pip: bool) -> bool:
    shutil.rmtree(VENV, ignore_errors=True)
    if with_pip and _FAKE_NO_ENSUREPIP:
        return False
    try:
        venv.EnvBuilder(with_pip=with_pip, clear=True).create(VENV)
    except Exception:
        return False
    return VPY.exists() and (not with_pip or _venv_has("pip"))


def _apt_install_venv() -> bool:
    """Debian/Ubuntu ship venv/ensurepip separately: install pythonX.Y-venv."""
    if _FAKE_NO_ENSUREPIP or not shutil.which("apt-get"):
        return False
    pkgs = [f"python{PYVER}-venv", "python3-venv"]
    sudo = [] if os.geteuid() == 0 else ["sudo"]
    if sudo and not shutil.which("sudo"):
        return False
    say(f"Your Python {PYVER} is missing the venv/pip module. Installing {pkgs[0]} with apt-get "
        f"(this is the official Debian/Ubuntu package).")
    if sys.stdin.isatty():
        ans = input("  Continue? [Y/n] ").strip().lower()
        if ans not in ("", "y", "yes"):
            return False
    subprocess.call([*sudo, "apt-get", "update", "-qq"])
    for pkg in pkgs:
        if subprocess.call([*sudo, "apt-get", "install", "-y", "-qq", pkg]) == 0:
            return True
    return False


def _get_pip_into_venv() -> bool:
    """Last resort: venv without pip, then bootstrap pip from the official PyPA script."""
    if not _make_venv(with_pip=False):
        return False

    # 1) Official pip wheel from PyPI: a wheel is importable, so `python pip.whl/pip install` works.
    try:
        import json
        say("Bootstrapping pip from its official wheel on pypi.org …")
        with urllib.request.urlopen("https://pypi.org/pypi/pip/json", timeout=60) as r:
            meta = json.load(r)
        wheel = next(u for u in meta["urls"] if u["filename"].endswith("py3-none-any.whl"))
        dest = VENV / wheel["filename"]
        with urllib.request.urlopen(wheel["url"], timeout=120) as r, dest.open("wb") as fh:
            shutil.copyfileobj(r, fh)
        import hashlib
        if hashlib.sha256(dest.read_bytes()).hexdigest() != wheel["digests"]["sha256"]:
            raise RuntimeError("pip wheel checksum mismatch")
        if subprocess.call([str(VPY), f"{dest}/pip", "install", "-q", "--no-index", str(dest)]) == 0 \
                and _venv_has("pip"):
            return True
    except Exception as e:
        say(f"PyPI wheel bootstrap failed: {e}")

    # 2) Official PyPA get-pip.py.
    say(f"Bootstrapping pip from {GET_PIP}")
    dest = VENV / "get-pip.py"
    try:
        with urllib.request.urlopen(GET_PIP, timeout=60) as r, dest.open("wb") as fh:
            shutil.copyfileobj(r, fh)
    except Exception as e:
        say(f"Could not download get-pip.py: {e}")
        return False
    return subprocess.call([str(VPY), str(dest), "-q"]) == 0 and _venv_has("pip")


def _fail(reason: str) -> None:
    shutil.rmtree(VENV, ignore_errors=True)
    sys.exit(
        f"\n✖ {reason}\n\nFix it with one command, then re-run `python3 flop_setup.py`:\n"
        f"  Debian/Ubuntu:  sudo apt-get install -y python{PYVER}-venv python3-pip\n"
        f"  Fedora/RHEL:    sudo dnf install -y python3-pip\n"
        f"  macOS:          brew install python\n"
    )


def _bootstrap() -> None:
    say("First run: setting up a private Python environment (.venv) …")
    if _venv_has("pip"):
        pass  # existing venv is healthy; just (re)install deps
    elif _make_venv(with_pip=True):
        pass
    elif _apt_install_venv() and _make_venv(with_pip=True):
        pass
    elif _get_pip_into_venv():
        pass
    else:
        _fail(f"Could not create a Python virtual environment with pip (Python {PYVER}).")

    say("Installing rich, questionary, websocket-client …")
    rc = subprocess.call([str(VPY), "-m", "pip", "install", "-q", "--disable-pip-version-check",
                          "-r", str(ROOT / "requirements.txt")])
    if rc != 0 or not _venv_has("rich"):
        _fail("Installing the Python dependencies failed (see the pip output above).")
    say("Environment ready.\n")


if __name__ == "__main__":
    # A venv's python is a symlink to the system one, so compare prefixes, not executables.
    in_venv = Path(sys.prefix).resolve() == VENV.resolve()
    if not _deps_ok():
        if in_venv:
            _fail("This .venv is missing its dependencies. Delete the .venv folder and re-run.")
        if not (_venv_has("rich") and _venv_has("questionary") and _venv_has("websocket")):
            _bootstrap()
        os.execv(str(VPY), [str(VPY), str(ROOT / "flop_setup.py"), *sys.argv[1:]])

    sys.path.insert(0, str(ROOT))
    from flopaz.cli import main

    sys.exit(main())
