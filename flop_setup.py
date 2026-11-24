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
three Python dependencies listed in requirements.txt. Nothing else is changed
without asking.
"""

import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
VPY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

if sys.version_info < (3, 9):
    sys.exit("FLOP A-Z needs Python 3.9 or newer.")


def _deps_ok() -> bool:
    try:
        import questionary  # noqa: F401
        import rich  # noqa: F401
        import websocket  # noqa: F401
        return True
    except ImportError:
        return False


def _bootstrap() -> None:
    print("› First run: creating .venv and installing rich, questionary, websocket-client …")
    if not VPY.exists():
        try:
            venv.create(VENV, with_pip=True)
        except Exception as e:  # e.g. Debian without python3-venv
            sys.exit(f"Could not create a virtualenv ({e}).\n"
                     "Install it with:  sudo apt-get install -y python3-venv   then re-run.")
    subprocess.check_call([str(VPY), "-m", "pip", "install", "-q", "--upgrade", "pip"])
    subprocess.check_call([str(VPY), "-m", "pip", "install", "-q", "-r", str(ROOT / "requirements.txt")])


if __name__ == "__main__":
    if not _deps_ok() and Path(sys.executable).resolve() != VPY.resolve():
        if not VPY.exists() or subprocess.call(
                [str(VPY), "-c", "import rich, questionary, websocket"],
                stderr=subprocess.DEVNULL) != 0:
            _bootstrap()
        os.execv(str(VPY), [str(VPY), str(ROOT / "flop_setup.py"), *sys.argv[1:]])

    sys.path.insert(0, str(ROOT))
    from flopaz.cli import main

    sys.exit(main())
